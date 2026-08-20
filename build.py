"""Сборка KrpaBindu.exe с помощью PyInstaller."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = "Krpabindu"


def build() -> int:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--noconsole",
        f"--name={NAME}",
        str(ROOT / "main.py"),
    ]

    icon = ROOT / "assets" / "icon.ico"
    if icon.exists():
        command.append(f"--icon={icon}")

    print("Сборка:", " ".join(command))
    return subprocess.call(command, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(build())
