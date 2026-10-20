use crate::autostart::{is_autostart_enabled, set_autostart};
use crate::config::{get_config_path, load_config, save_config, BindxConfig, WebDavConfig};
use crate::engine::{HotkeyEngine, RemapEngine};
use crate::updater::{check_for_updates, UpdateCheckResult};
use crate::webdav::WebDavClient;
use serde::{Deserialize, Serialize};
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
pub fn select_executable_file() -> Result<Option<String>, String> {
    #[repr(C)]
    struct OPENFILENAMEW {
        l_struct_size: u32,
        hwnd_owner: isize,
        h_instance: isize,
        lpstr_filter: *const u16,
        lpstr_custom_filter: *mut u16,
        n_max_cust_filter: u32,
        n_filter_index: u32,
        lpstr_file: *mut u16,
        n_max_file: u32,
        lpstr_file_title: *mut u16,
        n_max_file_title: u32,
        lpstr_initial_dir: *const u16,
        lpstr_title: *const u16,
        flags: u32,
        n_file_offset: u16,
        n_file_extension: u16,
        lpstr_def_ext: *const u16,
        l_cust_data: isize,
        lpfn_hook: usize,
        lp_template_name: *const u16,
        pv_reserved: usize,
        dw_reserved: u32,
        flags_ex: u32,
    }

    #[link(name = "comdlg32")]
    extern "system" {
        fn GetOpenFileNameW(lpofn: *mut OPENFILENAMEW) -> i32;
    }

    use std::ffi::OsString;
    use std::os::windows::ffi::OsStringExt;

    let mut file_buf = vec![0u16; 1024];
    let filter: Vec<u16> = "应用程序 (*.exe)\0*.exe\0所有文件 (*.*)\0*.*\0\0"
        .encode_utf16()
        .collect();
    let title: Vec<u16> = "选择应用程序可执行文件\0".encode_utf16().collect();
    let def_ext: Vec<u16> = "exe\0".encode_utf16().collect();

    let mut ofn = OPENFILENAMEW {
        l_struct_size: std::mem::size_of::<OPENFILENAMEW>() as u32,
        hwnd_owner: 0,
        h_instance: 0,
        lpstr_filter: filter.as_ptr(),
        lpstr_custom_filter: std::ptr::null_mut(),
        n_max_cust_filter: 0,
        n_filter_index: 1,
        lpstr_file: file_buf.as_mut_ptr(),
        n_max_file: file_buf.len() as u32,
        lpstr_file_title: std::ptr::null_mut(),
        n_max_file_title: 0,
        lpstr_initial_dir: std::ptr::null(),
        lpstr_title: title.as_ptr(),
        flags: 0x00081800, // OFN_EXPLORER | OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST
        n_file_offset: 0,
        n_file_extension: 0,
        lpstr_def_ext: def_ext.as_ptr(),
        l_cust_data: 0,
        lpfn_hook: 0,
        lp_template_name: std::ptr::null(),
        pv_reserved: 0,
        dw_reserved: 0,
        flags_ex: 0,
    };

    let ret = unsafe { GetOpenFileNameW(&mut ofn) };
    if ret != 0 {
        let len = file_buf.iter().position(|&c| c == 0).unwrap_or(file_buf.len());
        Ok(Some(
            OsString::from_wide(&file_buf[..len])
                .to_string_lossy()
                .to_string(),
        ))
    } else {
        Ok(None)
    }
}

#[tauri::command]
pub fn set_recording_state(state: tauri::State<'_, AppState>, active: bool) -> Result<(), String> {
    if active {
        state.hotkey_engine.pause();
        state.remap_engine.set_recording_paused(true);
    } else {
        state.hotkey_engine.resume();
        state.remap_engine.set_recording_paused(false);
    }
    Ok(())
}

use std::os::windows::process::CommandExt;
const CREATE_NO_WINDOW: u32 = 0x08000000;

fn get_start_menu_shortcut_path() -> Result<std::path::PathBuf, String> {
    let data_dir = dirs::data_dir().ok_or_else(|| "无法获取 AppData 路径".to_string())?;
    Ok(data_dir.join("Microsoft\\Windows\\Start Menu\\Programs\\BindX.lnk"))
}

fn create_shortcut_internal(target_exe: &std::path::Path, shortcut_path: &std::path::Path, desc: &str) -> Result<(), String> {
    if let Some(parent) = shortcut_path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let work_dir = target_exe.parent().unwrap_or(std::path::Path::new(""));
    let script = format!(
        "$w = New-Object -ComObject WScript.Shell; \
         $s = $w.CreateShortcut('{}'); \
         $s.TargetPath = '{}'; \
         $s.WorkingDirectory = '{}'; \
         $s.IconLocation = '{},0'; \
         $s.Description = '{}'; \
         $s.Save()",
        shortcut_path.to_string_lossy().replace('\'', "''"),
        target_exe.to_string_lossy().replace('\'', "''"),
        work_dir.to_string_lossy().replace('\'', "''"),
        target_exe.to_string_lossy().replace('\'', "''"),
        desc.replace('\'', "''")
    );

    let output = std::process::Command::new("powershell")
        .creation_flags(CREATE_NO_WINDOW)
        .arg("-NoProfile")
        .arg("-Command")
        .arg(&script)
        .output()
        .map_err(|e| format!("执行 PowerShell 创建快捷方式失败: {}", e))?;

    if output.status.success() {
        Ok(())
    } else {
        Err(String::from_utf8_lossy(&output.stderr).to_string())
    }
}

#[tauri::command]
pub fn check_start_menu_status() -> Result<bool, String> {
    let path = get_start_menu_shortcut_path()?;
    Ok(path.exists())
}

#[tauri::command]
pub fn toggle_start_menu_shortcut(enable: bool) -> Result<bool, String> {
    let path = get_start_menu_shortcut_path()?;
    if enable {
        let current_exe = std::env::current_exe().map_err(|e| format!("获取程序路径失败: {}", e))?;
        create_shortcut_internal(&current_exe, &path, "BindX - 快捷键与按键映射管理器")?;
        Ok(true)
    } else {
        if path.exists() {
            let _ = std::fs::remove_file(&path);
        }
        Ok(false)
    }
}

#[tauri::command]
pub fn locate_start_menu_shortcut() -> Result<(), String> {
    let path = get_start_menu_shortcut_path()?;
    if !path.exists() {
        let current_exe = std::env::current_exe().map_err(|e| format!("获取程序路径失败: {}", e))?;
        create_shortcut_internal(&current_exe, &path, "BindX - 快捷键与按键映射管理器")?;
    }
    let arg = format!("/select,\"{}\"", path.to_string_lossy());
    let _ = std::process::Command::new("explorer")
        .arg(&arg)
        .spawn();
    Ok(())
}

#[tauri::command]
pub fn create_desktop_shortcut() -> Result<(), String> {
    let desktop_dir = dirs::desktop_dir().ok_or_else(|| "无法获取桌面路径".to_string())?;
    let path = desktop_dir.join("BindX.lnk");
    let current_exe = std::env::current_exe().map_err(|e| format!("获取程序路径失败: {}", e))?;
    create_shortcut_internal(&current_exe, &path, "BindX - 快捷键与按键映射管理器")?;
    Ok(())
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConfigPathInfo {
    pub full_path: String,
    pub dir_path: String,
    pub exists: bool,
}

#[tauri::command]
pub fn get_config_path_info() -> Result<ConfigPathInfo, String> {
    let path = get_config_path();
    let path_str = path.to_string_lossy().to_string();
    let clean_path = if path_str.starts_with(r"\\?\") {
        path_str[4..].to_string()
    } else {
        path_str
    };
    let dir = std::path::PathBuf::from(&clean_path)
        .parent()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_default();

    Ok(ConfigPathInfo {
        full_path: clean_path,
        dir_path: dir,
        exists: path.exists(),
    })
}

#[tauri::command]
pub fn open_config_folder() -> Result<(), String> {
    let path = get_config_path();
    let path_str = path.to_string_lossy().to_string();
    let clean_path = if path_str.starts_with(r"\\?\") {
        path_str[4..].to_string()
    } else {
        path_str
    };

    let p = std::path::PathBuf::from(&clean_path);
    if let Some(parent) = p.parent() {
        let _ = std::fs::create_dir_all(parent);
    }

    // If config file does not exist yet on disk, save the current configuration
    if !p.exists() {
        let cfg = load_config();
        let _ = save_config(&cfg);
    }

    #[cfg(windows)]
    {
        use std::process::Command;
        if p.exists() {
            let arg = format!("/select,\"{}\"", clean_path);
            let _ = Command::new("explorer").arg(&arg).spawn();
            return Ok(());
        }
    }

    let dir = p.parent().unwrap_or(&p);
    open::that(dir).map_err(|e| format!("打开配置文件目录失败: {}", e))?;
    Ok(())
}


#[tauri::command]
pub async fn start_auto_update(
    app: tauri::AppHandle,
    download_url: String,
) -> Result<(), String> {
    crate::updater::download_and_install_update(app, download_url).await
}

#[tauri::command]
pub fn restart_app() -> Result<(), String> {
    let current_exe = std::env::current_exe().map_err(|e| format!("获取程序路径失败: {}", e))?;

    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        let script = format!(
            "Start-Sleep -Milliseconds 600; Start-Process -FilePath '{}'",
            current_exe.to_string_lossy().replace('\'', "''")
        );
        let _ = std::process::Command::new("powershell")
            .creation_flags(CREATE_NO_WINDOW)
            .arg("-NoProfile")
            .arg("-Command")
            .arg(&script)
            .spawn();
    }

    #[cfg(not(windows))]
    {
        let _ = std::process::Command::new(&current_exe).spawn();
    }

    std::process::exit(0);
}
