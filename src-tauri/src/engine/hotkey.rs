use crate::config::HotkeyEntry;
use crate::engine::win32::{find_window, get_vk_code, launch_app, toggle_app_window};
use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use windows::Win32::Foundation::HWND;
use windows::Win32::UI::Input::KeyboardAndMouse::{
    RegisterHotKey, UnregisterHotKey, HOT_KEY_MODIFIERS, MOD_ALT, MOD_CONTROL, MOD_NOREPEAT,
    MOD_SHIFT, MOD_WIN,
};
use windows::Win32::UI::WindowsAndMessaging::{
    DispatchMessageW, GetMessageW, PostThreadMessageW, TranslateMessage, MSG, WM_HOTKEY, WM_QUIT,
    WM_USER,
};

const WM_HOTKEY_RELOAD: u32 = WM_USER + 101;

pub struct RegisteredRule {
    pub id: i32,
    pub entry: HotkeyEntry,
}

pub struct HotkeyEngine {
    thread_id: Arc<AtomicU32>,
    running: Arc<AtomicBool>,
    rules: Arc<Mutex<Vec<HotkeyEntry>>>,
    toggle_window_sender: Arc<Mutex<Option<Box<dyn Fn() + Send + Sync + 'static>>>>,
}

impl HotkeyEngine {
    pub fn new() -> Self {
        Self {
            thread_id: Arc::new(AtomicU32::new(0)),
            running: Arc::new(AtomicBool::new(false)),
            rules: Arc::new(Mutex::new(Vec::new())),
            toggle_window_sender: Arc::new(Mutex::new(None)),
        }
    }

    pub fn set_toggle_window_handler<F>(&self, handler: F)
    where
        F: Fn() + Send + Sync + 'static,
    {
        let mut h = self.toggle_window_sender.lock().unwrap();
        *h = Some(Box::new(handler));
    }

    pub fn start(&self, initial_entries: Vec<HotkeyEntry>) {
        if self.running.load(Ordering::SeqCst) {
            self.reload(initial_entries);
            return;
        }

        {
            let mut r = self.rules.lock().unwrap();
            *r = initial_entries;
        }

        self.running.store(true, Ordering::SeqCst);

        let thread_id_atomic = self.thread_id.clone();
        let running_atomic = self.running.clone();
        let rules_mutex = self.rules.clone();
        let toggle_cb_mutex = self.toggle_window_sender.clone();

        thread::spawn(move || {
            let tid = unsafe { windows::Win32::System::Threading::GetCurrentThreadId() };
            thread_id_atomic.store(tid, Ordering::SeqCst);

            let mut active_registered: Vec<RegisteredRule> = Vec::new();

            // Initial registration
            register_all(&mut active_registered, &rules_mutex);

            let mut msg = MSG::default();
            unsafe {
                while running_atomic.load(Ordering::SeqCst) {
                    let b_ret = GetMessageW(&mut msg, HWND::default(), 0, 0);
                    if b_ret.0 == 0 || b_ret.0 == -1 {
                        break;
                    }

                    if msg.message == WM_HOTKEY_RELOAD {
                        unregister_all(&mut active_registered);
                        register_all(&mut active_registered, &rules_mutex);
                        continue;
                    }

                    if msg.message == WM_HOTKEY {
                        let hotkey_id = msg.wParam.0 as i32;
                        if let Some(rule) = active_registered.iter().find(|r| r.id == hotkey_id) {
                            handle_hotkey_trigger(&rule.entry, &toggle_cb_mutex);
                        }
                    }

                    let _ = TranslateMessage(&msg);
                    DispatchMessageW(&msg);
                }

                unregister_all(&mut active_registered);
            }

            thread_id_atomic.store(0, Ordering::SeqCst);
        });
    }

    pub fn reload(&self, new_entries: Vec<HotkeyEntry>) {
        {
            let mut r = self.rules.lock().unwrap();
            *r = new_entries;
        }

        let tid = self.thread_id.load(Ordering::SeqCst);
        if tid != 0 {
            unsafe {
                let _ = PostThreadMessageW(tid, WM_HOTKEY_RELOAD, windows::Win32::Foundation::WPARAM(0), windows::Win32::Foundation::LPARAM(0));
            }
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
                let _ = PostThreadMessageW(tid, WM_QUIT, windows::Win32::Foundation::WPARAM(0), windows::Win32::Foundation::LPARAM(0));
            }
        }
    }

    pub fn is_running(&self) -> bool {
        self.running.load(Ordering::SeqCst)
    }
}

fn register_all(
    active: &mut Vec<RegisteredRule>,
    rules_mutex: &Arc<Mutex<Vec<HotkeyEntry>>>,
) {
    let entries = {
        let lock = rules_mutex.lock().unwrap();
        lock.clone()
    };

    let mut id_counter = 1;
    for entry in entries {
        if !entry.enabled {
            continue;
        }

        if let Some((mods, vk)) = parse_hotkey(&entry.hotkey) {
            unsafe {
                let ok = RegisterHotKey(HWND::default(), id_counter, mods | MOD_NOREPEAT, vk);
                if ok.is_ok() {
                    active.push(RegisteredRule {
                        id: id_counter,
                        entry,
                    });
                    id_counter += 1;
                }
            }
        }
    }
}

fn unregister_all(active: &mut Vec<RegisteredRule>) {
    unsafe {
        for rule in active.drain(..) {
            let _ = UnregisterHotKey(HWND::default(), rule.id);
        }
    }
}

fn parse_hotkey(hotkey_str: &str) -> Option<(HOT_KEY_MODIFIERS, u32)> {
    let parts: Vec<&str> = hotkey_str.split('+').map(|s| s.trim()).collect();
    let mut mods = HOT_KEY_MODIFIERS(0);
    let mut vk_code: Option<u32> = None;

    for part in parts {
        let upper = part.to_uppercase();
        match upper.as_str() {
            "CTRL" | "CONTROL" => mods |= MOD_CONTROL,
            "ALT" | "MENU" => mods |= MOD_ALT,
            "SHIFT" => mods |= MOD_SHIFT,
            "WIN" | "WINDOWS" => mods |= MOD_WIN,
            _ => {
                if let Some(vk) = get_vk_code(part) {
                    vk_code = Some(vk.0 as u32);
                }
            }
        }
    }

    let vk = vk_code?;
    Some((mods, vk))
}

fn handle_hotkey_trigger(
    entry: &HotkeyEntry,
    toggle_cb: &Arc<Mutex<Option<Box<dyn Fn() + Send + Sync + 'static>>>>,
) {
    // 1. Check if this is BindX itself
    if entry.app == "hot_key_manager" || entry.name.as_deref() == Some("BindX") {
        if let Some(cb) = toggle_cb.lock().unwrap().as_ref() {
            cb();
        }
        return;
    }

    let hide_behavior = entry._runtime_profile.get("hide_behavior")
        .and_then(|v| v.as_str());

    let (exe_name, title_keyword) = match entry.target_type.as_deref() {
        Some("browser_tab") => {
            (entry.exe_name.as_deref(), entry.title_keyword.as_deref())
        }
        Some("builtin") => {
            if entry.app == "termius" || entry.name.as_deref() == Some("Termius") {
                (Some("Termius.exe"), None)
            } else {
                (entry.exe_name.as_deref(), entry.title_keyword.as_deref())
            }
        }
        _ => {
            // General or app-name based
            let exe = if let Some(ref e) = entry.exe_name {
                Some(e.as_str())
            } else {
                match entry.app.as_str() {
                    "cloudmusic" => Some("cloudmusic.exe"),
                    "zotero" => Some("zotero.exe"),
                    _ => None,
                }
            };
            (exe, entry.title_keyword.as_deref())
        }
    };

    if let Some(hwnd) = find_window(exe_name, title_keyword) {
        toggle_app_window(hwnd, hide_behavior);
    } else if entry.launch_if_not_running && !entry.install_path.is_empty() {
        let _ = launch_app(&entry.install_path);
    }
}
