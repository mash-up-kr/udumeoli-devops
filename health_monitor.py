import argparse
import json
import os
import shutil
import socket
import sys
from datetime import datetime, time
from http.client import HTTPException
from pathlib import Path
from time import sleep
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


SEOUL = ZoneInfo("Asia/Seoul")
DAILY_REPORT_TIME = time(9, 0)
REQUEST_TIMEOUT = 8


def read_config(path):
    config = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        config[key.strip()] = value.strip()
    return config


def check_health(url):
    try:
        request = Request(url, headers={"Accept": "application/json"})
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            if response.status != 200:
                return f"HTTP {response.status}"
            body = json.load(response)
    except HTTPError as error:
        return f"HTTP {error.code}"
    except (OSError, HTTPException) as error:
        return f"응답 실패 ({type(error).__name__})"
    except ValueError:
        return "JSON 응답을 읽을 수 없음"

    if not isinstance(body, dict) or body.get("status") != "UP":
        return "Actuator 상태가 UP이 아님"
    return None


def send_discord(url, message):
    payload = {"content": message, "allowed_mentions": {"parse": []}}
    separator = "&" if "?" in url else "?"
    request = Request(
        f"{url}{separator}wait=true",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "udumeoli-health-monitor/1.0"},
        method="POST",
    )
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        if response.status != 200:
            raise ValueError("Discord did not confirm delivery")


def run(directory, now):
    config = read_config(directory / ".env")
    service_name = config.get("SERVICE_NAME", "udumeoli")
    failure = check_health(config["HEALTH_URL"])
    daily_state = directory / ".last-daily-status"
    today = now.date().isoformat()
    try:
        last_report = daily_state.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        last_report = None

    daily_due = now.time() >= DAILY_REPORT_TIME and last_report != today
    if failure is None and not daily_due:
        return

    title = "일일 상태" if daily_due else "장애 알림"
    if daily_due and failure:
        title = "일일 상태 · 장애 알림"
    status = f"🔴 비정상 · {failure}" if failure else "🟢 정상 · UP"
    message = f"**{service_name} {title}**\n{status}\n{now:%Y-%m-%d %H:%M} KST"
    send_discord(config["DISCORD_WEBHOOK_URL"], message)

    if daily_due:
        temporary_state = daily_state.with_suffix(".tmp")
        temporary_state.write_text(f"{today}\n", encoding="utf-8")
        temporary_state.replace(daily_state)
    print(f"Discord 알림 전송 완료 · {service_name} · {title} · {now:%Y-%m-%d %H:%M} KST")


def read_cpu_times():
    with Path("/proc/stat").open(encoding="utf-8") as stat:
        counters = [int(value) for value in stat.readline().split()[1:9]]
    user, nice, system, _, _, irq, softirq, _ = counters
    return sum(counters), user + nice + system + irq + softirq


def format_usage(used, total, unit, divisor):
    percent = 100 * used / total if total else 0
    return f"{used / divisor:.1f} / {total / divisor:.1f} {unit} ({percent:.1f}%)"


def report_resources(directory, now):
    config = read_config(directory / ".env")
    host_name = config.get("RESOURCE_HOST_NAME", socket.gethostname())

    total_before, busy_before = read_cpu_times()
    sleep(1)
    total_after, busy_after = read_cpu_times()
    elapsed = total_after - total_before
    cpu = 100 * (busy_after - busy_before) / elapsed if elapsed > 0 else 0

    memory = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        name, value = line.split(":", 1)
        if name in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree"):
            memory[name] = int(value.split()[0])
    ram = format_usage(memory["MemTotal"] - memory["MemAvailable"], memory["MemTotal"], "MiB", 1024)
    swap = format_usage(memory["SwapTotal"] - memory["SwapFree"], memory["SwapTotal"], "MiB", 1024)
    disk = shutil.disk_usage("/")
    root = format_usage(disk.used, disk.total, "GiB", 1024**3)

    message = (
        f"**{host_name} 리소스 사용량**\n"
        f"CPU · {cpu:.1f}% (1초 평균)\n"
        f"메모리 · {ram}\n"
        f"스왑 · {swap}\n"
        f"디스크 `/` · {root}\n"
        f"{now:%Y-%m-%d %H:%M} KST"
    )
    send_discord(config["DISCORD_WEBHOOK_URL"], message)
    print(f"Discord 리소스 보고 전송 완료 · {host_name} · {now:%Y-%m-%d %H:%M} KST")


if __name__ == "__main__":
    os.umask(0o077)
    parser = argparse.ArgumentParser(description="Udumeoli monitoring")
    parser.add_argument("mode", nargs="?", default="health", choices=("health", "resources"))
    args = parser.parse_args()
    monitor = report_resources if args.mode == "resources" else run
    try:
        monitor(Path(__file__).resolve().parent, datetime.now(SEOUL))
    except HTTPError as error:
        sys.exit(f"Discord 전송 실패 · HTTP {error.code}")
    except (KeyError, OSError, ValueError, HTTPException) as error:
        sys.exit(f"모니터 실행 실패 · {args.mode} · {type(error).__name__}")
