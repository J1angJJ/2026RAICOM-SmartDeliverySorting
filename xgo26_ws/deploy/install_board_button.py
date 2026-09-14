#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import stat
import tempfile
from pathlib import Path


DEFAULT_MAIN = Path("/home/pi/RaspberryPi-CM5/common/main.py")
DEFAULT_WORKSPACE = Path("/home/pi/2026-raicom-smart-delivery-sorting/xgo26_ws")
BACKUP_SUFFIX = ".before-xgo26"
ORIGINAL = '        print("b button, but nothing to quit")'
MARKER = "        # XGO26_BOARD_START"


def replacement(workspace: Path) -> str:
    launcher = workspace / "scripts" / "run_board_start.py"
    return "\n".join(
        [
            MARKER,
            f"        launcher = {str(launcher)!r}",
            "        os.system(f'\"{sys.executable}\" \"{launcher}\"')",
        ]
    )


def state(main_path: Path) -> str:
    source = main_path.read_text(encoding="utf-8")
    if MARKER in source:
        return "installed"
    if ORIGINAL in source:
        return "patchable"
    return "unknown"


def atomic_write(path: Path, source: str) -> None:
    compile(source, str(path), "exec")
    path_stat = path.stat()
    mode = stat.S_IMODE(path_stat.st_mode)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(source)
        temporary = Path(handle.name)
    try:
        os.chmod(temporary, mode)
        os.chown(temporary, path_stat.st_uid, path_stat.st_gid)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def install(main_path: Path, workspace: Path) -> None:
    current = state(main_path)
    if current == "installed":
        backup = main_path.with_name(main_path.name + BACKUP_SUFFIX)
        if not backup.is_file():
            raise FileNotFoundError(f"挂接已存在但缺少可恢复备份: {backup}")
        print(f"already installed: {main_path}")
        return
    if current != "patchable":
        raise RuntimeError("main.py 内容与已知 CM5 版本不符，拒绝自动修改")

    launcher = workspace / "scripts" / "run_board_start.py"
    if not launcher.is_file():
        raise FileNotFoundError(f"找不到启动器: {launcher}")

    backup = main_path.with_name(main_path.name + BACKUP_SUFFIX)
    if backup.exists():
        if backup.read_bytes() != main_path.read_bytes():
            raise FileExistsError(f"已有备份与当前厂家文件不同，拒绝覆盖: {backup}")
        print(f"reuse backup: {backup}")
    else:
        shutil.copy2(main_path, backup)

    source = main_path.read_text(encoding="utf-8")
    updated = source.replace(ORIGINAL, replacement(workspace), 1)
    try:
        atomic_write(main_path, updated)
    except Exception:
        shutil.copy2(backup, main_path)
        raise
    print(f"installed: {main_path}")
    print(f"backup: {backup}")


def restore(main_path: Path) -> None:
    backup = main_path.with_name(main_path.name + BACKUP_SUFFIX)
    if not backup.is_file():
        raise FileNotFoundError(f"找不到备份: {backup}")
    compile(backup.read_text(encoding="utf-8"), str(backup), "exec")
    shutil.copy2(backup, main_path)
    print(f"restored: {main_path}")
    print(f"backup retained: {backup}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Install or restore the XGO26 B-button hook")
    parser.add_argument("action", choices=("check", "install", "restore"))
    parser.add_argument("--main", type=Path, default=DEFAULT_MAIN, help="厂家 common/main.py 路径")
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE, help="板端 xgo26_ws 路径")
    args = parser.parse_args()

    main_path = args.main.resolve()
    workspace = args.workspace.resolve()
    if args.action == "check":
        print(f"{main_path}: {state(main_path)}")
    elif args.action == "install":
        install(main_path, workspace)
    else:
        restore(main_path)


if __name__ == "__main__":
    main()
