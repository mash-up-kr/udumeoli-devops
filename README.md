# udumeoli 운영 모니터링

두 서버는 1분마다 서로의 상태를 확인합니다. 오전 9시(한국시간)부터 서버별 일일 상태를 한 번 보내고, 실패하면 실패한 매 분 Discord에 알립니다. 일일 알림 시각에 장애가 발생하면 한 메시지에 함께 표시합니다.

| 점검 실행 서버 | 계정 | 점검 대상 | 정상 기준 |
| --- | --- | --- | --- |
| 썸네일 서버 | `healthmonitor` | `https://pinnnned.duckdns.org/actuator/health` | HTTP 200과 `status: UP` |
| API 서버 | `deploy` | `http://10.0.0.220:8080/health` | HTTP 200과 `status: UP` |

썸네일의 `/health`는 HTTP 서버가 응답하는지 확인합니다.

각 실행 계정의 `~/health-monitor/.env`에 `HEALTH_URL`, `SERVICE_NAME`, `DISCORD_WEBHOOK_URL`을 저장합니다. 두 서버의 `.env` 권한은 `600`입니다.

`main`에 푸시하면 GitHub Actions가 두 서버의 `~/health-monitor/health_monitor.py`를 SCP로 교체합니다. 배포에는 `HEALTH_MONITOR_SSH_KEY` 저장소 Secret과 워크플로에 정의된 서버별 호스트 및 호스트 키 변수가 필요합니다.

초기 설치 시 서버에 `systemd/`의 두 파일을 `/etc/systemd/system/`에 복사한 뒤 `sudo systemctl daemon-reload`를 실행합니다. API 서버에서는 `sudo systemctl enable --now udumeoli-health-monitor@deploy.timer`, 썸네일 서버에서는 `sudo systemctl enable --now udumeoli-health-monitor@healthmonitor.timer`로 부팅 시 자동 실행을 등록합니다. 로그는 해당 `udumeoli-health-monitor@<계정>.service`의 저널에 기록됩니다.
