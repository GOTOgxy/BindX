# BindX 手册

> 适用版本：v3.0.0+。本文档描述 BindX 各子系统的**实际行为与实现逻辑**，与代码同步维护。
> 章节：① 快捷键目标类型 ② 按键映射 ③ 配置读取与云同步 ④ 安装与更新 ⑤ 开发与打包编译

---

## 一、快捷键目标类型：网页应用 / 桌面客户端 / 内置应用

每条快捷键规则（`hotkeys.entries[]`）由 `target_type` 决定其行为族：

| 类型 | `target_type` | 识别元素 | 典型场景 |
|------|--------------|---------|---------|
| 桌面客户端 | `win32`（默认） | 进程名 `exe_name` / 安装路径 `install_path` | 网易云音乐、VS Code |
| 内置应用 | `builtin`（UI 已并入 win32） | 预设名 → 进程名映射表 | 微信、Termius、Zotero |
| 网页应用 | `browser_tab` | 浏览器进程 + 标签标题关键字 `title_keyword` | 千问、Gemini、ChatGPT |

### 1.1 通用条目字段

| 字段 | 含义 |
|------|------|
| `hotkey` | 全局热键组合，如 `CTRL+ALT+A`（系统级 `RegisterHotKey`） |
| `enabled` | 是否注册该热键 |
| `launch_if_not_running` | 找不到窗口时是否允许"启动/重开"（serde 默认 `true` 兼容旧配置） |
| `install_path` / `exe_name` | 显式路径 / 进程名；留空时自动解析 |
| `_runtime_profile.hide_behavior` | 命中窗口后的切换行为：`minimize`（默认）/ `tray` / `hide` |
| `title_keyword` | 窗口标题关键字（网页应用必填；桌面客户端可选作窗口过滤） |
| `tab_url` / `tab_mode` | 仅网页应用：重开网址 / 重开形态（`tab` 或 `app_window`） |

### 1.2 统一触发流程

```
按下热键
 ├─ 目标是 BindX 自身 → 切换主窗口显示/隐藏
 └─ 查找窗口（exe_name 进程 + title_keyword 标题过滤）
     ├─ 找到 → 按 hide_behavior 切换（最小化/托盘/隐藏 ↔ 激活置顶）
     └─ 未找到 → launch_if_not_running == false？ → 什么都不做
                 └─ true → 按目标类型启动（见下）
```

- **桌面客户端**：`install_path` 优先；否则 `exe_name` 依次按 *运行中进程路径 → App Paths 注册表 → 卸载注册表（DisplayName 前缀匹配 → DisplayIcon / InstallLocation）→ 常见安装目录（含 `%LOCALAPPDATA%\Programs` 一级子目录，覆盖 Termius 等按用户安装的程序）* 解析，再 `launch_app`。
- **内置应用**：未填 `exe_name` 时按预设表映射（cloudmusic→`cloudmusic.exe`、wechat→`WeChat.exe`、termius、zotero、vscode→`Code.exe`、terminal→`wt.exe`）。
- **网页应用**：见 1.3。

### 1.3 网页应用：行为与重开逻辑

**命中判定**：在选定浏览器进程（`auto` = 所有浏览器 / `msedge.exe` / `chrome.exe` / 自定义）中查找标题包含 `title_keyword` 的窗口。浏览器把活动标签标题显示在窗口标题上，因此"标签"在 OS 层就是一个可匹配窗口。

**未命中时的重开**（需 `launch_if_not_running = true`；`tab_url` 可选——填了走网址链，留空时仅按名称亲和尝试唤起已安装应用，两者皆无则保持安静）：

| 顺序 | 形态 | 动作 | 结果 |
|------|------|------|------|
| 1 | `app_window` 且匹配到已安装应用 | `explorer.exe shell:AppsFolder\<AUMID>`（与开始菜单磁贴同一条 OS 路径；旧版浏览器回退 `--app-id`） | 完整安装身份窗口（应用菜单/固定任务栏等） |
| 2 | `app_window` | `<browser> --app=<url>` | 独立 app 窗口（无标签栏地址栏） |
| 3 | 上述失败或浏览器不可解析 | `ShellExecuteW("open", url)` | 系统默认浏览器新开标签（复用已运行实例） |
| — | `tab` | 同 3（或带指定浏览器 exe 参数） | 浏览器标签页 |

未配置 `tab_url` 时**保持安静**——绝不回退到"启动一个空白浏览器窗口"的旧 bug 行为。

**已安装网页应用检测**（决定顺序 1 能否生效）：Edge/Chrome 不对外暴露完整的静态安装清单（profile JSON、卸载注册表、AUMID 均已实测无 URL↔id 映射），因此采用多源融合 + 机器本地学习：

| 源 | 提供 | 覆盖 |
|----|------|------|
| **打开中的 app 窗口的 AppUserModelID**（`SHGetPropertyStoreForWindow` + `PKEY_AppUserModel_ID`，形如 `chatgpt.com-…!App`）与窗口标题 | OS 级启动钥匙 + 显示名 | 该 app 窗口开过一次即被学会并缓存 |
| 本机缓存 `%LOCALAPPDATA%\BindX\webapps_cache.json` | 学习结果持久化 | 窗口关闭后仍认识；**不属于配置、不参与云同步** |
| 浏览器 profile 注册目录 `<profile>\Web Applications\Manifest Resources\<id>` | id + 浏览器族 + profile | 所有装过的应用（与快捷方式/自启无关） |
| 应用显示名 | `Web Applications\_crx__<id>\<名称>.ico` 文件名 | 名称匹配用 |
| 开始菜单/桌面快捷方式参数 | `--app-id` → `--app-url` 配对 | 有快捷方式的应用（如设过开机自启） |

**匹配规则**（`find_installed_web_app_for_url`）：
1. **URL 配对**：条目 `tab_url` 与某应用的 `app-url` origin（`scheme://host[:port]`）相等，或归一化后互为前缀（浏览器记录的 URL 常带启动查询参数）；
2. **名称亲和**回退：条目标题关键字/显示名 与应用显示名双向包含（如「千问」⊂「千问-阿里 AI 助手」）。

编辑弹窗中的"已安装应用检测(实时)"行与触发时使用**同一套**匹配代码，所见即所得。检测只读本机公开契约、结果不写配置，云同步到其他设备后各自检测，人人可用。

> 边界与模型修正：Chromium 采用**交接模型**——浏览器已运行时，新启的 app 进程把窗口交给主进程后自己退出，因此**进程命令行永远读不到 `--app-id`**（早期 harvest 方案据此失效）。真正稳定的契约是**窗口级**的：AppUserModelID（OS 注册身份，开始菜单无 .lnk 磁贴即由此而来）+ 窗口标题。故 harvest 改为枚举打开中的浏览器窗口读取 AUMID/标题，缓存后即可在窗口关闭后继续匹配与唤起。Edge/Chrome 对既无快捷方式、也从未打开过的已安装应用只在磁盘留匿名 id 与图标 PNG，此类应用在其 app 窗口首次打开时被学会。

### 1.4 界面约定

- 所有编辑弹窗（快捷键/按键映射）在**非录制状态**下按 `ESC` 关闭；录制中 `ESC` 被录制为按键（捕获监听处于 capture 阶段并 `stopPropagation`）。
- 校验警告（如开关开启但未填网址）以 toast 提示，层级高于模态框，填写页内直接可见。
- 版本号各处（标题栏/概览/更新页）统一读取后端 `CARGO_PKG_VERSION`，不再硬编码。

### 1.5 热键引擎内部与生命周期（`engine/hotkey.rs`）

- `start` 起独立线程：对每条 `enabled` 条目 `RegisterHotKey(HWND::default(), id, mods | MOD_NOREPEAT, vk)`（线程级热键，`MOD_NOREPEAT` 抑制按住重复触发）；线程内 `GetMessageW` 消息泵，收到 `WM_HOTKEY` 按 id 找到条目 → `handle_hotkey_trigger`（即 1.2 流程）。
- **热重载**：`reload` 存新规则后 `PostThreadMessageW` 投递 `WM_HOTKEY_RELOAD`（`WM_USER+101`）；引擎线程收到后整体反注册再注册，**不重建线程、不丢消息泵**。
- **暂停/恢复**：`pause`/`resume` 投递 `WM_HOTKEY_PAUSE`/`WM_HOTKEY_RESUME`。录制开始时 `set_recording_state(true)` 同时暂停热键引擎与 remap 钩子，保证录制捕获原始按键；录制结束恢复。
- **停止**：投递 `WM_QUIT` 退出消息循环并反注册。
- **自呼出**：目标是 BindX 自身的条目不走窗口查找，直接调 `toggle_window_sender` 回调（lib.rs 注册：主窗口可见则隐藏，否则 show + unminimize + focus）。

### 1.6 局部流程：新增/修改快捷键端到端

```
模态框（录制/手输热键、目标类型、字段）
 → 保存校验（热键非空；browser_tab 必填标题关键字）
 → 写入 config.hotkeys.entries
 → update_config 命令：save_config 落盘 → set_autostart 同步注册表
                       → hotkey_engine.reload / remap_engine 重载
 → 引擎线程 WM_HOTKEY_RELOAD 反注册+注册 → 全局立即生效
```

---

## 二、按键映射

将"触发组合"（键盘键 + 鼠标侧键）在系统层拦截并替换为"输出序列"。

### 2.1 规则结构

```jsonc
{ "trigger": ["X1", "CTRL"],   // 触发组合：全部按下才命中
  "output": ["CTRL", "C"],     // 输出的按键序列
  "description": "侧键复制",
  "enabled": true }
```

- 鼠标侧键别名：`x1`/`x2` = `xbutton1`/`xbutton2` = `mouse4`/`mouse5` = 后退键/前进键 = 侧键1/侧键2。
- 旧版 `mouse_mappings`（单侧键规则）在加载时自动迁移进统一 `mappings`。

### 2.2 引擎实现（`engine/remap.rs`）

- 独立线程安装 `WH_KEYBOARD_LL` + `WH_MOUSE_LL` 低级钩子，线程内消息循环驱动；`reload` 热更新规则、`stop` 经 `WM_QUIT` 退出并卸载钩子。
- **键盘命中**：`WM_KEYDOWN/WM_SYSKEYDOWN` 时校验 trigger 全键按下（当前键 + 其余键 `GetAsyncKeyState`），命中返回 `1` 拦截原键。
- **鼠标命中**：`WM_XBUTTONDOWN` 取 `mouseData` 高字识别 X1/X2，同样校验组合中其余键。
- **输出**：独立线程 `send_key_sequence`——顺序按下、逆序抬起；每个合成输入带 `dwExtraInfo = BINDX_EXTRA_INFO` 自标记，钩子见到自标记直接放行，**防止自我触发环路**。
- **录制隔离**：UI 进入录制时 `set_recording_paused(true)` 暂停钩子拦截，保证录制能捕获原始按键（含 ESC）。
- **录制交互**：按下录制按钮后，捕获由**窗口级 capture 阶段监听**完成——窗口内任意位置按键即录（触发键另含鼠标侧键，走窗口级 `pointerdown` 捕获），无需先点击特定区域；未录制时输入框正常手动输入。编辑区为两行布局（标签+按钮行、输入框行）。
- 配置项 `app.output_delay_ms`、`app.restore_held_modifiers` 目前在 UI 暴露但后端尚未消费（保留项）。

### 2.3 局部流程：新增映射端到端

```
点"录制" → 窗口级 capture 监听（keydown / pointerdown，X1/X2 按 button 映射）
 → trigger / output 数组 → 保存 → update_config → remap_engine.start/reload
 → 钩子线程读取新规则 → 全局立即生效
输出执行：命中 → 独立线程 send_key_sequence（顺序按下、逆序抬起、自标记防环）
```

---

## 三、配置读取与云同步

### 3.1 配置路径解析（便携/安装双模兼容）

按序取第一个存在者：

1. 当前工作目录 `data/bindx_config.json`
2. **exe 同级 `data/bindx_config.json`，或 exe 旁存在 `data/` 目录** → 便携模式
3. `%APPDATA%\BindX\bindx_config.json` → 安装模式
4. 当前工作目录 `bindx_config.json`（兜底）

> 配置跟着用户走，不跟着程序走：安装包**不会**创建 `data/` 目录，因此安装模式天然落到 `%APPDATA%`；便携包解压即用 `data/`。

### 3.2 加载与保存

- 加载：serde 反序列化，缺失字段走 `#[serde(default)]`；两项 legacy 迁移——`mouse_mappings` 并入 `mappings`、`remote_filename` 的 `bindx/bindx_config.json` 归一为 `bindx`。
- 保存：pretty JSON 全量写回；`update_config` 命令落盘后**同步开机自启注册表**并按 `hotkey_running`/`mouse_running` 热重载双引擎。

### 3.3 WebDAV 云同步

- 远端文件名**固定**为 `bindx_config.json`；`remote_filename` 字段实际语义是**远端目录**（默认 `bindx`；填成含文件名的旧值会被归一）。
- 上传：逐层 `MKCOL` 建目录 → `PUT`；下载：`GET` → 解析 → **保留本地当前 WebDAV 凭据**（防止云端旧配置洗掉凭据）→ 写回本地磁盘并热生效。
- 连接测试：`PROPFIND`(Depth:0)，失败回退 `GET`；401/403/404 分别给出认证/权限/路径错误提示。

### 3.4 机器本地数据（非配置）

`%LOCALAPPDATA%\BindX\webapps_cache.json`（已安装网页应用学习缓存）等机器本地状态**不进入配置文件、不参与云同步**，换机自动重建。

### 3.5 启动与常驻流程（`lib.rs::run`）

```
panic hook（bindx_error.log；过滤 0x800700AA 资源占用噪声）
 → load_config（含 legacy 迁移）→ AppState（双引擎 Arc）
 → setup：
    清理上轮更新残留（bindx.exe.old、bindx_update.tmp）
    → 按 hotkey_running / mouse_running 启动双引擎
    → 托盘菜单（显示主窗口 / 检查更新... / 退出 BindX）
    → 注册热键引擎自呼出回调
    → 显示主窗口；关闭按钮 prevent_close + hide（隐藏到托盘，不退出）
```

`webdav.auto_sync_on_startup` 目前在 UI 暴露但启动流程尚未消费（保留项）。

---

## 四、安装与更新

### 4.1 三种分发产物

| 产物 | 形态 | 说明 |
|------|------|------|
| `bindx.exe` | 便携本体 | 单文件（MSVC 构建），放哪用哪 |
| `bindx-windows-x64-portable.zip` | 便携压缩包 | 解压后**仅含** `bindx.exe` |
| `bindx-setup.exe` | 安装程序 | Inno Setup（`installer/bindx.iss`），用户级安装，无 UAC |

### 4.2 运行模式检测（`detect_install_mode`）

1. 卸载注册表 `HKCU\...\Uninstall\BindX_is1` 的 `InstallLocation` == exe 目录 → 安装模式（权威）；
2. exe 目录 == `%LOCALAPPDATA%\Programs\BindX` → 安装模式；
3. 否则便携模式。

### 4.3 安装程序行为

- 默认目录 `%LOCALAPPDATA%\Programs\BindX`（`PrivilegesRequired=lowest`）；现代向导 + 中文语言 + BindX 图标。
- 可选任务：桌面快捷方式、开机自启（写 `HKCU\...\Run`，`uninsdeletevalue`；静默升级不触碰该项）。
- 安装前 `taskkill` 运行中的 BindX；**静默升级完成后自动重启应用**，用户无感。
- 卸载：移除文件/快捷方式/自启项；交互卸载询问是否删除 `%APPDATA%\BindX` 配置，静默卸载不删用户数据。

### 4.4 自更新流程

检查：GitHub Releases latest；`download_url` 资产优先级 `bindx.exe` > 任意 `.exe` > `.zip`；`setup_download_url` 单独取 `bindx-setup.exe`。

| 模式 | 更新动作 | 重启方式 |
|------|---------|---------|
| 便携 | 下载新 exe → 现 exe 改名 `.old` → 替换（失败自动回滚） | UI"立即重启" |
| 安装 | 下载 `bindx-setup.exe` 到临时目录 → `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART` 静默覆盖 → 应用自动退出交棒 | 安装程序自动重启应用 |

**不变量**：更新不改变配置内容与位置、安装路径、程序名、快捷方式；安装模式 release 无 setup 资产时自动回退便携式原地替换。

### 4.5 发布流水线

推送 `v*` tag → `release.yml`：MSVC 构建 → 打包 exe-only zip → `iscc` 编译 `.iss`（版本号取自 `tauri.conf.json`）→ 发布三产物。

### 4.6 局部流程：更新端到端

```
检查(check_software_update) → GitHub latest → semver 比较 → 资产选择
UI 状态机：idle → downloading（update-progress 事件：percent/message）
         → applying → done（便携：等待"立即重启"）/ error（重试或手动下载）
便携：下载 exe → 现 exe 改名 .old → 替换（失败回滚）→ 用户点重启 → 下次启动清理 .old
安装：下载 setup 到临时目录 → 分离静默启动 → 应用 exit 交棒 → 安装程序自动重启应用
```

---

## 五、开发与打包编译

### 5.1 依赖与本地开发

- Node.js ≥ 18；Rust ≥ 1.80（`x86_64-pc-windows-msvc` 或 `-gnu`）；Windows 10/11（内置 WebView2）。
- `npm install` → `npm run dev` → `npx tauri dev`。

### 5.2 空格路径陷阱（重要）

仓库路径含空格时（如 `D:\Program Files\...`）：

- **GNU 工具链**：tauri-winres 调 `windres` 时资源路径未转义 → `cc1.exe: fatal error: Files\app\...`。解法：`CARGO_TARGET_DIR=D:/bindx-target npx tauri build --no-bundle`（产物目录无空格即可）。
- **Git Bash 里验证 MSVC**：coreutils 的 `link` 遮蔽 MSVC `link.exe` → 需在 vcvars 终端中进行。
- **管道掩码**：`cargo check | tail` 的退出码是 `tail` 的；验证请单独捕获日志并打印 `EXIT=$?`。
- CI 统一 MSVC，不受影响。

### 5.3 GNU 与 MSVC 产物差异

GNU 构建的 exe 需 `WebView2Loader.dll` 傍身；MSVC 构建为真·单文件（分发产物一律 MSVC）。

### 5.4 打包与版本

- 发布构建：`npx tauri build --no-bundle`，产物 `target/release/bindx.exe`（或 `CARGO_TARGET_DIR` 指定处）。
- 版本号三处同步：`package.json`、`src-tauri/Cargo.toml`、`src-tauri/tauri.conf.json`；UI 显示读 `CARGO_PKG_VERSION`。
- 安装脚本版本由 CI 以 `/DMyAppVersion=` 注入（本地默认值仅作兜底）。

### 5.5 辅助工具

- `cargo run --release --example scan_apps`：打印本机已安装网页应用检测明细（GNU 构建需把 `WebView2Loader.dll` 放到 example exe 旁）。
