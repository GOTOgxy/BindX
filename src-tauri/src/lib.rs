pub mod autostart;
pub mod commands;
pub mod config;
pub mod engine;
pub mod tray;
pub mod updater;
pub mod webdav;

use commands::*;
use config::load_config;
use engine::{HotkeyEngine, RemapEngine};
use std::sync::Arc;
use tauri::{Manager, WindowEvent};

pub fn log_panic(info: &std::panic::PanicHookInfo) {
    use std::fs::OpenOptions;
    use std::io::Write;
    let msg = if let Some(s) = info.payload().downcast_ref::<&str>() {
        s.to_string()
    } else if let Some(s) = info.payload().downcast_ref::<String>() {
        s.clone()
    } else {
        format!("{:?}", info)
    };
    if msg.contains("0x800700AA") || msg.contains("请求的资源在使用中") {
        return;
    }
    let loc = info.location().map(|l| format!("{}:{}:{}", l.file(), l.line(), l.column())).unwrap_or_default();
    if let Ok(mut f) = OpenOptions::new().create(true).append(true).open("bindx_error.log") {
        let _ = writeln!(f, "[PANIC at {}] {}", loc, msg);
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    std::panic::set_hook(Box::new(|info| {
        log_panic(info);
    }));

    let cfg = load_config();

    let hotkey_engine = Arc::new(HotkeyEngine::new());
    let remap_engine = Arc::new(RemapEngine::new());

    let hotkey_engine_clone = hotkey_engine.clone();
    let remap_engine_clone = remap_engine.clone();

    tauri::Builder::default()
        .manage(AppState {
            hotkey_engine: hotkey_engine_clone,
            remap_engine: remap_engine_clone,
        })
        .setup(move |app| {
            // Silently clean up old executable or temp update files from previous update cycles
            if let Ok(exe_path) = std::env::current_exe() {
                let old_exe = exe_path.with_extension("old");
                if old_exe.exists() {
                    let _ = std::fs::remove_file(old_exe);
                }
                if let Some(parent) = exe_path.parent() {
                    let custom_tmp = parent.join("bindx_update.tmp");
                    if custom_tmp.exists() {
                        let _ = std::fs::remove_file(custom_tmp);
                    }
                }
            }

            // Start engines if enabled in configuration
            if cfg.app.hotkey_running {
                hotkey_engine.start(cfg.hotkeys.entries.clone());
            }
            if cfg.app.mouse_running {
                remap_engine.start(cfg.mouse.clone());
            }

            // Setup system tray
            let _ = tray::setup_tray(app.handle());

            // Bind toggle window callback for hotkey engine
            let app_handle = app.handle().clone();
            hotkey_engine.set_toggle_window_handler(move || {
                if let Some(window) = app_handle.get_webview_window("main") {
                    if window.is_visible().unwrap_or(false) {
                        let _ = window.hide();
                    } else {
                        let _ = window.show();
                        let _ = window.unminimize();
                        let _ = window.set_focus();
                    }
                }
            });

            // Show window on launch and prevent window close from exiting app: hide to tray
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.unminimize();
                let _ = window.set_focus();

                let win_clone = window.clone();
                window.on_window_event(move |event| {
                    if let WindowEvent::CloseRequested { api, .. } = event {
                        api.prevent_close();
                        let _ = win_clone.hide();
                    }
                });
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_config,
            update_config,
            toggle_hotkey_engine,
            toggle_mouse_engine,
            get_engine_status,
            test_webdav,
            upload_to_webdav,
            download_from_webdav,
            check_software_update,
            open_external_url,
            select_executable_file,
            set_recording_state,
            check_start_menu_status,
            toggle_start_menu_shortcut,
            locate_start_menu_shortcut,
            create_desktop_shortcut,
            get_config_path_info,
            open_config_folder,
            start_auto_update,
            get_install_mode,
            get_app_version,
            detect_installed_web_app,
            restart_app
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
