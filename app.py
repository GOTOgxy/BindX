# -*- coding: utf-8 -*-

import atexit
import sys

from core import single_instance


def main():
    start_hidden = "--autostart" in sys.argv[1:]

    if not single_instance.acquire():
        print("BindX 已在运行。")
        return

    atexit.register(single_instance.release)

    from core import config_proxy
    config_proxy.init_subprojects()

    from core.controller import BindXController
    from core.gui import BindXApp

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