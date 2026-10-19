use std::ffi::OsString;
use std::os::windows::ffi::OsStringExt;
use std::path::Path;
use std::process::Command;
use windows::Win32::Foundation::{BOOL, HWND, LPARAM, MAX_PATH};
use windows::Win32::Graphics::Dwm::{DwmGetWindowAttribute, DWMWA_CLOAKED};
use windows::Win32::System::ProcessStatus::GetModuleFileNameExW;
use windows::Win32::System::Threading::{
    AttachThreadInput, GetCurrentThreadId, OpenProcess, PROCESS_QUERY_LIMITED_INFORMATION,
};
use windows::Win32::UI::Input::KeyboardAndMouse::{
    SendInput, INPUT, INPUT_0, INPUT_KEYBOARD, KEYBDINPUT, KEYEVENTF_KEYUP,
    VIRTUAL_KEY, VK_BACK, VK_CONTROL, VK_DELETE, VK_DOWN, VK_ESCAPE, VK_F1, VK_F10, VK_F11,
    VK_F12, VK_F2, VK_F3, VK_F4, VK_F5, VK_F6, VK_F7, VK_F8, VK_F9, VK_LEFT, VK_LWIN, VK_MENU,
    VK_RETURN, VK_RIGHT, VK_SHIFT, VK_SPACE, VK_TAB, VK_UP,
};
use windows::Win32::UI::WindowsAndMessaging::{
    EnumWindows, GetForegroundWindow, GetWindowLongW, GetWindowTextLengthW, GetWindowTextW,
    GetWindowThreadProcessId, IsIconic, IsWindowVisible, SetForegroundWindow, ShowWindow,
    GWL_EXSTYLE, SW_HIDE, SW_MINIMIZE, SW_RESTORE, SW_SHOW, WS_EX_TOOLWINDOW,
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

pub fn get_window_exe_name(hwnd: HWND) -> Option<String> {
    unsafe {
        let mut pid: u32 = 0;
        GetWindowThreadProcessId(hwnd, Some(&mut pid));
        if pid == 0 {
            return None;
        }

        let handle = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, pid).ok()?;
        let mut buf = [0u16; MAX_PATH as usize];
        let len = GetModuleFileNameExW(handle, None, &mut buf);
        let _ = windows::Win32::Foundation::CloseHandle(handle);

        if len == 0 {
            return None;
        }

        let full_path = OsString::from_wide(&buf[..len as usize]).to_string_lossy().to_string();
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
}

pub fn find_window(exe_name: Option<&str>, title_keyword: Option<&str>) -> Option<HWND> {
    let mut criteria = SearchCriteria {
        exe_name,
        title_keyword,
        found_hwnd: None,
    };

    unsafe extern "system" fn enum_proc(hwnd: HWND, lparam: LPARAM) -> BOOL {
        let criteria = &mut *(lparam.0 as *mut SearchCriteria);

        if !IsWindowVisible(hwnd).as_bool() || is_window_cloaked(hwnd) {
            return BOOL(1);
        }

        let ex_style = GetWindowLongW(hwnd, GWL_EXSTYLE);
        if (ex_style & (WS_EX_TOOLWINDOW.0 as i32)) != 0 {
            return BOOL(1);
        }

        let title = get_window_title(hwnd);
        if title.trim().is_empty() {
            return BOOL(1);
        }

        // Title filter
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

        // Found matching window!
        criteria.found_hwnd = Some(hwnd);
        BOOL(0) // Stop enumeration
    }

    unsafe {
        let _ = EnumWindows(Some(enum_proc), LPARAM(&mut criteria as *mut _ as isize));
    }

    criteria.found_hwnd
}

pub fn activate_window(hwnd: HWND) {
    unsafe {
        if IsIconic(hwnd).as_bool() {
            let _ = ShowWindow(hwnd, SW_RESTORE);
        } else {
            let _ = ShowWindow(hwnd, SW_SHOW);
        }

        let fg = GetForegroundWindow();
        if fg != hwnd {
            let cur_thread = GetCurrentThreadId();
            let fg_thread = GetWindowThreadProcessId(fg, None);
            if cur_thread != fg_thread {
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
        if hide_behavior.contains("tray") || hide_behavior.contains("taskbar_hidden") {
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

        if is_fg && !is_min {
            // Already in foreground: toggle to hide/minimize
            minimize_or_hide_window(hwnd, hide_behavior.unwrap_or("minimize"));
        } else {
            // Not in foreground or minimized: activate
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
