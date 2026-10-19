use std::ffi::OsString;
use std::os::windows::ffi::OsStringExt;
use std::path::Path;
use std::process::Command;
use windows::Win32::Foundation::{BOOL, HWND, LPARAM, MAX_PATH};
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
    PROCESS_NAME_FORMAT, PROCESS_QUERY_LIMITED_INFORMATION,
};
use windows::Win32::UI::Input::KeyboardAndMouse::{
    SendInput, INPUT, INPUT_0, INPUT_KEYBOARD, KEYBDINPUT, KEYEVENTF_KEYUP,
    VIRTUAL_KEY, VK_BACK, VK_CONTROL, VK_DELETE, VK_DOWN, VK_ESCAPE, VK_F1, VK_F10, VK_F11,
    VK_F12, VK_F2, VK_F3, VK_F4, VK_F5, VK_F6, VK_F7, VK_F8, VK_F9, VK_LEFT, VK_LWIN, VK_MENU,
    VK_RETURN, VK_RIGHT, VK_SHIFT, VK_SPACE, VK_TAB, VK_UP,
};
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

pub fn resolve_app_executable_path(exe_name: &str) -> Option<String> {
    if let Some(p) = find_running_process_path(exe_name) {
        return Some(p);
    }
    if let Some(p) = find_app_path_from_registry(exe_name) {
        return Some(p);
    }
    let common_dirs = [
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        r"D:\Program Files",
        r"D:\Program Files (x86)",
    ];
    for dir in &common_dirs {
        let candidate = Path::new(dir).join(exe_name);
        if candidate.exists() {
            return Some(candidate.to_string_lossy().to_string());
        }
    }
    None
}
