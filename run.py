# -*- coding: utf-8 -*-
# @Time    : 26/10/18 0:12
# @Author  : yy
# @File    : run.py
# @Software: cbg_test
"""

启动入口，职责：
1. 确保 reports 目录存在（pytest-html 写报告需要）
2. 检查登录态文件，缺失则自动拉起登录流程
3. 调 pytest 并透传参数、透传退出码
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORTS_DIR = ROOT / "reports"


def main():
    args = sys.argv[1:]

    force = "--relogin" in args
    if force:
        args.remove("--relogin")
        os.environ["CBG_FORCE_RELOGIN"] = "1"

    REPORTS_DIR.mkdir(exist_ok=True)

    cmd = [sys.executable, "-m", "pytest", *args]
    print(f"[run] 执行: {' '.join(cmd)}")
    sys.exit(subprocess.run(cmd, cwd=ROOT).returncode)


if __name__ == "__main__":
    main()