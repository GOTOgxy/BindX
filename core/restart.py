# -*- coding: utf-8 -*-
"""BindX 重启支持：解析解释器并启动新实例。

重启的完整顺序由调用方（GUI）执行：
1. 保存窗口状态；
2. 停掉钩子（controller.quit()）；
3. 释放单实例互斥体（single_instance.release()）——必须在启动新实例之前；
4. spawn_new_instance() 启动新的 pythonw 进程；
5. os._exit(0) 结束当前进程。
"""

import os
import subprocess
import sys
from pathlib import Path

from .startup_manager import APP_SCRIPT, _startup_pythonw

CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


def build_restart_command():
    """返回 (解释器, 入口脚本, 附加参数)；解析失败时抛 RuntimeError。"""
    interpreter = _startup_pythonw()
    if not interpreter.exists():
        raise RuntimeError("找不到 Python 解释器：%s" % interpreter)
    if not APP_SCRIPT.exists():
        raise RuntimeError("找不到程序入口文件：%s" % APP_SCRIPT)
    extra = ["--autostart"] if "--autostart" in sys.argv[1:] else []
    return (str(interpreter), str(APP_SCRIPT), extra)


def spawn_new_instance(interpreter, script, extra_args):
    """无控制台窗口地启动新实例，返回 Popen 对象。"""
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = (
            CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        )
    return subprocess.Popen(
        [interpreter, script] + list(extra_args),
        cwd=str(Path(script).parent),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **kwargs,
    )