use crate::config::{KeyMapping, MouseMapping, MouseSection};
use crate::engine::win32::{get_vk_code, send_key_sequence, BINDX_EXTRA_INFO};
use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use windows::Win32::Foundation::{HINSTANCE, HWND, LPARAM, LRESULT, WPARAM};
use windows::Win32::UI::Input::KeyboardAndMouse::GetAsyncKeyState;
use windows::Win32::UI::WindowsAndMessaging::{
    CallNextHookEx, DispatchMessageW, GetMessageW, PostThreadMessageW, SetWindowsHookExW,
    TranslateMessage, UnhookWindowsHookEx, HHOOK, KBDLLHOOKSTRUCT, MSG, MSLLHOOKSTRUCT,
    WH_KEYBOARD_LL, WH_MOUSE_LL, WM_KEYDOWN, WM_QUIT, WM_SYSKEYDOWN, WM_XBUTTONDOWN,
};

static mut MOUSE_HOOK: HHOOK = HHOOK(std::ptr::null_mut());
static mut KBD_HOOK: HHOOK = HHOOK(std::ptr::null_mut());
static mut ACTIVE_MOUSE_RULES: Option<Vec<MouseMapping>> = None;
static mut ACTIVE_KEY_RULES: Option<Vec<KeyMapping>> = None;

pub struct RemapEngine {
    thread_id: Arc<AtomicU32>,
    running: Arc<AtomicBool>,
    section: Arc<Mutex<MouseSection>>,
}

impl RemapEngine {
    pub fn new() -> Self {
        Self {
            thread_id: Arc::new(AtomicU32::new(0)),
            running: Arc::new(AtomicBool::new(false)),
            section: Arc::new(Mutex::new(MouseSection::default())),
        }
    }

    pub fn start(&self, section: MouseSection) {
        if self.running.load(Ordering::SeqCst) {
            self.reload(section);
            return;
        }

        {
            let mut s = self.section.lock().unwrap();
            *s = section;
        }

        self.running.store(true, Ordering::SeqCst);

        let thread_id_atomic = self.thread_id.clone();
        let running_atomic = self.running.clone();
        let section_arc = self.section.clone();

        thread::spawn(move || {
            let tid = unsafe { windows::Win32::System::Threading::GetCurrentThreadId() };
            thread_id_atomic.store(tid, Ordering::SeqCst);

            unsafe {
                let current_rules = section_arc.lock().unwrap().clone();
                ACTIVE_MOUSE_RULES = Some(current_rules.mouse_mappings);
                ACTIVE_KEY_RULES = Some(current_rules.mappings);

                MOUSE_HOOK = SetWindowsHookExW(
                    WH_MOUSE_LL,
                    Some(mouse_hook_proc),
                    HINSTANCE(std::ptr::null_mut()),
                    0,
                ).unwrap_or(HHOOK(std::ptr::null_mut()));

                KBD_HOOK = SetWindowsHookExW(
                    WH_KEYBOARD_LL,
                    Some(kbd_hook_proc),
                    HINSTANCE(std::ptr::null_mut()),
                    0,
                ).unwrap_or(HHOOK(std::ptr::null_mut()));

                let mut msg = MSG::default();
                while running_atomic.load(Ordering::SeqCst) {
                    let b_ret = GetMessageW(&mut msg, HWND::default(), 0, 0);
                    if b_ret.0 == 0 || b_ret.0 == -1 {
                        break;
                    }
                    let _ = TranslateMessage(&msg);
                    DispatchMessageW(&msg);
                }

                if !MOUSE_HOOK.0.is_null() {
                    let _ = UnhookWindowsHookEx(MOUSE_HOOK);
                    MOUSE_HOOK = HHOOK(std::ptr::null_mut());
                }
                if !KBD_HOOK.0.is_null() {
                    let _ = UnhookWindowsHookEx(KBD_HOOK);
                    KBD_HOOK = HHOOK(std::ptr::null_mut());
                }

                ACTIVE_MOUSE_RULES = None;
                ACTIVE_KEY_RULES = None;
            }

            thread_id_atomic.store(0, Ordering::SeqCst);
        });
    }

    pub fn reload(&self, section: MouseSection) {
        {
            let mut s = self.section.lock().unwrap();
            *s = section.clone();
        }

        unsafe {
            ACTIVE_MOUSE_RULES = Some(section.mouse_mappings);
            ACTIVE_KEY_RULES = Some(section.mappings);
        }
    }

    pub fn stop(&self) {
        if !self.running.load(Ordering::SeqCst) {
            return;
        }
        self.running.store(false, Ordering::SeqCst);

        let tid = self.thread_id.load(Ordering::SeqCst);
        if tid != 0 {
            unsafe {
                let _ = PostThreadMessageW(tid, WM_QUIT, WPARAM(0), LPARAM(0));
            }
        }
    }

    pub fn is_running(&self) -> bool {
        self.running.load(Ordering::SeqCst)
    }
}

unsafe extern "system" fn mouse_hook_proc(n_code: i32, w_param: WPARAM, l_param: LPARAM) -> LRESULT {
    if n_code >= 0 && (w_param.0 as u32) == WM_XBUTTONDOWN {
        let info = &*(l_param.0 as *const MSLLHOOKSTRUCT);
        if info.dwExtraInfo == BINDX_EXTRA_INFO {
            return CallNextHookEx(MOUSE_HOOK, n_code, w_param, l_param);
        }

        let button_flag = (info.mouseData >> 16) & 0xFFFF;
        let btn_str = match button_flag {
            1 => "x1",
            2 => "x2",
            _ => "",
        };

        if !btn_str.is_empty() {
            if let Some(ref rules) = ACTIVE_MOUSE_RULES {
                for rule in rules {
                    if rule.enabled && rule.button.eq_ignore_ascii_case(btn_str) {
                        let out_keys = rule.output.clone();
                        thread::spawn(move || {
                            send_key_sequence(&out_keys);
                        });
                        return LRESULT(1); // Intercept event!
                    }
                }
            }
        }
    }

    CallNextHookEx(MOUSE_HOOK, n_code, w_param, l_param)
}

unsafe extern "system" fn kbd_hook_proc(n_code: i32, w_param: WPARAM, l_param: LPARAM) -> LRESULT {
    if n_code >= 0 && (w_param.0 as u32 == WM_KEYDOWN || w_param.0 as u32 == WM_SYSKEYDOWN) {
        let info = &*(l_param.0 as *const KBDLLHOOKSTRUCT);
        if info.dwExtraInfo == BINDX_EXTRA_INFO {
            return CallNextHookEx(KBD_HOOK, n_code, w_param, l_param);
        }

        if let Some(ref rules) = ACTIVE_KEY_RULES {
            for rule in rules {
                if !rule.enabled || rule.trigger.is_empty() {
                    continue;
                }

                // Check if all trigger keys are currently pressed
                let mut all_match = true;
                for trigger_key in &rule.trigger {
                    if let Some(vk) = get_vk_code(trigger_key) {
                        let is_down = if vk.0 == info.vkCode as u16 {
                            true
                        } else {
                            (GetAsyncKeyState(vk.0 as i32) as u16 & 0x8000) != 0
                        };

                        if !is_down {
                            all_match = false;
                            break;
                        }
                    } else {
                        all_match = false;
                        break;
                    }
                }

                if all_match {
                    let out_keys = rule.output.clone();
                    thread::spawn(move || {
                        send_key_sequence(&out_keys);
                    });
                    return LRESULT(1); // Intercept event
                }
            }
        }
    }

    CallNextHookEx(KBD_HOOK, n_code, w_param, l_param)
}
