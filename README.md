# BindX

Hot Key（全局热键管理）与 Mouse（按键重映射）的统一编排器。

单进程、单托盘、单 UI，同时驱动两个子项目的核心引擎，子项目源码**零修改**。
独立运行子项目仍完全可用（各自 `.bat` / `app.py` 不受影响）。

## 项目结构

```
BindX/
├── app_hotkey_manager/  子项目（自带 .git，独立可用）
├── mouse_click/          子项目（自带 .git，独立可用）
├── app.py                BindX 入口（单实例 mutex → init → BindXApp mainloop）
├── gui.py                统一 UI（ttk.Notebook 三页 + 托盘）
├── controller.py         双引擎生命周期封装
├── tray.py               BindX 系统托盘（纯 ctypes，手绘图标）
├── config_proxy.py       子项目模块加载器（importlib，解决 gui.py 名冲突）
├── BindX.bat             启动器
├── install_startup.bat   安装开机自启
├── uninstall_startup.bat 移除开机自启
├── pin_to_start.bat      创建开始菜单快捷方式
├── requirements.txt      keyboard, pynput
└── README.md
```

## 运行要求

- Windows 10 / 11
- Python 3.10+（项目使用 PEP 604 `X | Y` 语法）
- `pip install -r requirements.txt`（keyboard, pynput）

## 快速启动

```bat
pip install -r requirements.txt
BindX.bat
```

或直接：

```bat
python app.py
```

## 架构

BindX 通过 `importlib.util.spec_from_file_location` 将子项目源码按受控名字加载进同一进程：

| 子项目文件             | sys.modules 名     | 用途                               |
|------------------------|---------------------|------------------------------------|
| mouse_click/engine.py  | `engine`            | RemapperEngine 引擎 + 配置读写     |
| mouse_click/gui.py     | `bindx_mc_gui`      | AddMappingDialog 等对话框类        |
| app_hotkey_manager/hotkey_manager.py | `hotkey_manager` | HotkeyManager 引擎 + DLL argtypes  |
| app_hotkey_manager/gui.py         | `bindx_hk_gui`      | EntryDialog 等对话框类             |

两个 `gui.py` 用别名避免模块名冲突；引擎用自然名以便各自 gui 的 `from engine import ...` /
`from hotkey_manager import ...` 能找到依赖。

### 加载顺序

mouse_click → app_hotkey_manager（mouse_click/gui.py 顶层设置部分 user32 argtypes，app_hotkey_manager/hotkey_manager.py
随后覆盖为完整签名——HotkeyManager 依赖这些签名；BindX 仅复用 mouse_click 的对话框类，
不使用其 ctypes 托盘代码，故覆盖无副作用）。

### 线程模型

- **主线程**：tkinter mainloop + BindX 托盘 WndProc + 状态刷新
- **HotKey daemon**：RegisterHotKey + PeekMessageW 轮询（来自 hotkey_manager）
- **Mouse daemon**：keyboard.hook + pynput.mouse.Listener（来自 engine）

### 配置

- Hot Key 条目 → `app_hotkey_manager/app_hotkey_config.json`（子项目原路径，`Path(__file__).parent` 定位）
- Mouse 映射   → `mouse_click/config.json`（同上）

BindX UI 编辑直接写回各自 JSON，子项目独立运行时共享同一份配置。

## UI 说明

三页 Notebook：

1. **总览**：Hot Key / Mouse 引擎运行状态 + 启停按钮 + 全局动作（全部启动 / 全部停止 / 退出）
2. **Hot Key**：条目列表（应用 / 快捷键 / 启用 / 启动未运行 / 安装路径），增删改查 + 录制
   - 双击"启用"列切换条目启用/禁用
   - 双击"启动未运行"列切换 launch_if_not_running
   - 双击其他列打开编辑对话框
   - 右键菜单：编辑 / 启用-禁用 / 删除
3. **Mouse**：映射列表（启用 / 类型 / 触发 / 输出 / 描述），增删改查 + 录制
   - 双击"启用"列切换映射启用/禁用
   - 右键菜单：编辑 / 启用-禁用 / 删除

### 系统托盘

紫色 "BX" 图标（手绘 16×16）：
- 左键 / 双击 → 显示主窗口
- 右键 → 菜单（显示主窗口 / 启停 Hot Key / 启停 Mouse / 退出）

关闭主窗口 → 最小化到托盘（不退出）；退出仅通过托盘菜单"退出"或总览页"退出 BindX"按钮。

### 自热键

CTRL+ALT+H 由 HotKeyManager 自动注入，回调指向 BindX 主窗口的显隐切换。
可在 Hot Key 页编辑/禁用该条目。

## 批处理文件

| 文件                  | 作用                                           |
|-----------------------|------------------------------------------------|
| `BindX.bat`           | `cd /d %~dp0` + `start "" pythonw app.py`     |
| `install_startup.bat` | 复制 BindX.bat 到 `%APPDATA%\...\Startup\`    |
| `uninstall_startup.bat`| 删除上述文件                                   |
| `pin_to_start.bat`    | VBS 创建 `%APPDATA%\...\Programs\BindX.lnk`   |

`install_startup.bat` 只装 BindX.bat；开机后 BindX 启动并在进程内拉起两个引擎，
不需要分别安装子项目的自启。

## ⚠ 重要提示

- **不要同时运行 BindX 和子项目独立版**。BindX 已在进程内注册所有热键 + 鼠标钩子，
  若同时运行 `app_hotkey_manager\app_hotkey_manager.bat` 或 `mouse_click\mouse_remapper.bat`，
  会导致热键重复注册 / 钩子重复挂载。
- 如需单独使用某个子项目，请先退出 BindX。

## 子项目独立运行

```bat
cd app_hotkey_manager
pip install -r requirements.txt    # 空（零依赖）
app_hotkey_manager.bat             # 或 python app.py

cd mouse_click
pip install -r requirements.txt    # keyboard, pynput
mouse_remapper.bat                 # 或 python app.py
```
