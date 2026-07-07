# -*- coding: utf-8 -*-

import atexit
import ctypes
import sys

ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = "Global\\BindX"


def main():
    start_hidden = "--autostart" in sys.argv[1:]
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p

    mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        print("BindX 已在运行。")
        return

    atexit.register(kernel32.CloseHandle, mutex)

    import config_proxy
    config_proxy.init_subprojects()

    from controller import BindXController
    from gui import BindXApp

    controller = BindXController()
    app = BindXApp(controller)
    if start_hidden:
        app.withdraw()
    app.mainloop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
