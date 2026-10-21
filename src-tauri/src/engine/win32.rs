use std::ffi::OsString;
use std::os::windows::ffi::OsStringExt;
use std::path::Path;
use std::process::Command;
use windows::Win32::Foundation::{CloseHandle, BOOL, HWND, LPARAM, MAX_PATH};
use windows::Win32::Graphics::Dwm::{DwmGetWindowAttribute, DWMWA_CLOAKED};
use windows::Win32::System::Diagnostics::ToolHelp::{
    CreateToolhelp32Snapshot, Process32FirstW, Process32NextW, PROCESSENTRY32W, TH32CS_SNAPPROCESS,
};
use windows::Win32::System::ProcessStatus::GetModuleFileNameExW;
use windows::Win32::System::Registry::{
    RegCloseKey, RegOpenKeyExW, RegQueryValueExW, HKEY, HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE,
    KEY_READ, REG_SZ,
};
use windows::Win32::System::Threading::{
    AttachThreadInput, GetCurrentThreadId, OpenProcess, QueryFullProcessImageNameW,
    PROCESS_NAME_FORMAT, PROCESS_QUERY_LIMITED_INFORMATION, PROCESS_VM_READ,
};

// ntdll is not exposed by the windows crate without Wdk features; declare the
// one call we need. ProcessCommandLineInformation = 60.
#[link(name = "ntdll")]
extern "system" {
    fn NtQueryInformationProcess(
        process: isize,
        infoclass: u32,
        info: *mut std::ffi::c_void,
        infolen: u32,
        retlen: *mut u32,
    ) -> i32;
}
const PROCESS_COMMAND_LINE_INFORMATION: u32 = 60;
use windows::Win32::UI::Input::KeyboardAndMouse::{
    SendInput, INPUT, INPUT_0, INPUT_KEYBOARD, KEYBDINPUT, KEYEVENTF_KEYUP,
    VIRTUAL_KEY, VK_BACK, VK_CONTROL, VK_DELETE, VK_DOWN, VK_ESCAPE, VK_F1, VK_F10, VK_F11,
    VK_F12, VK_F2, VK_F3, VK_F4, VK_F5, VK_F6, VK_F7, VK_F8, VK_F9, VK_LEFT, VK_LWIN, VK_MENU,
    VK_RETURN, VK_RIGHT, VK_SHIFT, VK_SPACE, VK_TAB, VK_UP,
};
use serde::{Deserialize, Serialize};
use windows::Win32::UI::Shell::ShellExecuteW;
use windows::Win32::UI::WindowsAndMessaging::{
    EnumWindows, GetClassNameW, GetForegroundWindow, GetWindowLongW, GetWindowTextLengthW,
    GetWindowTextW, GetWindowThreadProcessId, IsIconic, IsWindowVisible, SetForegroundWindow,
    SetWindowPos, ShowWindow, GWL_EXSTYLE, HWND_NOTOPMOST, HWND_TOPMOST, SWP_NOMOVE, SWP_NOSIZE,
    SWP_SHOWWINDOW, SW_HIDE, SW_MINIMIZE, SW_RESTORE, SW_SHOW, WS_EX_TOOLWINDOW,
};

pub const BINDX_EXTRA_INFO: usize = 0x42494E58;

pub fn get_vk_code(key: &str) -> Option<VIRTUAL_KEY> {
    let lower = key.trim().to_lowercase();
    match lower.as_str() {
        "ctrl" | "control" => Some(VK_CONTROL),
        "alt" | "menu" => Some(VK_MENU),
        "shift" => Some(VK_SHIFT),
        "win" | "windows" | "super" => Some(VK_LWIN),
        "enter" | "return" => Some(VK_RETURN),
        "space" => Some(VK_SPACE),
        "tab" => Some(VK_TAB),
        "esc" | "escape" => Some(VK_ESCAPE),
        "backspace" => Some(VK_BACK),
        "delete" | "del" => Some(VK_DELETE),
        "up" => Some(VK_UP),
        "down" => Some(VK_DOWN),
        "left" => Some(VK_LEFT),
        "right" => Some(VK_RIGHT),
        "f1" => Some(VK_F1),
        "f2" => Some(VK_F2),
        "f3" => Some(VK_F3),
        "f4" => Some(VK_F4),
        "f5" => Some(VK_F5),
        "f6" => Some(VK_F6),
        "f7" => Some(VK_F7),
        "f8" => Some(VK_F8),
        "f9" => Some(VK_F9),
        "f10" => Some(VK_F10),
        "f11" => Some(VK_F11),
        "f12" => Some(VK_F12),
        "x1" | "xbutton1" | "mouse4" | "后退键" | "侧键1" => Some(VIRTUAL_KEY(0x05)),
        "x2" | "xbutton2" | "mouse5" | "前进键" | "侧键2" => Some(VIRTUAL_KEY(0x06)),
        "mbutton" | "mouse3" | "中键" => Some(VIRTUAL_KEY(0x04)),
        k if k.len() == 1 => {
            let ch = k.chars().next()?.to_ascii_uppercase();
            if ch.is_ascii_alphanumeric() {
                Some(VIRTUAL_KEY(ch as u16))
            } else {
                None
            }
        }
        _ => None,
    }
}

pub fn send_key_sequence(keys: &[String]) {
    let vks: Vec<VIRTUAL_KEY> = keys.iter().filter_map(|k| get_vk_code(k)).collect();
    if vks.is_empty() {
        return;
    }

    let mut inputs: Vec<INPUT> = Vec::new();

    // 1. Key down for all in sequence
    for &vk in &vks {
        inputs.push(INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: vk,
                    wScan: 0,
                    dwFlags: windows::Win32::UI::Input::KeyboardAndMouse::KEYBD_EVENT_FLAGS(0),
                    time: 0,
                    dwExtraInfo: BINDX_EXTRA_INFO,
                },
            },
        });
    }

    // 2. Key up for all in reverse
    for &vk in vks.iter().rev() {
        inputs.push(INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: vk,
                    wScan: 0,
                    dwFlags: KEYEVENTF_KEYUP,
                    time: 0,
                    dwExtraInfo: BINDX_EXTRA_INFO,
                },
            },
        });
    }

    unsafe {
        SendInput(&inputs, std::mem::size_of::<INPUT>() as i32);
    }
}

pub fn is_window_cloaked(hwnd: HWND) -> bool {
    let mut cloaked: u32 = 0;
    unsafe {
        let hr = DwmGetWindowAttribute(
            hwnd,
            DWMWA_CLOAKED,
            &mut cloaked as *mut _ as *mut _,
            std::mem::size_of::<u32>() as u32,
        );
        hr.is_ok() && cloaked != 0
    }
}

pub fn get_window_title(hwnd: HWND) -> String {
    unsafe {
        let len = GetWindowTextLengthW(hwnd);
        if len == 0 {
            return String::new();
        }
        let mut buf = vec![0u16; (len + 1) as usize];
        let copied = GetWindowTextW(hwnd, &mut buf);
        OsString::from_wide(&buf[..copied as usize]).to_string_lossy().to_string()
    }
}

pub fn get_window_class_name(hwnd: HWND) -> String {
    unsafe {
        let mut buf = [0u16; 256];
        let len = GetClassNameW(hwnd, &mut buf);
        if len == 0 {
            return String::new();
        }
        OsString::from_wide(&buf[..len as usize]).to_string_lossy().to_string()
    }
}

pub fn get_window_exe_name(hwnd: HWND) -> Option<String> {
    unsafe {
        let mut pid: u32 = 0;
        GetWindowThreadProcessId(hwnd, Some(&mut pid));
        if pid == 0 {
            return None;
        }

        let handle = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, pid).ok()?;
        let mut buf = [0u16; MAX_PATH as usize];
        let mut len = buf.len() as u32;

        // QueryFullProcessImageNameW supports 32-bit processes from 64-bit caller
        let success = QueryFullProcessImageNameW(
            handle,
            PROCESS_NAME_FORMAT(0),
            windows::core::PWSTR(buf.as_mut_ptr()),
            &mut len,
        )
        .is_ok();

        let full_path = if success && len > 0 {
            OsString::from_wide(&buf[..len as usize]).to_string_lossy().to_string()
        } else {
            let len2 = GetModuleFileNameExW(handle, None, &mut buf);
            if len2 == 0 {
                let _ = windows::Win32::Foundation::CloseHandle(handle);
                return None;
            }
            OsString::from_wide(&buf[..len2 as usize]).to_string_lossy().to_string()
        };

        let _ = windows::Win32::Foundation::CloseHandle(handle);

        let file_name = Path::new(&full_path)
            .file_name()?
            .to_string_lossy()
            .to_string();
        Some(file_name)
    }
}

struct SearchCriteria<'a> {
    exe_name: Option<&'a str>,
    title_keyword: Option<&'a str>,
    found_hwnd: Option<HWND>,
    hidden_candidate: Option<HWND>,
}

pub fn find_window(exe_name: Option<&str>, title_keyword: Option<&str>) -> Option<HWND> {
    let exe_name = exe_name.map(|s| s.trim()).filter(|s| !s.is_empty());
    let title_keyword = title_keyword.map(|s| s.trim()).filter(|s| !s.is_empty());

    if exe_name.is_none() && title_keyword.is_none() {
        return None;
    }

    let mut criteria = SearchCriteria {
        exe_name,
        title_keyword,
        found_hwnd: None,
        hidden_candidate: None,
    };

    unsafe extern "system" fn enum_proc(hwnd: HWND, lparam: LPARAM) -> BOOL {
        let criteria = &mut *(lparam.0 as *mut SearchCriteria);

        let ex_style = GetWindowLongW(hwnd, GWL_EXSTYLE);
        if (ex_style & (WS_EX_TOOLWINDOW.0 as i32)) != 0 {
            return BOOL(1);
        }

        let class_name = get_window_class_name(hwnd);
        let ignored_classes = [
            "Chrome_SystemMessageWindow",
            "GDI+ Hook Window Class",
            "Base_PowerMessageWindow",
            "IME",
            "MSCTFIME UI",
            "OrpheusShadow",
            "MozillaDropShadowWindowClass",
        ];
        if ignored_classes.iter().any(|&c| class_name.eq_ignore_ascii_case(c)) {
            return BOOL(1);
        }

        let title = get_window_title(hwnd);

        // Title keyword filter
        if let Some(kw) = criteria.title_keyword {
            if !title.to_lowercase().contains(&kw.to_lowercase()) {
                return BOOL(1);
            }
        }

        // Exe filter
        if let Some(target_exe) = criteria.exe_name {
            if let Some(w_exe) = get_window_exe_name(hwnd) {
                if !w_exe.eq_ignore_ascii_case(target_exe) {
                    return BOOL(1);
                }
            } else {
                return BOOL(1);
            }
        }

        let is_visible = IsWindowVisible(hwnd).as_bool() && !is_window_cloaked(hwnd);

        // Check if this looks like a valid primary application window
        let is_primary_class = class_name.eq_ignore_ascii_case("OrpheusBrowserHost") // NetEase Cloud Music
            || class_name.eq_ignore_ascii_case("WeChatMainWndForPC")                  // WeChat
            || class_name.eq_ignore_ascii_case("Chrome_WidgetWin_1")                  // Chromium/Electron
            || class_name.eq_ignore_ascii_case("MozillaWindowClass");                 // Firefox/Zotero

        let has_meaningful_title = !title.trim().is_empty();

        if is_visible {
            if has_meaningful_title || is_primary_class {
                criteria.found_hwnd = Some(hwnd);
                return BOOL(0); // Stop enumeration, visible window found!
            }
        } else {
            // Invisible / tray window candidate
            if criteria.hidden_candidate.is_none() && (has_meaningful_title || is_primary_class) {
                criteria.hidden_candidate = Some(hwnd);
            }
        }

        BOOL(1)
    }

    unsafe {
        let _ = EnumWindows(Some(enum_proc), LPARAM(&mut criteria as *mut _ as isize));
    }

    criteria.found_hwnd.or(criteria.hidden_candidate)
}

pub fn activate_window(hwnd: HWND) {
    unsafe {
        if IsIconic(hwnd).as_bool() {
            let _ = ShowWindow(hwnd, SW_RESTORE);
        } else {
            let _ = ShowWindow(hwnd, SW_SHOW);
            let _ = ShowWindow(hwnd, SW_RESTORE);
        }

        // Ensure window pops to topmost and un-cloaks
        let _ = SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            0,
            0,
            0,
            0,
            SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW,
        );
        let _ = SetWindowPos(
            hwnd,
            HWND_NOTOPMOST,
            0,
            0,
            0,
            0,
            SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW,
        );

        let fg = GetForegroundWindow();
        if fg != hwnd {
            let cur_thread = GetCurrentThreadId();
            let fg_thread = GetWindowThreadProcessId(fg, None);
            if cur_thread != fg_thread && fg_thread != 0 {
                let _ = AttachThreadInput(cur_thread, fg_thread, true);
                let _ = SetForegroundWindow(hwnd);
                let _ = AttachThreadInput(cur_thread, fg_thread, false);
            } else {
                let _ = SetForegroundWindow(hwnd);
            }
        }
    }
}

pub fn minimize_or_hide_window(hwnd: HWND, hide_behavior: &str) {
    unsafe {
        let behavior = hide_behavior.to_lowercase();
        if behavior.contains("tray") || behavior.contains("taskbar_hidden") || behavior == "hide" {
            let _ = ShowWindow(hwnd, SW_HIDE);
        } else {
            let _ = ShowWindow(hwnd, SW_MINIMIZE);
        }
    }
}

pub fn toggle_app_window(
    hwnd: HWND,
    hide_behavior: Option<&str>,
) {
    unsafe {
        let fg = GetForegroundWindow();
        let is_fg = fg == hwnd;
        let is_min = IsIconic(hwnd).as_bool();
        let is_vis = IsWindowVisible(hwnd).as_bool();

        if is_fg && !is_min && is_vis {
            // Already in foreground and visible: toggle to hide/minimize
            minimize_or_hide_window(hwnd, hide_behavior.unwrap_or("minimize"));
        } else {
            // Not in foreground, or minimized, or hidden: activate
            activate_window(hwnd);
        }
    }
}

pub fn launch_app(install_path: &str) -> Result<(), String> {
    if install_path.trim().is_empty() {
        return Err("未配置可执行程序路径".to_string());
    }
    Command::new(install_path)
        .spawn()
        .map_err(|e| format!("启动程序失败: {}", e))?;
    Ok(())
}

pub fn find_running_process_path(target_exe: &str) -> Option<String> {
    unsafe {
        let snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0).ok()?;
        let mut entry = PROCESSENTRY32W {
            dwSize: std::mem::size_of::<PROCESSENTRY32W>() as u32,
            ..Default::default()
        };

        let mut found_path: Option<String> = None;
        if Process32FirstW(snapshot, &mut entry).is_ok() {
            loop {
                let name = OsString::from_wide(&entry.szExeFile)
                    .to_string_lossy()
                    .trim_matches('\0')
                    .to_string();
                if name.eq_ignore_ascii_case(target_exe) {
                    if let Ok(handle) = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, entry.th32ProcessID) {
                        let mut buf = [0u16; MAX_PATH as usize];
                        let mut len = buf.len() as u32;
                        if QueryFullProcessImageNameW(
                            handle,
                            PROCESS_NAME_FORMAT(0),
                            windows::core::PWSTR(buf.as_mut_ptr()),
                            &mut len,
                        )
                        .is_ok()
                            && len > 0
                        {
                            let p = OsString::from_wide(&buf[..len as usize]).to_string_lossy().to_string();
                            let _ = windows::Win32::Foundation::CloseHandle(handle);
                            found_path = Some(p);
                            break;
                        }
                        let _ = windows::Win32::Foundation::CloseHandle(handle);
                    }
                }
                if Process32NextW(snapshot, &mut entry).is_err() {
                    break;
                }
            }
        }
        let _ = windows::Win32::Foundation::CloseHandle(snapshot);
        found_path
    }
}

pub fn find_app_path_from_registry(target_exe: &str) -> Option<String> {
    unsafe {
        let sub_key: Vec<u16> = format!("SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{}\0", target_exe)
            .encode_utf16()
            .collect();

        for root in [HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE] {
            let mut hkey = HKEY::default();
            if RegOpenKeyExW(root, windows::core::PCWSTR(sub_key.as_ptr()), 0, KEY_READ, &mut hkey).is_ok() {
                let mut buf = [0u16; MAX_PATH as usize];
                let mut cb_data = (buf.len() * 2) as u32;
                let mut reg_type = REG_SZ;
                let status = RegQueryValueExW(
                    hkey,
                    windows::core::PCWSTR::null(),
                    None,
                    Some(&mut reg_type),
                    Some(buf.as_mut_ptr() as *mut u8),
                    Some(&mut cb_data),
                );
                let _ = RegCloseKey(hkey);
                if status.is_ok() && cb_data > 0 {
                    let len = (cb_data as usize / 2).saturating_sub(1);
                    let path = OsString::from_wide(&buf[..len]).to_string_lossy().to_string();
                    let trimmed = path.trim_matches('"').trim();
                    if Path::new(trimmed).exists() {
                        return Some(trimmed.to_string());
                    }
                }
            }
        }
        None
    }
}

/// A browser web app installed via "Install this site as an app", discovered by
/// scanning Start Menu shortcuts whose targets carry `--app-id=` arguments.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InstalledWebApp {
    pub id: String,
    pub name: String,
    pub profile: String,
    pub browser_exe: String,
    /// The `--app-url` recorded in a shortcut, when one exists; used as the
    /// strongest matching signal between a BindX entry and an installed app.
    pub app_url: String,
}

fn utf16_needle(s: &str) -> Vec<u16> {
    s.encode_utf16().collect()
}

fn find_utf16(hay: &[u16], needle: &[u16]) -> Option<usize> {
    hay.windows(needle.len()).position(|w| w == needle)
}

/// Read the value of a `--key=value` style argument out of a .lnk's UTF-16 string data.
fn read_utf16_arg(hay: &[u16], key: &str) -> Option<String> {
    let pos = find_utf16(hay, &utf16_needle(key))?;
    let mut out = String::new();
    for &c in &hay[pos + key.len()..] {
        if c == 0 || c == u16::from(b' ') || c == u16::from(b'"') {
            break;
        }
        out.push(char::from_u32(c as u32)?);
    }
    if out.is_empty() {
        None
    } else {
        Some(out)
    }
}

/// Same as read_utf16_arg but for .lnk files whose string data is stored as ANSI
/// (Windows omits the Unicode flag when every string in the shortcut is ASCII).
fn read_ansi_arg(bytes: &[u8], key: &str) -> Option<String> {
    let nb = key.as_bytes();
    let pos = bytes.windows(nb.len()).position(|w| w == nb)?;
    let mut out = String::new();
    for &c in &bytes[pos + nb.len()..] {
        if c == 0 || c == b' ' || c == b'"' {
            break;
        }
        out.push(c as char);
    }
    if out.is_empty() {
        None
    } else {
        Some(out)
    }
}

fn read_lnk_arg(bytes: &[u8], hay: &[u16], key: &str) -> Option<String> {
    read_utf16_arg(hay, key).or_else(|| read_ansi_arg(bytes, key))
}

/// Browser roots that keep a per-profile installed-web-app registry on disk.
fn browser_roots() -> Vec<(&'static str, std::path::PathBuf)> {
    let Some(local) = dirs::data_local_dir() else { return Vec::new() };
    vec![
        ("msedge.exe", local.join("Microsoft").join("Edge").join("User Data")),
        ("chrome.exe", local.join("Google").join("Chrome").join("User Data")),
    ]
}

/// Collect app-id → app-url pairs from Start Menu / Desktop shortcut arguments.
/// Only a supplementary source: shortcuts exist for pinned / autostart apps,
/// not necessarily for every installed one.
fn shortcut_app_urls() -> std::collections::HashMap<String, String> {
    let mut map = std::collections::HashMap::new();
    let mut stack = Vec::new();
    if let Some(d) = dirs::data_dir() {
        stack.push(d.join("Microsoft").join("Windows").join("Start Menu").join("Programs"));
    }
    if let Some(d) = dirs::desktop_dir() {
        stack.push(d);
    }
    while let Some(dir) = stack.pop() {
        let Ok(rd) = std::fs::read_dir(&dir) else { continue };
        for ent in rd.flatten() {
            let path = ent.path();
            if path.is_dir() {
                stack.push(path);
                continue;
            }
            if path.extension().and_then(|e| e.to_str()) != Some("lnk") {
                continue;
            }
            let Ok(bytes) = std::fs::read(&path) else { continue };
            let hay: Vec<u16> = bytes
                .chunks_exact(2)
                .map(|c| u16::from_le_bytes([c[0], c[1]]))
                .collect();
            let id = read_lnk_arg(&bytes, &hay, "--app-id=");
            let url = read_lnk_arg(&bytes, &hay, "--app-url=");
            if let (Some(id), Some(url)) = (id, url) {
                map.entry(id).or_insert(url);
            }
        }
    }
    map
}

/// Display name of an installed web app: the `_crx__<id>\<name>.ico` file name.
fn web_app_display_name(web_apps: &std::path::Path, id: &str) -> String {
    let Ok(rd) = std::fs::read_dir(web_apps.join(format!("_crx__{}", id))) else {
        return String::new();
    };
    for ent in rd.flatten() {
        let p = ent.path();
        if p.extension().and_then(|e| e.to_str()) == Some("ico") {
            if let Some(stem) = p.file_stem() {
                return stem.to_string_lossy().to_string();
            }
        }
    }
    String::new()
}

/// Enumerate installed browser web apps from each browser profile's own registry
/// (`<profile>\Web Applications\Manifest Resources\<id>`), which exists for every
/// installed app regardless of shortcuts or autostart settings. Browser family and
/// profile name come from the directory structure; display names from the icon file;
/// shortcut arguments only supplement the URL→id pairing.
pub fn list_installed_web_apps() -> Vec<InstalledWebApp> {
    let mut out = Vec::new();
    let url_pairs = shortcut_app_urls();
    for (browser_exe, root) in browser_roots() {
        let Ok(rd) = std::fs::read_dir(&root) else { continue };
        for profile_ent in rd.flatten() {
            let web_apps = profile_ent.path().join("Web Applications");
            if !web_apps.is_dir() {
                continue;
            }
            let profile = profile_ent.file_name().to_string_lossy().to_string();
            let Ok(mr) = std::fs::read_dir(web_apps.join("Manifest Resources")) else {
                continue;
            };
            for id_ent in mr.flatten() {
                if !id_ent.path().is_dir() {
                    continue;
                }
                let id = id_ent.file_name().to_string_lossy().to_string();
                out.push(InstalledWebApp {
                    name: web_app_display_name(&web_apps, &id),
                    app_url: url_pairs.get(&id).cloned().unwrap_or_default(),
                    id,
                    profile: profile.clone(),
                    browser_exe: browser_exe.to_string(),
                });
            }
        }
    }
    out
}

/// Read a running process' command line (OS-level public contract).
fn process_command_line(pid: u32) -> Option<String> {
    unsafe {
        let h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, false, pid).ok()?;
        let raw = h.0 as isize;
        let mut needed = 0u32;
        let _ = NtQueryInformationProcess(
            raw,
            PROCESS_COMMAND_LINE_INFORMATION,
            std::ptr::null_mut(),
            0,
            &mut needed,
        );
        if needed < 16 {
            let _ = CloseHandle(h);
            return None;
        }
        let mut buf = vec![0u8; needed as usize];
        let st = NtQueryInformationProcess(
            raw,
            PROCESS_COMMAND_LINE_INFORMATION,
            buf.as_mut_ptr() as *mut _,
            needed,
            &mut needed,
        );
        let _ = CloseHandle(h);
        if st < 0 {
            return None;
        }
        let len = u16::from_le_bytes([buf[0], buf[1]]) as usize;
        let start = 16usize.min(buf.len());
        let avail = buf.len().saturating_sub(start);
        let wide: Vec<u16> = buf[start..start + len.min(avail)]
            .chunks_exact(2)
            .map(|c| u16::from_le_bytes([c[0], c[1]]))
            .collect();
        Some(String::from_utf16_lossy(&wide))
    }
}

/// Title of the first visible window owned by `pid`, filtered against
/// transient/browser-generic titles ("New tab", "Loading", Edge itself).
fn main_window_title_for_pid(pid: u32) -> Option<String> {
    use windows::Win32::UI::WindowsAndMessaging::{
        EnumWindows, GetWindowThreadProcessId, IsWindowVisible,
    };
    struct Ctx {
        pid: u32,
        title: Option<String>,
    }
    unsafe extern "system" fn proc(hwnd: HWND, lparam: LPARAM) -> windows::Win32::Foundation::BOOL {
        let ctx = &mut *(lparam.0 as *mut Ctx);
        let mut win_pid = 0u32;
        GetWindowThreadProcessId(hwnd, Some(&mut win_pid));
        if win_pid == ctx.pid && IsWindowVisible(hwnd).as_bool() {
            let len = GetWindowTextLengthW(hwnd);
            if len > 0 {
                let mut buf = vec![0u16; len as usize + 1];
                let got = GetWindowTextW(hwnd, &mut buf);
                if got > 0 {
                    let t = String::from_utf16_lossy(&buf[..got as usize]);
                    let low = t.to_lowercase();
                    let generic = ["new tab", "loading", "microsoft edge", "edge‎"]
                        .iter()
                        .any(|g| low.contains(g));
                    if !generic && low != "edge" {
                        ctx.title = Some(t);
                        return windows::Win32::Foundation::BOOL(0); // stop enumerating
                    }
                }
            }
        }
        windows::Win32::Foundation::BOOL(1)
    }
    let mut ctx = Ctx { pid, title: None };
    unsafe {
        let _ = EnumWindows(Some(proc), LPARAM(&mut ctx as *mut Ctx as isize));
    }
    ctx.title
}

fn cmd_arg(cmd: &str, key: &str) -> Option<String> {
    let i = cmd.find(key)?;
    let mut rest = &cmd[i + key.len()..];
    if let Some(stripped) = rest.strip_prefix('"') {
        rest = stripped;
        let end = rest.find('"').unwrap_or(rest.len());
        let v = &rest[..end];
        return if v.is_empty() { None } else { Some(v.to_string()) };
    }
    let end = rest.find(' ').unwrap_or(rest.len());
    let v = &rest[..end];
    if v.is_empty() {
        None
    } else {
        Some(v.to_string())
    }
}

/// Harvest id/url/profile triples from the command lines of currently running
/// browser app-mode processes. This is the only complete, version-stable source:
/// every installed web app window carries its full launch contract on the CLI.
pub fn harvest_running_web_apps() -> Vec<InstalledWebApp> {
    let mut out = Vec::new();
    unsafe {
        let Ok(snap) = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0) else {
            return out;
        };
        let mut entry = PROCESSENTRY32W::default();
        entry.dwSize = std::mem::size_of::<PROCESSENTRY32W>() as u32;
        if Process32FirstW(snap, &mut entry).is_ok() {
            loop {
                let name_end = entry.szExeFile.iter().position(|&c| c == 0).unwrap_or(entry.szExeFile.len());
                let name = String::from_utf16_lossy(&entry.szExeFile[..name_end]).to_lowercase();
                let browser = if name == "msedge.exe" {
                    "msedge.exe"
                } else if name == "chrome.exe" {
                    "chrome.exe"
                } else {
                    ""
                };
                if !browser.is_empty() {
                    if let Some(cmd) = process_command_line(entry.th32ProcessID) {
                        // --app-id alone is enough: running app-mode processes often
                        // carry no --app-url (only shortcut launch params do).
                        if let Some(id) = cmd_arg(&cmd, "--app-id=") {
                            let profile = cmd_arg(&cmd, "--profile-directory=")
                                .unwrap_or_else(|| "Default".to_string());
                            // The app window's title is the most reliable display
                            // name: Edge persists names to disk only lazily.
                            let name = main_window_title_for_pid(entry.th32ProcessID)
                                .unwrap_or_default();
                            out.push(InstalledWebApp {
                                id,
                                name,
                                profile,
                                browser_exe: browser.to_string(),
                                app_url: cmd_arg(&cmd, "--app-url=").unwrap_or_default(),
                            });
                        }
                    }
                }
                if Process32NextW(snap, &mut entry).is_err() {
                    break;
                }
            }
        }
        let _ = CloseHandle(snap);
    }
    out
}

/// Machine-local cache so a web app learned once is recognized ever after,
/// even while its window is closed. Never part of the synced config.
fn web_apps_cache_path() -> Option<std::path::PathBuf> {
    dirs::data_local_dir().map(|d| d.join("BindX").join("webapps_cache.json"))
}

fn load_web_apps_cache() -> Vec<InstalledWebApp> {
    web_apps_cache_path()
        .and_then(|p| std::fs::read_to_string(p).ok())
        .and_then(|s| serde_json::from_str::<Vec<InstalledWebApp>>(&s).ok())
        .unwrap_or_default()
}

fn save_web_apps_cache(cache: &[InstalledWebApp]) {
    if let Some(p) = web_apps_cache_path() {
        if let Some(dir) = p.parent() {
            let _ = std::fs::create_dir_all(dir);
        }
        if let Ok(s) = serde_json::to_string(cache) {
            let _ = std::fs::write(p, s);
        }
    }
}

/// Live view of installed web apps: machine-local cache (topped up from running
/// app processes right now) merged with the on-disk profile registry and any
/// shortcut URL pairings.
pub fn refresh_installed_web_apps() -> Vec<InstalledWebApp> {
    let mut apps = load_web_apps_cache();
    let mut changed = false;
    for h in harvest_running_web_apps() {
        match apps.iter_mut().find(|c| c.id == h.id && c.profile == h.profile) {
            Some(slot) => {
                if slot.app_url.is_empty() && !h.app_url.is_empty() {
                    slot.app_url = h.app_url;
                    changed = true;
                }
                if slot.name.is_empty() && !h.name.is_empty() {
                    slot.name = h.name;
                    changed = true;
                }
            }
            None => {
                apps.push(h);
                changed = true;
            }
        }
    }
    if changed {
        save_web_apps_cache(&apps);
    }
    for reg in list_installed_web_apps() {
        match apps.iter_mut().find(|a| a.id == reg.id && a.profile == reg.profile) {
            Some(slot) => {
                if slot.name.is_empty() && !reg.name.is_empty() {
                    slot.name = reg.name;
                }
                if slot.app_url.is_empty() && !reg.app_url.is_empty() {
                    slot.app_url = reg.app_url;
                }
            }
            None => apps.push(reg),
        }
    }
    apps
}

fn url_origin(url: &str) -> String {
    let t = url.trim().to_lowercase();
    match t.find("://") {
        Some(i) => {
            let rest = &t[i + 3..];
            let end = rest.find('/').unwrap_or(rest.len());
            t[..i + 3 + end].to_string()
        }
        None => String::new(),
    }
}

fn url_norm(url: &str) -> String {
    url.trim().to_lowercase().trim_end_matches('/').to_string()
}

/// Match a BindX entry against the installed web apps.
///
/// 1. URL pairing: an app whose recorded `--app-url` shares the entry URL's origin,
///    or where one normalized URL is a prefix of the other (recorded URLs carry
///    launch query params the user never types).
/// 2. Name affinity: the entry's title keyword / display name contained in (or
///    containing) an app's display name — covers apps without any shortcut,
///    since the registry and icon name always exist.
///
/// `hints` should carry the entry's title_keyword and name.
pub fn find_installed_web_app_for_url(url: &str, hints: &[String]) -> Option<InstalledWebApp> {
    let apps = refresh_installed_web_apps();

    let want = url_norm(url);
    if !want.is_empty() {
        let want_origin = url_origin(url);
        if let Some(app) = apps.iter().find(|a| {
            if a.app_url.trim().is_empty() {
                return false;
            }
            let got = url_norm(&a.app_url);
            url_origin(&a.app_url) == want_origin || got.starts_with(&want) || want.starts_with(&got)
        }) {
            return Some(app.clone());
        }
    }

    let hints: Vec<String> = hints
        .iter()
        .map(|h| h.trim().to_lowercase())
        .filter(|h| h.chars().count() >= 2)
        .collect();
    if hints.is_empty() {
        return None;
    }
    apps.iter().find(|a| {
        let name = a.name.trim().to_lowercase();
        !name.is_empty() && hints.iter().any(|h| name.contains(h.as_str()) || h.contains(name.as_str()))
    }).cloned()
}

/// Launch an installed web app with its full browser identity (app menu, pins, etc).
pub fn launch_installed_web_app(
    browser_exe: &str,
    profile: &str,
    app_id: &str,
) -> Result<(), String> {
    let path = resolve_app_executable_path(browser_exe)
        .ok_or_else(|| format!("未找到浏览器: {}", browser_exe))?;
    Command::new(&path)
        .arg(format!("--profile-directory={}", profile))
        .arg(format!("--app-id={}", app_id))
        .spawn()
        .map(|_| ())
        .map_err(|e| format!("启动已安装网页应用失败: {}", e))
}

/// Look up an app's install path via the uninstall registry (HKCU/HKLM, both
/// 64/32-bit views). Catches per-user installers (Termius, VS Code, etc.) that
/// have no App Paths entry. Matches DisplayName prefix, then prefers
/// DisplayIcon and falls back to InstallLocation\<exe>.
fn find_app_path_from_uninstall(exe_name: &str) -> Option<String> {
    use windows::Win32::System::Registry::{RegCloseKey, RegEnumKeyExW, RegOpenKeyExW, HKEY};
    let base = exe_name.to_lowercase();
    let base = base.trim_end_matches(".exe");

    unsafe extern "system" fn reg_string(
        hkey: HKEY,
        value: &str,
    ) -> Option<String> {
        use windows::Win32::System::Registry::RegQueryValueExW;
        let value_wide: Vec<u16> = value.encode_utf16().chain(std::iter::once(0)).collect();
        unsafe {
            let mut buf = vec![0u16; 512];
            let mut cb_data = (buf.len() * 2) as u32;
            let mut reg_type = REG_SZ;
            let status = RegQueryValueExW(
                hkey,
                windows::core::PCWSTR(value_wide.as_ptr()),
                None,
                Some(&mut reg_type),
                Some(buf.as_mut_ptr() as *mut u8),
                Some(&mut cb_data),
            );
            if status.is_ok() && cb_data > 0 {
                let len = (cb_data as usize / 2).saturating_sub(1);
                return Some(OsString::from_wide(&buf[..len]).to_string_lossy().to_string());
            }
            None
        }
    }

    unsafe {
        for root in [HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE] {
            for view in [
                "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall",
                "SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall",
            ] {
                let view_wide: Vec<u16> = view.encode_utf16().chain(std::iter::once(0)).collect();
                let mut hkey = HKEY::default();
                if RegOpenKeyExW(
                    root,
                    windows::core::PCWSTR(view_wide.as_ptr()),
                    0,
                    KEY_READ,
                    &mut hkey,
                )
                .is_err()
                {
                    continue;
                }
                let mut index = 0u32;
                loop {
                    let mut name_buf = [0u16; 256];
                    let mut name_len = name_buf.len() as u32;
                    let rc = RegEnumKeyExW(
                        hkey,
                        index,
                        windows::core::PWSTR(name_buf.as_mut_ptr()),
                        &mut name_len,
                        None,
                        windows::core::PWSTR::null(),
                        None,
                        None,
                    );
                    if rc.is_err() {
                        break;
                    }
                    index += 1;
                    let mut sub = HKEY::default();
                    let sub_wide: Vec<u16> = OsString::from_wide(&name_buf[..name_len as usize])
                        .to_string_lossy()
                        .encode_utf16()
                        .chain(std::iter::once(0))
                        .collect();
                    if RegOpenKeyExW(
                        hkey,
                        windows::core::PCWSTR(sub_wide.as_ptr()),
                        0,
                        KEY_READ,
                        &mut sub,
                    )
                    .is_err()
                    {
                        continue;
                    }
                    let display = reg_string(sub, "DisplayName").unwrap_or_default();
                    let matched = display.to_lowercase().starts_with(base);
                    let mut found = None;
                    if matched {
                        if let Some(icon) = reg_string(sub, "DisplayIcon") {
                            let cand = icon
                                .trim_matches('"')
                                .split(',')
                                .next()
                                .unwrap_or_default()
                                .trim()
                                .to_string();
                            if cand.to_lowercase().ends_with(".exe") && Path::new(&cand).is_file() {
                                found = Some(cand);
                            }
                        }
                        if found.is_none() {
                            if let Some(loc) = reg_string(sub, "InstallLocation") {
                                let cand = Path::new(loc.trim_matches('"')).join(exe_name);
                                if cand.is_file() {
                                    found = Some(cand.to_string_lossy().to_string());
                                }
                            }
                        }
                    }
                    let _ = RegCloseKey(sub);
                    if let Some(p) = found {
                        let _ = RegCloseKey(hkey);
                        return Some(p);
                    }
                }
                let _ = RegCloseKey(hkey);
            }
        }
        None
    }
}

pub fn resolve_app_executable_path(exe_name: &str) -> Option<String> {
    if let Some(p) = find_running_process_path(exe_name) {
        return Some(p);
    }
    if let Some(p) = find_app_path_from_registry(exe_name) {
        return Some(p);
    }
    if let Some(p) = find_app_path_from_uninstall(exe_name) {
        return Some(p);
    }
    let mut common_dirs: Vec<String> = vec![
        r"C:\Program Files".to_string(),
        r"C:\Program Files (x86)".to_string(),
        r"D:\Program Files".to_string(),
        r"D:\Program Files (x86)".to_string(),
    ];
    if let Some(local) = dirs::data_local_dir() {
        common_dirs.push(local.join("Programs").to_string_lossy().to_string());
    }
    for dir in &common_dirs {
        let candidate = Path::new(dir).join(exe_name);
        if candidate.exists() {
            return Some(candidate.to_string_lossy().to_string());
        }
        // Per-user installers nest one level deep (e.g. %LOCALAPPDATA%\Programs\Termius\Termius.exe)
        if let Ok(rd) = std::fs::read_dir(dir) {
            for ent in rd.flatten() {
                let candidate = ent.path().join(exe_name);
                if candidate.is_file() {
                    return Some(candidate.to_string_lossy().to_string());
                }
            }
        }
    }
    None
}


/// Open a URL in a browser, either as a standalone app-mode window or as a tab.
///
/// - `app_window = true`: launch the browser with `--app=<url>`, yielding a standalone
///   window without tab strip / address bar (the "installed web app" look). Requires a
///   resolvable browser exe; probes common browsers when none is configured.
/// - `app_window = false`: reuse a running browser instance (new tab), falling back to
///   ShellExecuteW so the system default handler picks the browser.
pub fn open_url_in_browser(url: &str, browser_exe: Option<&str>, app_window: bool) -> Result<(), String> {
    if url.trim().is_empty() {
        return Err("目标 URL 为空".to_string());
    }

    if app_window {
        let candidates: Vec<&str> = match browser_exe.filter(|e| !e.trim().is_empty()) {
            Some(exe) => vec![exe],
            None => vec!["msedge.exe", "chrome.exe"],
        };
        for exe in candidates {
            if let Some(browser_path) = resolve_app_executable_path(exe) {
                return Command::new(&browser_path)
                    .arg(format!("--app={}", url))
                    .spawn()
                    .map(|_| ())
                    .map_err(|e| format!("启动 app 窗口失败: {}", e));
            }
        }
        // No known browser resolved: fall through to the default handler below.
    } else if let Some(exe) = browser_exe.filter(|e| !e.trim().is_empty()) {
        // If a specific browser exe is requested and we can find it, launch it directly with the URL.
        // Many browsers accept a URL as argument and will open it in an existing window.
        if let Some(browser_path) = resolve_app_executable_path(exe) {
            let _ = Command::new(&browser_path).arg(url).spawn();
            return Ok(());
        }
    }

    // Fallback: ShellExecuteW with "open" verb – the system picks the default browser and
    // reuses an existing browser instance (opens a new tab, not a new window).
    let url_wide: Vec<u16> = url.encode_utf16().chain(std::iter::once(0)).collect();
    let verb_wide: Vec<u16> = "open".encode_utf16().chain(std::iter::once(0)).collect();

    unsafe {
        let result = ShellExecuteW(
            HWND::default(),
            windows::core::PCWSTR(verb_wide.as_ptr()),
            windows::core::PCWSTR(url_wide.as_ptr()),
            windows::core::PCWSTR::null(),
            windows::core::PCWSTR::null(),
            windows::Win32::UI::WindowsAndMessaging::SW_SHOWNORMAL,
        );
        if result.0 as isize > 32 {
            Ok(())
        } else {
            Err(format!("ShellExecuteW 失败，返回值: {}", result.0 as isize))
        }
    }
}
