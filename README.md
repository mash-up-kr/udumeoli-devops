# udumeoli 운영 모니터링

서버의 `deploy` 계정이 1분마다 `/actuator/health`를 호출합니다. HTTP 200과 `status: UP`을 정상으로 판단합니다. 오전 9시(한국시간)부터 그날의 일일 상태를 한 번 보내며, 점검에 실패하면 실패한 매 분 Discord에 알립니다. 일일 알림 시각에 장애가 발생하면 일일 메시지에 장애 상태를 담습니다.

서버의 `~/health-monitor/.env`에 아래 값을 한 줄씩 저장합니다.

```dotenv
HEALTH_URL=https://pinnnned.duckdns.org/actuator/health
DISCORD_WEBHOOK_URL=<Discord 웹훅 URL>
```

`main`에 푸시하면 GitHub Actions가 SCP로 `~/health-monitor/health_monitor.py`를 교체합니다. 배포에는 `HEALTH_MONITOR_SSH_KEY` 저장소 Secret과 `HEALTH_MONITOR_SSH_HOST`, `HEALTH_MONITOR_SSH_KNOWN_HOSTS` 저장소 변수가 필요합니다. 서버의 `.env`와 일일 발송 기록은 배포 사이에도 유지됩니다. 서버 로그는 `journalctl -t udumeoli-health-monitor`로 확인할 수 있습니다.
