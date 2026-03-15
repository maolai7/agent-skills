#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys


def check_python() -> dict:
    result = {
        "python_found": False,
        "python_cmd": None,
        "python_version": None,
        "python_ok": False,
        "uv_found": False,
        "venv_available": False,
        "install_hint": "未检测到可用 Python 3.10+。请先安装 Python，或在你确认后由 agent 帮你安装。",
    }

    candidates = ["python3", "python"]
    for cmd in candidates:
        path = shutil.which(cmd)
        if not path:
            continue
        try:
            out = subprocess.check_output([cmd, "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"], text=True).strip()
            parts = tuple(int(x) for x in out.split("."))
            result["python_found"] = True
            result["python_cmd"] = cmd
            result["python_version"] = out
            result["python_ok"] = parts >= (3, 10)
            break
        except Exception:
            continue

    result["uv_found"] = shutil.which("uv") is not None

    if result["python_found"]:
        try:
            subprocess.check_call([result["python_cmd"], "-c", "import venv"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            result["venv_available"] = True
        except Exception:
            result["venv_available"] = False

        if result["python_ok"]:
            result["install_hint"] = "Python 环境可用。优先用 uv；若无 uv，可用 venv + pip。"
        else:
            result["install_hint"] = "检测到 Python，但版本低于 3.10。请升级 Python，或在你确认后由 agent 帮你安装/升级。"

    return result


if __name__ == "__main__":
    json.dump(check_python(), sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
