#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

#[cfg(windows)]
mod single_instance {
    use std::sync::atomic::{AtomicIsize, Ordering};
    use windows::core::{w, PCWSTR};
    use windows::Win32::Foundation::{CloseHandle, ERROR_ALREADY_EXISTS, GetLastError, BOOL, HWND, LPARAM};
    use windows::Win32::System::Threading::CreateMutexW;
    use windows::Win32::UI::WindowsAndMessaging::{
        AllowSetForegroundWindow, EnumWindows, FindWindowW, GetWindowTextW, SetForegroundWindow,
        ShowWindow, ASFW_ANY, SW_RESTORE, SW_SHOW,
    };

    static MUTEX_HANDLE: AtomicIsize = AtomicIsize::new(0);

    pub fn acquire_single_instance() -> bool {
        unsafe {
            let handle_res = CreateMutexW(None, true, w!("Local\\BindX_Desktop_SingleInstance_Mutex"));
            match handle_res {
                Ok(handle) => {
                    if GetLastError() == ERROR_ALREADY_EXISTS {
                        let _ = CloseHandle(handle);
                        activate_existing_instance();
                        return false;
                    }
                    MUTEX_HANDLE.store(handle.0 as isize, Ordering::SeqCst);
                    true
                }
                Err(_) => true,
            }
        }
    }

    fn activate_existing_instance() {
        unsafe {
            let _ = AllowSetForegroundWindow(ASFW_ANY);

            // 1. Try FindWindowW directly with title "BindX"
            if let Ok(hwnd) = FindWindowW(PCWSTR::null(), w!("BindX")) {
                if !hwnd.is_invalid() && !hwnd.0.is_null() {
                    let _ = ShowWindow(hwnd, SW_SHOW);
                    let _ = ShowWindow(hwnd, SW_RESTORE);
                    let _ = SetForegroundWindow(hwnd);
                    return;
                }
            }

            // 2. Fallback: EnumWindows to find any top-level window with title "BindX"
            unsafe extern "system" fn enum_proc(hwnd: HWND, _lparam: LPARAM) -> BOOL {
                let mut buf = [0u16; 256];
                let len = GetWindowTextW(hwnd, &mut buf);
                if len > 0 {
                    let title = String::from_utf16_lossy(&buf[..len as usize]);
                    if title == "BindX" {
                        let _ = ShowWindow(hwnd, SW_SHOW);
                        let _ = ShowWindow(hwnd, SW_RESTORE);
                        let _ = SetForegroundWindow(hwnd);
                        return BOOL(0); // stop enumeration
                    }
                }
                BOOL(1) // continue enumeration
            }

            let _ = EnumWindows(Some(enum_proc), LPARAM(0));
        }
    }
}

fn main() {
    #[cfg(windows)]
    {
        if !single_instance::acquire_single_instance() {
            std::process::exit(0);
        }
    }

    bindx::run();
}
