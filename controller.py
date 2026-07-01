# -*- coding: utf-8 -*-

"""BindX 双引擎控制器。

封装 app_hotkey_manager 的 HotkeyManager 与 mouse_click 的 RemapperEngine 生命周期，
让 gui.py 不必直接接触子项目内部 API。

关键约束（来自子项目源码）：
  - HotkeyManager.start_polling_thread() 内部才初始化 _pending_registers /
    _pending_unregisters（hotkey_manager.py:829-830）；在此之前的 _register_one /
    _unregister_one 会 AttributeError。因此控制器在 init 时先 start_polling_thread，
    其后所有 CRUD 才安全。
  - start_polling_thread 启动轮询线程时会自动 RegisterHotKey 所有 enabled 条目
    （hotkey_manager.py:854-856），等价于"启动即注册"。所以 hk_running 初值跟随
    该事实设为 True。
  - RemapperEngine.start() 是重入 no-op（engine.py:37-38），stop() 不 join（daemon
    线程）；重启需 stop()->sleep(0.1)->start()，与 mouse_click/gui.py:671-676 一致。
"""

import time

import config_proxy


class BindXController:
    def __init__(self):
        hk = config_proxy.hk_module()
        mc = config_proxy.mc_engine_module()

        self._HotkeyManager = hk.HotkeyManager
        self._load_hotkey_config = hk.load_config
        self._RemapperEngine = mc.RemapperEngine
        self._load_mouse_config = mc.load_config
        self._save_mouse_config = mc.save_config

        self.hk_config = self._load_hotkey_config()
        self.hotkey_manager = self._HotkeyManager(self.hk_config)

        self.hk_running = False
        self.hotkey_manager.start_polling_thread()
        self.hk_running = True

        self.mc_config = self._load_mouse_config()
        self.mouse_engine = self._RemapperEngine()
        self.mc_running = False
        self.start_mouse()

    def set_hotkey_self_callback(self, callback):
        self.hotkey_manager.set_self_callback(callback)

    def process_hotkeys(self):
        if self.hotkey_manager is not None:
            self.hotkey_manager.process_hotkeys()

    def start_hotkey(self):
        if self.hotkey_manager is None:
            return
        self.hotkey_manager.register_all()
        self.hk_running = True

    def stop_hotkey(self):
        if self.hotkey_manager is None:
            return
        self.hotkey_manager.unregister_all()
        self.hk_running = False

    def reload_hotkey_config(self):
        self.hk_config = self._load_hotkey_config()

    def start_mouse(self):
        if self.mouse_engine is None:
            return
        self.mc_config = self._load_mouse_config()
        self.mouse_engine.start(self.mc_config)
        self.mc_running = True

    def stop_mouse(self):
        if self.mouse_engine is None:
            return
        self.mouse_engine.stop()
        self.mc_running = False

    def restart_mouse(self):
        was_running = self.mc_running
        self.mouse_engine.stop()
        time.sleep(0.1)
        if was_running:
            self.mc_config = self._load_mouse_config()
            self.mouse_engine.start(self.mc_config)
            self.mc_running = True
        else:
            self.mc_config = self._load_mouse_config()

    def save_mouse_config(self, config):
        self.mc_config = config
        self._save_mouse_config(config)

    def quit(self):
        try:
            self.hotkey_manager.unregister_all()
            self.hotkey_manager.stop_polling_thread()
        except Exception:
            pass
        try:
            self.mouse_engine.stop()
        except Exception:
            pass
