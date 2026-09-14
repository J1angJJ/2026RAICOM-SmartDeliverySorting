from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


B_BUTTON_PIN = 23
DEFAULT_CONFIRM_WINDOW = 1.2
DEFAULT_COUNTDOWN_SECONDS = 3
LOCK_PATH = Path("/tmp/xgo26-mission.lock")


class StatusDisplay:
    """Best-effort LCD feedback without importing uiutils or opening the robot serial port."""

    def __init__(self) -> None:
        self.display = None
        self.image = None
        self.draw = None
        self.font_small = None
        self.font_large = None
        try:
            import xgoscreen.LCD_2inch as LCD_2inch
            from PIL import Image, ImageDraw, ImageFont

            font_path = "/home/pi/RaspberryPi-CM5/common/model/msyh.ttc"
            self.display = LCD_2inch.LCD_2inch()
            self.display.Init()
            self.image = Image.new("RGB", (320, 240), (15, 21, 46))
            self.draw = ImageDraw.Draw(self.image)
            self.font_small = ImageFont.truetype(font_path, 24)
            self.font_large = ImageFont.truetype(font_path, 56)
        except Exception as exc:
            print(f"[board-start] LCD unavailable: {exc}")

    def show(self, title: str, detail: str = "") -> None:
        print(f"[board-start] {title} {detail}".rstrip())
        if self.display is None or self.draw is None or self.image is None:
            return
        self.draw.rectangle((0, 0, 320, 240), fill=(15, 21, 46))
        title_box = self.draw.textbbox((0, 0), title, font=self.font_small)
        title_width = title_box[2] - title_box[0]
        self.draw.text(((320 - title_width) // 2, 58), title, fill="white", font=self.font_small)
        if detail:
            detail_box = self.draw.textbbox((0, 0), detail, font=self.font_large)
            detail_width = detail_box[2] - detail_box[0]
            self.draw.text(((320 - detail_width) // 2, 108), detail, fill=(90, 200, 255), font=self.font_large)
        self.display.ShowImage(self.image)


class BoardButton:
    def __init__(self, pin: int = B_BUTTON_PIN, poll_seconds: float = 0.02) -> None:
        self.pin = pin
        self.poll_seconds = poll_seconds

    def prepare(self) -> None:
        result = subprocess.run(
            ["sudo", "-n", "pinctrl", "set", str(self.pin), "ip"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "无法初始化 B 键 GPIO")

    def is_pressed(self) -> bool:
        result = subprocess.run(
            ["sudo", "-n", "pinctrl", "level", str(self.pin)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise RuntimeError(result.stderr.strip() or "无法读取 B 键 GPIO")
        return result.stdout.strip()[0] == "0"

    def wait_for_press(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.is_pressed():
                while self.is_pressed():
                    time.sleep(self.poll_seconds)
                return True
            time.sleep(self.poll_seconds)
        return False


def service_is_active(unit: str) -> bool:
    result = subprocess.run(
        ["systemctl", "is-active", "--quiet", unit],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def camera_is_ready(url: str = "http://127.0.0.1:8090/health") -> bool:
    try:
        with urlopen(url, timeout=1.0) as response:
            return response.status == 200
    except (OSError, URLError):
        return False


def run_board_start(
    workspace: Path,
    confirm_window: float | None = None,
    countdown_seconds: int | None = None,
) -> int:
    config_path = workspace / "config.json"
    if not config_path.is_file():
        raise FileNotFoundError(f"比赛工作区不完整: {workspace}")
    with config_path.open(encoding="utf-8") as handle:
        config = json.load(handle)
    start_config = config.get("board_start", {})
    confirm_window = float(
        start_config.get("confirm_window", DEFAULT_CONFIRM_WINDOW)
        if confirm_window is None
        else confirm_window
    )
    countdown_seconds = int(
        start_config.get("countdown_seconds", DEFAULT_COUNTDOWN_SECONDS)
        if countdown_seconds is None
        else countdown_seconds
    )

    display = StatusDisplay()
    button = BoardButton()
    button.prepare()

    display.show("PRESS B AGAIN")
    if not button.wait_for_press(confirm_window):
        display.show("START CANCELLED")
        time.sleep(0.8)
        return 2

    if not bool(start_config.get("armed", False)):
        display.show("MISSION NOT ARMED")
        print("[board-start] set board_start.armed=true only after staged motion tests")
        time.sleep(2.0)
        return 6

    if service_is_active("oumax-manual.service"):
        display.show("MANUAL SERVICE ON")
        print("[board-start] disable oumax-manual.service before competition mode")
        time.sleep(2.0)
        return 3

    if not camera_is_ready():
        display.show("CAMERA NOT READY")
        print("[board-start] xgo26 camera service health check failed")
        time.sleep(2.0)
        return 5

    lock_file = LOCK_PATH.open("w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        display.show("MISSION RUNNING")
        lock_file.close()
        time.sleep(1.5)
        return 4

    try:
        for remaining in range(max(0, countdown_seconds), 0, -1):
            display.show("MISSION STARTS IN", str(remaining))
            time.sleep(1.0)

        mission_script = workspace / "scripts" / "run_mission.py"
        if not mission_script.is_file():
            raise FileNotFoundError(f"比赛工作区不完整: {workspace}")

        display.show("MISSION RUNNING")
        result = subprocess.run(
            [sys.executable, str(mission_script), "--config", str(config_path)],
            cwd=workspace,
        )
        if result.returncode == 0:
            display.show("MISSION FINISHED")
        else:
            display.show("MISSION FAILED", str(result.returncode))
        time.sleep(2.0)
        return result.returncode
    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()


def default_workspace() -> Path:
    configured = os.environ.get("XGO26_WORKSPACE")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[1]
