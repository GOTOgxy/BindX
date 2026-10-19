use crate::autostart::{is_autostart_enabled, set_autostart};
use crate::config::{load_config, save_config, BindxConfig, WebDavConfig};
use crate::engine::{HotkeyEngine, RemapEngine};
use crate::updater::{check_for_updates, UpdateCheckResult};
use crate::webdav::WebDavClient;
use serde::Serialize;
use std::sync::Arc;
use tauri::State;

pub struct AppState {
    pub hotkey_engine: Arc<HotkeyEngine>,
    pub remap_engine: Arc<RemapEngine>,
}

#[derive(Serialize)]
pub struct EngineStatus {
    pub hotkey_running: bool,
    pub mouse_running: bool,
    pub autostart: bool,
}

#[tauri::command]
pub fn get_config() -> Result<BindxConfig, String> {
    Ok(load_config())
}

#[tauri::command]
pub fn update_config(state: State<'_, AppState>, new_config: BindxConfig) -> Result<(), String> {
    save_config(&new_config)?;

    // Sync autostart
    let _ = set_autostart(new_config.app.autostart_enabled);

    // Reload engines
    if new_config.app.hotkey_running {
        state.hotkey_engine.start(new_config.hotkeys.entries.clone());
    } else {
        state.hotkey_engine.stop();
    }

    if new_config.app.mouse_running {
        state.remap_engine.start(new_config.mouse.clone());
    } else {
        state.remap_engine.stop();
    }

    Ok(())
}

#[tauri::command]
pub fn toggle_hotkey_engine(state: State<'_, AppState>, enable: bool) -> Result<bool, String> {
    let mut cfg = load_config();
    cfg.app.hotkey_running = enable;
    save_config(&cfg)?;

    if enable {
        state.hotkey_engine.start(cfg.hotkeys.entries);
    } else {
        state.hotkey_engine.stop();
    }

    Ok(enable)
}

#[tauri::command]
pub fn toggle_mouse_engine(state: State<'_, AppState>, enable: bool) -> Result<bool, String> {
    let mut cfg = load_config();
    cfg.app.mouse_running = enable;
    save_config(&cfg)?;

    if enable {
        state.remap_engine.start(cfg.mouse);
    } else {
        state.remap_engine.stop();
    }

    Ok(enable)
}

#[tauri::command]
pub fn get_engine_status(state: State<'_, AppState>) -> EngineStatus {
    EngineStatus {
        hotkey_running: state.hotkey_engine.is_running(),
        mouse_running: state.remap_engine.is_running(),
        autostart: is_autostart_enabled(),
    }
}

#[tauri::command]
pub async fn test_webdav(config: WebDavConfig) -> Result<String, String> {
    let client = WebDavClient::new();
    client.test_connection(&config).await
}

#[tauri::command]
pub async fn upload_to_webdav(config: WebDavConfig) -> Result<String, String> {
    let current_cfg = load_config();
    let json_str = serde_json::to_string_pretty(&current_cfg)
        .map_err(|e| format!("序列化配置失败: {}", e))?;

    let client = WebDavClient::new();
    client.upload_config(&config, &json_str).await
}

#[tauri::command]
pub async fn download_from_webdav(
    state: State<'_, AppState>,
    config: WebDavConfig,
) -> Result<BindxConfig, String> {
    let client = WebDavClient::new();
    let downloaded_cfg = client.download_config(&config).await?;

    // Reload hotkeys & mouse remap with downloaded config
    if downloaded_cfg.app.hotkey_running {
        state.hotkey_engine.start(download_cfg(&downloaded_cfg));
    } else {
        state.hotkey_engine.stop();
    }

    if downloaded_cfg.app.mouse_running {
        state.remap_engine.start(downloaded_cfg.mouse.clone());
    } else {
        state.remap_engine.stop();
    }

    let _ = set_autostart(downloaded_cfg.app.autostart_enabled);

    Ok(downloaded_cfg)
}

fn download_cfg(cfg: &BindxConfig) -> Vec<crate::config::HotkeyEntry> {
    cfg.hotkeys.entries.clone()
}

#[tauri::command]
pub async fn check_software_update(update_url: Option<String>) -> Result<UpdateCheckResult, String> {
    let cfg = load_config();
    let url = update_url.unwrap_or(cfg.updater.update_url);
    check_for_updates(&url).await
}

#[tauri::command]
pub fn open_external_url(url: String) -> Result<(), String> {
    open::that(&url).map_err(|e| format!("打开链接失败: {}", e))?;
    Ok(())
}

#[tauri::command]
pub fn drag_window(window: tauri::WebviewWindow) -> Result<(), String> {
    window.start_dragging().map_err(|e| e.to_string())
}
