use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    #[serde(default = "default_true")]
    pub hotkey_running: bool,
    #[serde(default)]
    pub mouse_running: bool,
    #[serde(default = "default_window_size")]
    pub window_size: String,
    #[serde(default)]
    pub window_zoomed: bool,
    #[serde(default = "default_font_preset")]
    pub font_preset: String,
    #[serde(default = "default_true")]
    pub autostart_enabled: bool,
    #[serde(default = "default_output_delay")]
    pub output_delay_ms: u64,
    #[serde(default = "default_true")]
    pub restore_held_modifiers: bool,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            hotkey_running: true,
            mouse_running: false,
            window_size: default_window_size(),
            window_zoomed: false,
            font_preset: default_font_preset(),
            autostart_enabled: true,
            output_delay_ms: 20,
            restore_held_modifiers: true,
        }
    }
}

fn default_true() -> bool {
    true
}

fn default_window_size() -> String {
    "940x640".to_string()
}

fn default_font_preset() -> String {
    "常规".to_string()
}

fn default_output_delay() -> u64 {
    20
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HotkeyEntry {
    pub app: String,
    pub hotkey: String,
    #[serde(default)]
    pub launch_if_not_running: bool,
    #[serde(default)]
    pub install_path: String,
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default)]
    pub _runtime_profile: serde_json::Value,
    #[serde(default)]
    pub target_type: Option<String>,
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub exe_name: Option<String>,
    #[serde(default)]
    pub title_keyword: Option<String>,
    #[serde(default)]
    pub tray_aware: Option<bool>,
    #[serde(flatten)]
    pub extra: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct HotkeysSection {
    #[serde(default = "default_display_name")]
    pub display_name: String,
    #[serde(default = "default_mutex_name")]
    pub mutex_name: String,
    #[serde(default)]
    pub entries: Vec<HotkeyEntry>,
}

fn default_display_name() -> String {
    "App Hotkey Manager".to_string()
}

fn default_mutex_name() -> String {
    "Global\\AppHotkeyManager".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KeyMapping {
    pub trigger: Vec<String>,
    pub output: Vec<String>,
    #[serde(default)]
    pub description: String,
    #[serde(default = "default_true")]
    pub enabled: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MouseMapping {
    pub button: String, // e.g. "x1", "x2"
    pub output: Vec<String>,
    #[serde(default)]
    pub description: String,
    #[serde(default = "default_true")]
    pub enabled: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct MouseSection {
    #[serde(default)]
    pub mappings: Vec<KeyMapping>,
    #[serde(default)]
    pub mouse_mappings: Vec<MouseMapping>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WebDavConfig {
    #[serde(default)]
    pub server_url: String,
    #[serde(default)]
    pub username: String,
    #[serde(default)]
    pub password: String,
    #[serde(default = "default_remote_filename")]
    pub remote_filename: String,
    #[serde(default)]
    pub auto_sync_on_startup: bool,
}

fn default_remote_filename() -> String {
    "bindx_config.json".to_string()
}

impl Default for WebDavConfig {
    fn default() -> Self {
        Self {
            server_url: String::new(),
            username: String::new(),
            password: String::new(),
            remote_filename: default_remote_filename(),
            auto_sync_on_startup: false,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdaterConfig {
    #[serde(default = "default_true")]
    pub check_on_startup: bool,
    #[serde(default = "default_update_url")]
    pub update_url: String,
}

fn default_update_url() -> String {
    "https://api.github.com/repos/GOTOgxy/BindX/releases/latest".to_string()
}

impl Default for UpdaterConfig {
    fn default() -> Self {
        Self {
            check_on_startup: true,
            update_url: default_update_url(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct BindxConfig {
    #[serde(default)]
    pub app: AppConfig,
    #[serde(default)]
    pub hotkeys: HotkeysSection,
    #[serde(default)]
    pub mouse: MouseSection,
    #[serde(default)]
    pub webdav: WebDavConfig,
    #[serde(default)]
    pub updater: UpdaterConfig,
    #[serde(flatten)]
    pub extra: HashMap<String, serde_json::Value>,
}

pub fn get_config_path() -> PathBuf {
    // 1. Check relative data/bindx_config.json
    let p = PathBuf::from("data/bindx_config.json");
    if p.exists() {
        return p;
    }

    // 2. Check executable directory / data / bindx_config.json
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            let p = parent.join("data").join("bindx_config.json");
            if p.exists() {
                return p;
            }
        }
    }

    // 3. Fallback to AppData / BindX
    if let Some(app_data) = dirs::data_dir() {
        let p = app_data.join("BindX").join("bindx_config.json");
        return p;
    }

    PathBuf::from("bindx_config.json")
}

pub fn load_config() -> BindxConfig {
    let path = get_config_path();
    if let Ok(content) = fs::read_to_string(&path) {
        if let Ok(cfg) = serde_json::from_str::<BindxConfig>(&content) {
            return cfg;
        }
    }
    BindxConfig::default()
}

pub fn save_config(config: &BindxConfig) -> Result<(), String> {
    let path = get_config_path();
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let content = serde_json::to_string_pretty(config)
        .map_err(|e| format!("序列化配置失败: {}", e))?;
    fs::write(&path, content)
        .map_err(|e| format!("写入配置文件失败: {}", e))?;
    Ok(())
}
