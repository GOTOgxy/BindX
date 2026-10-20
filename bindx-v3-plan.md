# BindX 需求规划文档

> 当前版本：v2.0.3 | 规划版本：v2.0.4（Bug 修复 + ESC）→ v2.1.0（分发架构升级）

---

## 一、Bug 修复和小需求（v2.0.4，优先落实）

### Bug 1：网页标签型应用行为错误

**问题描述：**
- 关闭网页标签后，按快捷键，若浏览器已关闭 → 启动浏览器（打开空白页），而非重新打开该网页标签
- 若浏览器开着 → 新开一个空白窗口
- UI 中缺少"程序未运行时自动启动"选项

**根本原因分析：**

1. **`launch_if_not_running` 被强制为 `false`**（`saveHotkeyModal` 中 L2269 写死）：
   ```js
   hotkeyModal.value.data.launch_if_not_running = false  // browser_tab 不给启动选项
   ```

2. **后端 `handle_hotkey_trigger` 没有为 `browser_tab` 实现"打开新标签"逻辑**（L292-304）：
   当找不到窗口时，目前逻辑只会 `launch_app(&target)` 即启动浏览器进程本身，而不是打开特定 URL 或空白标签并等待用户手动切。对 `browser_tab` 类型正确的"启动"语义应该是：
   - **如果浏览器本身没有运行** → 启动浏览器并附带 URL（如果用户配置了 url 字段）
   - **如果浏览器运行中但标签页不存在** → 在当前浏览器里打开新标签到目标 URL（如果有 url）或直接打开浏览器默认页
   - **如果没有配置 URL** → 仅告知用户（不乱开窗口）

**修复方案：**

**后端（`config.rs` + `hotkey.rs` + `win32.rs`）：**

1. 在 `HotkeyEntry` 增加 `tab_url: Option<String>` 字段：当 `target_type == browser_tab` 时，可选配置一个 URL，用于在标签不存在时重新打开。

2. 修改后端 `handle_hotkey_trigger`，对 `browser_tab` 分支：
   - 找到标签窗口 → toggle（现有逻辑，正常）
   - 找不到 → 若 `launch_if_not_running == true` 且配置了 `tab_url`：
     - 调用 `open_url_in_browser(url, exe_name)` 函数，使用 `ShellExecuteW` 或 `Command::new(browser_exe).arg(url)` 来打开 URL（会在已打开的浏览器里新建标签而不是新开浏览器窗口）
   - 找不到 → 若没有 URL 或 `launch_if_not_running == false`：啥都不做（不乱打开）

3. 实现 `open_url_in_browser(url: &str, browser_exe: Option<&str>)` in `win32.rs`：
   - 优先用 `ShellExecuteW(NULL, "open", url, ...)` → 系统默认处理，会在已打开的浏览器实例中新建标签
   - 这是最正确的方式，不用关心浏览器是否已经在运行

**前端（`App.vue`）：**

1. `browser_tab` 类型也显示"程序未运行时自动启动"选项（改名为"标签不存在时自动打开"）
2. 新增"目标网址（可选）"字段：`tab_url`，用于在标签不存在时用 ShellExecute 打开
3. 去掉 `saveHotkeyModal` 中强制设置 `launch_if_not_running = false` 的逻辑

---

### 需求 2：所有弹出框支持 ESC 退出

**方案：**
在 `onMounted` 中加一个全局 `keydown` 事件监听：

```js
window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    if (hotkeyModal.value.show) closeHotkeyModal()
    else if (remapModal.value.show) closeRemapModal()
  }
})
```

需要注意：录制状态中 `onHotkeyRecordKeyDown` 会 `e.stopPropagation()`，因此 ESC 在录制框内按下时会被录制为 `ESC` 按键，不会触发关闭弹窗（这是合理的）。仅在非录制状态下，ESC 关闭弹窗。

---

## 二、分发包架构升级（v2.1.0，大工程）

### 2.1 三级分发包定义

| 类型 | 文件名示例 | 定义 | 特点 |
|------|-----------|------|------|
| **Portable ZIP** | `bindx-v2.1.0-windows-x64.zip` | 便携压缩包 | 解压即用，仅含 `bindx.exe`，解压到任意目录 |
| **Portable EXE** | `bindx.exe` | 便携程序本体 | 单文件，直接下载运行，功能与 ZIP 内一致 |
| **Installer EXE** | `bindx-setup.exe` | 安装程序 | 创建安装目录、注册开始菜单、写卸载项、开机自启等标准安装行为 |

> **ZIP 内容**：只有一个 `bindx.exe`，不放 dll 也不放 readme（当前 GitHub Actions 多打包了 dll，需修改）

---

### 2.2 配置文件路径策略（两种模式兼容）

**核心原则：配置跟着用户走，不跟着程序走。**

```
便携模式（Portable Mode）：
  exe 目录下有 data/ 文件夹，或存在 data/bindx_config.json
  → 配置存放于 <exe目录>/data/bindx_config.json（现有逻辑，不变）

安装模式（Installed Mode）：
  exe 路径在标准安装目录（如 %LOCALAPPDATA%\Programs\BindX\）
  → 配置存放于 %APPDATA%\BindX\bindx_config.json（现有逻辑，不变）

检测逻辑（已存在于 config.rs，但需微调）：
  1. 检查 exe 同级目录是否有 data/ 文件夹 → 便携模式
  2. 否则检查 %APPDATA%\BindX\ → 安装模式
```

**这个逻辑目前代码中已经实现得比较正确，主要需要保证安装包不破坏它。**

---

### 2.3 安装程序设计

**技术方案**：使用 [Inno Setup](https://jrsoftware.org/isinfo.php)（免费、业界成熟、支持自定义）

**安装行为：**
- 安装目录：`%LOCALAPPDATA%\Programs\BindX\`（用户级安装，不需要管理员权限）
- 创建开始菜单快捷方式：`%APPDATA%\Microsoft\Windows\Start Menu\Programs\BindX.lnk`
- 可选创建桌面快捷方式
- 写入卸载注册表项（`HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\BindX`）
- 可选开机自启（勾选框，调用 BindX 内置注册表写入）
- 配置文件统一放 `%APPDATA%\BindX\`（与便携模式分开）

**卸载行为：**
- 删除 `%LOCALAPPDATA%\Programs\BindX\`
- 删除开始菜单快捷方式
- 删除开机自启注册表项
- 提示用户是否保留 `%APPDATA%\BindX\`（配置文件）

**GitHub Actions 调整：**
- 在构建完 `bindx.exe` 后，额外运行 `iscc` 编译 `.iss` 脚本生成 `bindx-setup.exe`
- 发布 3 个产物：`bindx.exe`、`bindx-windows-x64.zip`（只含 exe）、`bindx-setup.exe`

---

### 2.4 自动更新机制（兼容两种模式）

**挑战：便携模式和安装模式的更新方式必须不同。**

| 模式 | 更新行为 |
|------|---------|
| 便携模式 | 下载新版 `bindx.exe`，in-place 替换当前 exe（现有逻辑，继续用） |
| 安装模式 | 下载新版 `bindx-setup.exe`，静默运行 `/VERYSILENT /NORESTART`，Inno Setup 自动覆盖安装到原路径 |

**如何判断当前是哪种模式：**
- 新增 `detect_install_mode()` 函数
- 判断 exe 路径是否在 `%LOCALAPPDATA%\Programs\BindX\` 或卸载注册表中是否有 BindX 记录

**更新 UI（前端）：**
- 自动判断模式后显示对应提示文案：
  - 便携模式："一键自动更新（原地替换，保留配置）"
  - 安装模式："一键静默更新（覆盖安装，保留配置）"
- 下载进度条对两种模式都正常显示

---

## 三、实施顺序

### Phase 1：Bug + ESC（已完成，随 v2.1.0 一并发布）
- [x] 已分析根本原因
- [x] 后端：`HotkeyEntry` 增加 `tab_url` 字段
- [x] 后端：`win32.rs` 实现 `open_url_in_browser`
- [x] 后端：`hotkey.rs` 的 `browser_tab` 分支修复启动逻辑（顺带让 `launch_if_not_running` 在后端真正生效，serde 默认改为 true 以兼容旧配置）
- [x] 前端：`browser_tab` 显示"自动打开"开关 + URL 输入框
- [x] 前端：全局 ESC 关闭弹窗监听
- [x] cargo check / vite build 验证通过

### Phase 2：v2.1.0（分发架构，代码已完成）
- [x] 编写 Inno Setup 脚本（`installer/bindx.iss`，用户级安装、中文向导、静默升级自重启、卸载可选清理配置）
- [x] 修改 `release.yml` 添加安装包构建步骤、修复 ZIP 内容（只含 exe）
- [x] 后端：`detect_install_mode()` 检测运行模式（卸载注册表优先，默认安装目录兜底），更新机制分支（安装模式走静默覆盖安装）
- [x] 前端：更新 UI 适配两种模式（模式标识、按钮文案、setup 链接透传）
- [x] 版本号统一 bump 至 2.1.0（package.json / Cargo.toml / tauri.conf.json）
- [ ] 本地实测：便携更新流、安装流、静默升级流
- [ ] 打 tag `v2.1.0` 发布

---

> [!IMPORTANT]
> 三个待定问题已于 2026-10-20 由用户拍板：
> 1. 安装目录：`%LOCALAPPDATA%\Programs\BindX\`（用户级，无需管理员权限）✅
> 2. 安装界面：Inno Setup 默认现代向导 + BindX 名称/图标/中文语言 ✅
> 3. 发布节奏：Phase 1 + Phase 2 合并为 v2.1.0 单一版本发布 ✅
