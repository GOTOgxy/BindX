# BindX

BindX 是一个 Windows 桌面工具，用一个主程序统一管理两类能力：

- 全局热键：按一个快捷键显示、隐藏、启动或切换目标应用。
- 鼠标/键盘映射：把某个键盘组合或鼠标按键映射成另一个按键输出。

BindX 只有一个主入口、一个托盘图标、一个配置文件。`app_hotkey_manager` 和 `mouse_click` 目录现在只是业务模块，不再单独运行、不再单独维护 GUI 或配置。

## 适用场景

BindX 适合下面这类需求：

- 给常用应用绑定全局快捷键，比如 `Ctrl+Alt+Q` 控制网易云音乐显示/隐藏。
- 给网页应用绑定快捷键，比如 Gemini、ChatGPT、其他浏览器 App。
- 给带托盘的应用绑定快捷键，比如关闭窗口后仍在后台运行的应用。
- 把鼠标侧键映射成 `Ctrl+W`、`Alt+Tab` 等组合键。
- 希望所有配置集中在一个 JSON 文件里，必要时可以手工编辑。

BindX 的目标不是做窗口管理器，也不是完整替代系统快捷键工具。它主要解决一个具体问题：用户只想按一个热键，让不同类型的应用尽量表现成统一的“显示/隐藏/显示/隐藏”。

## 运行环境

- Windows 10 / Windows 11
- Python 3.10+
- 依赖：

```bat
pip install -r requirements.txt
```

`requirements.txt` 当前包含：

```text
keyboard
pynput
customtkinter
```

## 启动方式

推荐双击：

```bat
BindX.bat
```

也可以在项目目录运行：

```bat
python app.py
```

如果希望不显示控制台窗口，可以使用：

```bat
pythonw app.py
```

## 主界面

BindX 左侧有三个主要页面：

- 总览
- 热键
- 鼠标映射

### 总览

总览页用于管理 BindX 自身状态：

- 查看热键引擎和鼠标映射引擎是否运行。
- 一键启动全部引擎。
- 一键停止全部引擎。
- 重置窗口大小。
- 退出 BindX。
- 调整字体大小。
- 开启/关闭开机启动。
- 创建/删除桌面图标。
- 创建/删除开始菜单图标。

关闭主窗口不会退出程序，只会隐藏到托盘。真正退出请用总览页的“退出 BindX”或托盘菜单的“退出”。

### 热键

热键页用于管理“快捷键 -> 应用控制”。

常用操作：

- `添加`：新增一个热键绑定。
- `编辑`：编辑选中的绑定。
- `删除`：删除选中的绑定。
- `刷新`：刷新列表状态。
- 双击 `启用` 列：启用或禁用该条热键。
- 双击 `热键启动` 列：切换“目标未运行时，按热键是否启动它”。
- 右键条目：打开编辑/启用/删除菜单。

列表列含义：

| 列 | 含义 |
|---|---|
| 类型 | 目标类型，以及是否叠加托盘/多窗口特征 |
| 应用 | 显示名，优先使用用户填写的应用名 |
| 快捷键 | 注册到系统的热键 |
| 启用 | 该条规则是否启用 |
| 注册 | 当前是否成功注册到 Windows |
| 热键启动 | 目标未运行时是否尝试启动 |
| 安装路径 | 用于启动或推导进程名的 exe 路径 |

### 鼠标映射

鼠标映射页用于管理“输入 -> 输出”。

支持：

- 键盘组合映射，例如 `Ctrl+P -> Ctrl+Alt+W`。
- 鼠标按键映射，例如 `X1 -> Ctrl+W`。
- 每条映射单独启用/禁用。
- 录制输入键。
- 添加、编辑、删除映射。
- 按键检查，用来查看当前按下的键盘/鼠标按键名称和真实键值。

## 热键目标怎么填

添加或编辑热键时，BindX 会让你先选目标类型。目标类型决定下面哪些字段需要填写。

### 目标类型

| 类型 | 用途 |
|---|---|
| Win32 窗口 | 普通桌面应用，通常有一个主窗口 |
| Chromium 应用 | Electron、Chromium、WebView 类应用，例如 Termius、很多 AI 客户端 |
| 浏览器 App | 浏览器里的网页应用，例如 Gemini |
| UWP 应用 | 商店应用或系统应用 |
| 内置适配 | BindX 已经为它写好默认策略的应用 |

### 叠加特征

这些不是互斥类型，而是额外特征：

| 选项 | 含义 |
|---|---|
| 托盘隐藏 | 应用关闭窗口后可能还在托盘里，显示/隐藏不能只看窗口句柄 |
| 多窗口 | 应用可能有多个主窗口、多文档或多实例 |
| 热键启动 | 目标未运行时，按热键是否尝试启动它 |

### 可填写字段

| 字段 | 是否必填 | 说明 |
|---|---|---|
| 应用名 | 可选 | 用户给这个目标起的显示名，也可作为弱匹配线索 |
| 标题关键词 | 按类型决定 | 用窗口标题找目标，适合浏览器 App、UWP 或不知道进程名的应用 |
| 安装路径 | 可选 | exe 文件路径；填了以后 BindX 会自动推导进程名 |
| 进程名 | 兜底 | 例如 `QQMusic.exe`；用户通常不需要填，除非没有安装路径 |
| 浏览器 | 浏览器 App 需要 | 当前支持 Edge 和 Chrome |

路径在 UI 和配置里统一显示为 `/`，例如：

```text
C:/Program Files/Zotero/zotero.exe
```

Windows 可以正常识别这种路径。

## 最小填写规则

BindX 的填写规则尽量少要求用户懂技术细节。

### 内置适配

只需要选择适配应用。

当前内置适配：

- 网易云音乐
- Zotero
- Termius
- BindX

选择后 BindX 会自动设置：

- 应用名
- 进程名
- 常见安装路径。如果本机路径存在才自动填，不存在就留空。
- 是否托盘隐藏
- 是否多窗口
- 是否热键启动

### 浏览器 App

最少填写：

- 标题关键词

可选填写：

- 应用名
- 浏览器类型

例子：

| 字段 | 示例 |
|---|---|
| 应用名 | Gemini |
| 浏览器 | Edge |
| 标题关键词 | Google Gemini |

浏览器 App 的本质不是控制整个浏览器，而是找“标题匹配的浏览器窗口”。如果多个浏览器窗口、多个 profile 或多个标签页标题很像，匹配可能不稳定。

### Win32 窗口 / Chromium 应用

至少填写下面任意一个：

- 应用名
- 标题关键词
- 安装路径
- 进程名

推荐优先填：

1. 应用名
2. 安装路径
3. 标题关键词

如果填了安装路径，BindX 会自动从路径推导进程名，不需要再手动填 `xxx.exe`。

### UWP 应用

UWP 应用通常不适合填安装路径。

推荐填写：

- 应用名
- 标题关键词

BindX 会尽量通过窗口标题找它。由于 UWP 的进程和窗口关系不一定稳定，显示/隐藏的可靠性取决于具体应用。

## 热键控制的核心逻辑

BindX 期望提供统一体验：

```text
按热键 -> 显示
再按 -> 隐藏
再按 -> 显示
再按 -> 隐藏
```

但 Windows 应用的窗口模型并不统一，所以 BindX 内部会按目标类型和特征选择不同策略。

### 1. 进程定位

如果配置里有进程名，BindX 会枚举进程。

进程名来源：

1. 用户填写的进程名。
2. 从安装路径自动推导出来的文件名。
3. 内置适配自带的进程名。

如果没有进程名，BindX 会退到标题匹配：

1. 优先使用标题关键词。
2. 没有标题关键词时，尝试使用应用名。

没有进程名时，BindX 不会乱启动未知应用。

### 2. 窗口选择

找到进程后，BindX 会枚举它的窗口，并尽量排除这些窗口：

- IME 输入法窗口。
- 无标题的 Chromium 辅助窗口。
- 截图、overlay、devtools 等非主窗口。
- 不可见或面积很小的窗口。

然后按标题、窗口类名、可见性、窗口面积、上次成功控制的窗口等信息排序，选择最像主窗口的那个。

### 3. 显示

显示目标时，BindX 会尝试：

- 恢复最小化窗口。
- 显示隐藏窗口。
- 将窗口切到前台。
- 对部分单实例/托盘应用，必要时重新启动同一 exe，让应用自己弹出主窗口。

### 4. 隐藏

隐藏目标时，BindX 会按应用特征选择：

- 普通最小化。
- 隐藏窗口。
- 托盘隐藏。
- 从任务栏临时移除。

不同应用对这些 API 的响应不一样，所以内置适配会为具体应用设置更合适的策略。

## 已知约束

Windows 上“显示/隐藏一个应用”不是单一标准行为。下面这些情况不能做到完全确定：

- 应用有多个主窗口。
- 应用关闭窗口后实际进入托盘。
- Electron/Chromium 应用存在无标题辅助窗口。
- 浏览器 App 有多个窗口、多个 profile、多个标题相似的标签页。
- UWP 应用没有稳定的 exe 到窗口的一一对应关系。
- 某些应用拒绝外部进程抢前台。
- 某些应用隐藏后必须通过自身托盘逻辑恢复。

BindX 的原则是：

- 用户不需要填写窗口句柄、窗口类名、策略名。
- 用户最多填写应用名、标题关键词、安装路径、进程名。
- 能用安装路径推导的信息不要求用户重复填写。
- 内置适配负责把已知应用调到最合理的默认行为。
- 找不到目标时不做危险操作，不乱关闭、不乱杀进程。

## 鼠标/键盘映射逻辑

鼠标映射由统一底层 Hook 处理。

支持两类规则：

- 键盘规则：按下某个键盘组合后输出另一个组合。
- 鼠标规则：按下鼠标按键后输出另一个组合。

示例：

```text
Ctrl+P -> Ctrl+Alt+W
Mouse X1 -> Ctrl+W
```

注意：

- 输出期间会抑制触发键的释放事件，避免原始输入穿透。
- 映射只在 BindX 的 Mouse 引擎运行时生效。
- 某些管理员权限应用可能需要 BindX 也以管理员权限运行才能拦截输入。

## 托盘与开机启动

BindX 常驻托盘。

托盘操作：

- 左键/双击：显示主窗口。
- 右键：打开托盘菜单。

开机启动在总览页设置，使用当前用户注册表：

```text
HKCU/Software/Microsoft/Windows/CurrentVersion/Run
```

开启后，登录 Windows 时 BindX 会后台启动到托盘。

## 配置文件

所有配置集中在项目根目录：

```text
bindx_config.json
```

顶层结构：

```json
{
  "app": {},
  "hotkeys": {},
  "mouse": {}
}
```

### app

保存 BindX 自身状态：

- 热键引擎是否运行。
- 鼠标引擎是否运行。
- 窗口大小。
- 是否最大化。
- 字体档位。
- 开机启动状态。

### hotkeys

保存热键条目。

示例：

```json
{
  "app": "generic",
  "name": "千问",
  "target_type": "chromium",
  "tray_aware": true,
  "multi_window": false,
  "hotkey": "CTRL+ALT+A",
  "launch_if_not_running": true,
  "install_path": "C:/Users/gxy/AppData/Local/Programs/QianwenApp/qianwen.exe",
  "exe_name": "qianwen.exe",
  "title_keyword": "千问",
  "enabled": true
}
```

常见字段：

| 字段 | 说明 |
|---|---|
| app | 内部应用类型：`generic`、`web_app`、`cloudmusic`、`zotero`、`termius`、`hot_key_manager` |
| name | 用户显示名 |
| target_type | UI 目标类型：`win32`、`chromium`、`browser_tab`、`uwp`、`builtin` |
| tray_aware | 是否按托盘隐藏类应用处理 |
| multi_window | 是否按多窗口目标看待 |
| hotkey | 快捷键 |
| launch_if_not_running | 目标未运行时是否启动 |
| install_path | 安装路径 |
| exe_name | 进程名，可从安装路径推导 |
| title_keyword | 标题关键词 |
| enabled | 是否启用 |

### mouse

保存键盘/鼠标映射。

示例：

```json
{
  "mappings": [
    {
      "trigger": ["ctrl", "p"],
      "output": ["ctrl", "alt", "w"],
      "description": "Ctrl+P -> Ctrl+Alt+W",
      "enabled": true
    }
  ],
  "mouse_mappings": [
    {
      "button": "x1",
      "output": ["ctrl", "w"],
      "description": "鼠标侧键X1 -> Ctrl+W",
      "enabled": true
    }
  ]
}
```

## 项目结构

```text
BindX/
├── app.py                  主入口
├── BindX.bat               手动启动入口
├── gui.py                  customtkinter 主界面
├── controller.py           引擎生命周期与 UI 状态管理
├── config_store.py         集中 JSON 配置读写与旧配置迁移
├── config_proxy.py         子模块加载代理
├── trigger_engine.py       统一 Keyboard/Mouse Hook
├── tray.py                 托盘封装
├── shortcut_manager.py     桌面/开始菜单快捷方式
├── startup_manager.py      开机启动管理
├── app_hotkey_manager/     热键业务逻辑
├── mouse_click/            鼠标/键盘映射业务逻辑
├── assets/                 图标资源
├── requirements.txt
└── README.md
```

## 核心模块

| 模块 | 作用 |
|---|---|
| `app.py` | 创建 BindX 主应用 |
| `gui.py` | 主 UI、热键页、鼠标映射页、对话框 |
| `controller.py` | 管理热键引擎、鼠标引擎、配置保存 |
| `config_store.py` | 读写 `bindx_config.json`，迁移旧配置 |
| `trigger_engine.py` | 底层键盘/鼠标 Hook，负责映射触发 |
| `app_hotkey_manager/hotkey_manager.py` | 热键注册、窗口查找、显示/隐藏/启动逻辑 |
| `mouse_click/engine.py` | 鼠标/键盘映射执行逻辑 |

## 运行约束

- 不要同时运行多个 BindX 实例。
- 不要再单独运行 `app_hotkey_manager` 或 `mouse_click` 目录里的旧入口；这些入口已经移除。
- 全局热键注册可能被系统或其他软件占用。注册失败时，热键页的“注册”列会显示失败。
- 如果目标应用以管理员权限运行，BindX 可能也需要管理员权限才能稳定控制它。
- 低层 Hook 和模拟输入可能被安全软件拦截。

## 开发检查

修改 Python 代码后，至少运行：

```bat
python -m py_compile gui.py app_hotkey_manager\hotkey_manager.py trigger_engine.py config_store.py controller.py app.py tray.py
```

如果改了热键行为，建议手动验证：

- 普通 Win32 应用显示/隐藏。
- 托盘应用关闭窗口后再用热键唤醒。
- Chromium/Electron 应用是否选中真正主窗口。
- 浏览器 App 是否匹配到正确窗口。
- 鼠标映射是否触发且原始输入没有穿透。
