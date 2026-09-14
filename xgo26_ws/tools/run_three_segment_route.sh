#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PYTHON=${XGO_PYTHON:-/home/pi/RaspberryPi-CM5/xgovenv/bin/python}
CAMERA_PID=""

cleanup() {
    trap - EXIT INT TERM
    if [[ -n "$CAMERA_PID" ]]; then
        kill -TERM "$CAMERA_PID" 2>/dev/null || true
        wait "$CAMERA_PID" 2>/dev/null || true
    fi
    rm -f /tmp/xgo26-three-segment-camera.log
    sudo systemctl start oumax-camera.service oumax-manual.service || true
    sudo systemctl restart --no-block rc-local.service || true
}

trap cleanup EXIT
trap 'exit 130' INT TERM

cd "$ROOT"
sudo systemctl stop rc-local.service oumax-manual.service oumax-camera.service
sudo pkill -TERM -f '^python common/main.py$' 2>/dev/null || true
sudo pkill -TERM -f '^su - pi -c .*common/main.py.*$' 2>/dev/null || true
sleep 2

if sudo fuser /dev/ttyAMA0 >/dev/null 2>&1; then
    echo "[three-segment] 控制串口仍被其他进程占用，拒绝启动" >&2
    sudo fuser -v /dev/ttyAMA0 >&2 || true
    exit 1
fi

PYTHONUNBUFFERED=1 "$PYTHON" scripts/run_camera_service.py \
    >/tmp/xgo26-three-segment-camera.log 2>&1 &
CAMERA_PID=$!

for _ in {1..30}; do
    if curl -fsS --max-time 1 http://127.0.0.1:8090/health >/dev/null; then
        break
    fi
    if ! kill -0 "$CAMERA_PID" 2>/dev/null; then
        cat /tmp/xgo26-three-segment-camera.log >&2
        exit 1
    fi
    sleep 0.2
done

curl -fsS --max-time 2 http://127.0.0.1:8090/health >/dev/null || {
    echo "[three-segment] 比赛相机服务未就绪" >&2
    exit 1
}

"$PYTHON" tools/test_three_segment_route.py
