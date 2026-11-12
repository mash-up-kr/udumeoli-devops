import json
import os
import sys
from datetime import datetime, time
from http.client import HTTPException
from pathlib import Path
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


if __name__ == "__main__":
    os.umask(0o077)
    try:
        run(Path(__file__).resolve().parent, datetime.now(SEOUL))
    except HTTPError as error:
        sys.exit(f"Discord 전송 실패 · HTTP {error.code}")
    except (KeyError, OSError, ValueError, HTTPException) as error:
        sys.exit(f"헬스체크 실행 실패 · {type(error).__name__}")
