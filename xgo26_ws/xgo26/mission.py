from __future__ import annotations

import argparse
import json
import time
from enum import Enum
from pathlib import Path

from .actions import grasp_ball, place_task, prepare_for_mission, speak_task
from .config import load_config
from .motion import Motion
from .perception import DeliveryTask, capture_and_vote_expected
from .robot import Robot


class MissionState(str, Enum):
    BOOT_CHECK = "BOOT_CHECK"
    FOLLOW_TO_RECOGNITION_1 = "FOLLOW_TO_RECOGNITION_1"
    DETECT_PACKAGE_1 = "DETECT_PACKAGE_1"
    FOLLOW_TO_RECOGNITION_2 = "FOLLOW_TO_RECOGNITION_2"
    DETECT_PACKAGE_2 = "DETECT_PACKAGE_2"
    GO_TO_PICK_AREA = "GO_TO_PICK_AREA"
    PICK_AND_DELIVER = "PICK_AND_DELIVER"
    RETURN_TO_PICK_AREA = "RETURN_TO_PICK_AREA"
    FINISH = "FINISH"


class MissionRunner:
    def __init__(
        self,
        config: dict,
        dry_run: bool = False,
        use_expected: bool = False,
        robot: Robot | None = None,
        motion: Motion | None = None,
    ):
        self.config = config
        self.dry_run = dry_run
        self.use_expected = use_expected
        self.robot = robot or Robot(
            serial_port=config["robot"].get("serial_port", "/dev/ttyAMA0"),
            dry_run=dry_run,
        )
        self.motion = motion or Motion(self.robot)
        self.routes = config["mission"]["routes"]
        self.expected = list(config["mission"].get("expected_tasks", []))
        self.tasks: list[DeliveryTask] = []

    def run(self) -> None:
        started = time.time()
        try:
            self.enter(MissionState.BOOT_CHECK)
            self.boot_check()
            self.enter(MissionState.FOLLOW_TO_RECOGNITION_1)
            self.go("start_to_recognition_1")
            self.enter(MissionState.DETECT_PACKAGE_1)
            self.detect_package(0)
            self.enter(MissionState.FOLLOW_TO_RECOGNITION_2)
            self.go("recognition_1_to_recognition_2")
            self.enter(MissionState.DETECT_PACKAGE_2)
            self.detect_package(1)
            self.enter(MissionState.GO_TO_PICK_AREA)
            self.go("recognition_2_to_pick_area")
            for index, task in enumerate(self.tasks):
                self.enter(MissionState.PICK_AND_DELIVER)
                self.pick_and_deliver(task)
                if index == 0:
                    self.enter(MissionState.RETURN_TO_PICK_AREA)
                    self.go("return_to_pick_area")
            self.enter(MissionState.FINISH)
            self.finish(started)
        except KeyboardInterrupt:
            print("[mission] interrupted")
            self.robot.stop()
            raise
        except Exception as exc:
            print(f"[mission] failed: {exc}")
            self.robot.stop()
            raise

    def enter(self, state: MissionState) -> None:
        print(f"[mission] STATE {state.value}")

    def boot_check(self) -> None:
        battery = self.robot.read_battery()
        if battery is not None:
            print(f"[mission] battery={battery}%")
        self.robot.initialize_control_mode(self.config["robot"].get("control", {}))
        prepare_for_mission(self.robot)

    def go(self, route_name: str) -> None:
        print(f"[mission] GO {route_name}")
        route = self.routes.get(route_name)
        if route is None:
            raise KeyError(f"未配置路线: {route_name}")
        self.motion.run_route(route_name, route)

    def detect_package(self, index: int) -> None:
        print(f"[mission] DETECT_PACKAGE_{index + 1}")
        expected = self.expected[index] if self.use_expected and index < len(self.expected) else None
        task = capture_and_vote_expected(self.config, expected)
        print(f"[mission] detected: {task.summary()}")
        speak_task(task, dry_run=self.dry_run)
        self.tasks.append(task)

    def pick_and_deliver(self, task: DeliveryTask) -> None:
        print(f"[mission] PICK_AND_DELIVER {task.summary()}")
        grasp_ball(self.robot, self.motion, task.ball_color, self.config)
        print("[mission] hold ball for 3 seconds")
        if not self.dry_run:
            time.sleep(3.0)
        route_name = f"drop_{task.letter}"
        self.go(route_name)
        place_task(self.robot, task, self.config)

    def finish(self, started: float) -> None:
        self.robot.stop()
        elapsed = time.time() - started
        print("[mission] FINISH")
        print("[mission] tasks=" + json.dumps([task.__dict__ for task in self.tasks], ensure_ascii=False))
        print(f"[mission] elapsed={elapsed:.1f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAICOM 2026 XGO mission")
    parser.add_argument("--config", default="config.json", help="配置文件路径")
    parser.add_argument("--dry-run", action="store_true", help="不连接硬件，只打印动作")
    parser.add_argument(
        "--use-expected",
        action="store_true",
        help="使用 config.json 中 expected_tasks 作为识别结果",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    runner = MissionRunner(config, dry_run=args.dry_run, use_expected=args.use_expected)
    runner.run()


if __name__ == "__main__":
    main()
