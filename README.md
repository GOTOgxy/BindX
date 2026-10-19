# BindX

BindX 是一个面向 Windows 平台的高性能桌面快捷键呼出与底层键鼠输入增强工具。

采用 **Rust 原生后端 + Tauri v2 + 现代化 Fluent WebUI** 构建，以单一便携式 `.exe` 分发运行，**无需任何 Python、Conda 或第三方环境依赖**，启动即用、内存占用极低（约 20MB），并享受 GPU 硬件加速的 120Hz 丝滑窗口响应。

---

## 核心特性

- **应用呼出与切换引擎**：
  - 基于原生 Win32 `RegisterHotKey` 低功耗消息泵。
  - 支持一键呼出、激活、最小化或收起桌面客户端（如网易云音乐、Zotero、Termius 等）。
  - 支持精确匹配并切换指定 Edge / Chrome 浏览器标签页（如通义千问、ChatGPT、Gemini 等）。
  - 支持未运行时自动启动目标应用程序。

- **鼠标与键盘重映射**：
  - 基于低级系统钩子（`WH_MOUSE_LL` 与 `WH_KEYBOARD_LL`）。
  - 支持将鼠标侧键（X1 / X2 前进与后退键）一键重映射为组合键（如 `Ctrl+W`、`Alt+Tab` 等）。
  - 支持将按键组合映射为连击宏与输出键序列。
  - 自带修饰键隔离与注入事件防死循环防护。

- **WebDAV 云端多端同步**：
  - 支持坚果云（Nutstore）、Nextcloud、Alist、群晖 NAS 等任意标准 WebDAV 服务。
  - 包含实时“连接测试”、“备份上传配置”以及“从云端同步下载”。
  - 云端拉取后由 Rust 引擎**内存即时热重载**，规则秒级生效，无需重启软件。

- **软件版本检查与更新中心**：
  - 接入 GitHub Releases 自动版本检查。
  - 查看新版更新日志与特性变更。
  - 支持一键直链下载最新绿色发行版。

- **沉浸式现代无边框界面**：
  - 统一的 Windows 11 深色亚克力/玻璃拟态 Fluent 视觉风格。
  - 窗口平滑拉伸、缩放与最大化 0 延迟。
  - 系统托盘常驻菜单支持快捷呼出主界面与快速启停引擎。
  - 支持开机自启（自动写入 Windows 注册表）。

---

## 快速使用

### 直接运行

项目根目录已打包生成独立的二进制文件：
- 直接双击 **`bindx.exe`** 即可启动。
- 启动后主界面自动呼出，并在 Windows 右下角系统托盘常驻图标。

### 快捷键呼出 BindX 自身

默认全局快捷键：`Ctrl + Alt + V`，按下即可随时呼出或隐藏 BindX 主面板。

---

## 配置文件说明

本地配置存储于：
```text
data/bindx_config.json
```
- 配置包含通用设置、全局应用快捷键规则（`hotkeys`）、鼠标与按键映射规则（`mouse`）、WebDAV 云同步配置（`webdav`）以及更新设置（`updater`）。
- 每次在 UI 界面点击“保存所有修改”或从 WebDAV 同步时，配置会自动更新并热重载生效。

---

## 项目开发与构建

### 开发依赖

- **Node.js** >= 18
- **Rust** >= 1.80 (支持 `x86_64-pc-windows-msvc` 或 `x86_64-pc-windows-gnu`)
- Windows 10 / Windows 11 (内置 WebView2 运行时)

### 本地开发

```bash
# 1. 安装前端依赖
npm install

# 2. 启动前端 Vite 调试服务
npm run dev

# 3. 启动 Tauri 开发环境
npx tauri dev
```

### 生产打包

```bash
# 构建前端并编译 release 原生可执行文件
npx tauri build --no-bundle
```
构建成功后的可执行文件将生成于 `target/release/bindx.exe`。
