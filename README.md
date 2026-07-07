# BindX

BindX 是一个把 Hot Key（全局热键管理）和 Mouse（按键映射）统一到单进程、单托盘、单 UI 里的桌面工具。

当前项目保留两个子项目的独立运行能力，但日常主入口已经收敛为 BindX。

## 项目结构

```text
BindX/
├── app_hotkey_manager/   Hot Key 子项目（保留独立运行能力）
├── mouse_click/          Mouse 子项目（保留独立运行能力）
├── app.py                BindX 主入口
├── gui.py                主界面（customtkinter）
├── controller.py         引擎生命周期与 UI 状态管理
├── tray.py               BindX 托盘实现
├── trigger_engine.py     统一低层 Keyboard / Mouse Hook
├── config_proxy.py       子项目模块加载代理
├── shortcut_manager.py   桌面 / 开始菜单快捷方式创建
├── startup_manager.py    开机启动管理（HKCU\Run）
├── assets/               图标等资源
├── BindX.bat             唯一手动启动入口
├── requirements.txt
└── README.md
```

## 运行要求

- Windows 10 / 11
- Python 3.10+
- 依赖：

```bat
pip install -r requirements.txt
```

## 启动方式

### 推荐方式

双击：

```bat
BindX.bat
```

这是 BindX 的唯一手动启动入口。

### 命令行方式

也可以直接运行：

```bat
python app.py
```

或：

```bat
pythonw app.py
```

## UI 功能

BindX 使用左侧导航，包含三个页面：

1. 总览
2. 热键
3. 鼠标映射

### 总览页

总览页提供：

- Hot Key / Mouse 引擎状态
- 全部启动
- 全部停止
- 重置窗口
- 退出 BindX
- 字体大小档位切换
- 开机启动开关（登录后后台运行）
- 创建桌面图标
- 创建开始菜单图标

### 热键页

支持：

- 查看热键条目
- 新增 / 编辑 / 删除条目
- 双击切换启用状态
- 双击切换“启动未运行”
- 右键菜单操作

### 鼠标映射页

支持：

- 查看映射条目
- 新增 / 编辑 / 删除映射
- 双击切换启用状态
- 右键菜单操作

## 托盘行为

BindX 使用单托盘图标。

- 左键 / 双击：显示主窗口
- 右键：打开托盘菜单

关闭主窗口不会退出程序，而是最小化到托盘。

退出程序请使用：

- 托盘菜单“退出”
- 或总览页“退出 BindX”

## 开机启动

开机启动已经集成到 UI 中，不再依赖单独批处理脚本。

实现方式：

- 注册表位置：

```text
HKCU\Software\Microsoft\Windows\CurrentVersion\Run
```

行为：

- 打开开关后：登录 Windows 自动后台启动到托盘
- 关闭开关后：移除启动项

## 快捷方式与图标

快捷方式能力已经集成到 UI 中：

- 创建桌面图标
- 创建开始菜单图标

两者都会使用 `assets/` 中的图标资源。

说明：

- “创建开始菜单图标”是创建开始菜单入口
- 如果要固定到开始菜单/开始栏，请在系统开始菜单中手动固定

## 配置文件

BindX 会使用以下配置：

- Hot Key 配置：
  - `app_hotkey_manager/app_hotkey_config.json`
- Mouse 配置：
  - `mouse_click/config.json`
- BindX 自身状态：
  - `bindx_config.json`

`bindx_config.json` 当前用于保存：

- 热键引擎是否运行
- 鼠标引擎是否运行
- 窗口大小 / 最大化状态
- 字体大小档位
- 开机启动状态

## 重要提示

- 不要同时运行 BindX 和两个子项目的独立版本
- 否则可能出现：
  - 热键重复注册
  - Hook 重复挂载
  - 行为冲突

如果要单独运行子项目，请先退出 BindX。

## 子项目独立运行

### Hot Key

```bat
cd app_hotkey_manager
app_hotkey_manager.bat
```

或：

```bat
python app.py
```

### Mouse

```bat
cd mouse_click
mouse_remapper.bat
```

或：

```bat
python app.py
```
