import io
import logging
import os
import sys
from pathlib import Path

# 强制 stdout/stderr 使用 UTF-8 编码，避免非 UTF-8 系统环境下中文输出报错
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

os.chdir(os.path.dirname(os.path.abspath(__file__)))

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.deploy.deploy import deploy, get_main_py_path


def main():

    from maa.agent.agent_server import AgentServer
    from maa.define import LoggingLevelEnum
    from maa.tasker import Tasker

    portable_python = get_main_py_path().parents[1] / "python"
    quiet_logs = (
        Path(sys.executable).resolve().parent == portable_python
        and os.environ.get("MAAUTODORI_DEBUG_LOGS") != "1"
    )
    if quiet_logs:
        # Keep the main process's diagnostics, including failure screenshots.
        Tasker.set_log_dir("")
        Tasker.set_stdout_level(LoggingLevelEnum.Warn)
        logging.getLogger("minitouch.py").setLevel(logging.WARNING)
    else:
        Tasker.set_log_dir(Path("debug"))

    socket_id = sys.argv[-1]
    print(f"socket_id: {socket_id}")

    AgentServer.start_up(socket_id)
    AgentServer.join()
    AgentServer.shut_down()


if __name__ == "__main__":
    # 在运行主程序之前进行部署检查
    git_path = get_main_py_path().parent.parent / ".git"
    if git_path.exists():
        print("测试模式,. 不进行部署检查")
        if len(sys.argv) == 1:
            sys.argv.append("MAA_AGENT_SOCKET")
    elif not deploy():
        print("error: 部署检查失败，程序退出")
        sys.exit(1)

    from agent.CustomFile import *

    try:
        main()
    except Exception as e:
        print(f"error: 程序运行错误: {e}")
        sys.exit(1)
