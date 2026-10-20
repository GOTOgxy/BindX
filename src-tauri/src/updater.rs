use reqwest::header::USER_AGENT;
use serde::{Deserialize, Serialize};
use std::time::Duration;
use tauri::Emitter;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateCheckResult {
    pub has_update: bool,
    pub current_version: String,
    pub latest_version: String,
    pub release_name: String,
    pub release_notes: String,
    pub published_at: String,
    pub download_url: String,
    pub setup_download_url: String,
    pub release_page_url: String,
}

/// How this copy of BindX was deployed. Updates apply differently per mode:
/// portable replaces the running exe in place, installed re-runs the silent installer.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum InstallMode {
    Portable,
    Installed,
}

const UNINSTALL_REG_KEY: &str =
    "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\BindX_is1";

fn normalize_path(p: &std::path::Path) -> String {
    p.to_string_lossy()
        .replace('/', "\\")
        .trim_end_matches('\\')
        .to_lowercase()
}

/// Read InstallLocation from the Inno Setup uninstall entry (HKCU, user-level install).
fn read_uninstall_install_location() -> Option<String> {
    use std::os::windows::ffi::OsStringExt;
    use windows::Win32::System::Registry::{
        RegCloseKey, RegOpenKeyExW, RegQueryValueExW, HKEY, HKEY_CURRENT_USER, KEY_READ, REG_SZ,
    };
    let key_wide: Vec<u16> = UNINSTALL_REG_KEY.encode_utf16().chain(std::iter::once(0)).collect();
    let value_wide: Vec<u16> = "InstallLocation".encode_utf16().chain(std::iter::once(0)).collect();
    unsafe {
        let mut hkey = HKEY::default();
        if RegOpenKeyExW(
            HKEY_CURRENT_USER,
            windows::core::PCWSTR(key_wide.as_ptr()),
            0,
            KEY_READ,
            &mut hkey,
        )
        .is_err()
        {
            return None;
        }
        let mut buf = [0u16; 260];
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
        let _ = RegCloseKey(hkey);
        if status.is_ok() && cb_data > 0 {
            let len = (cb_data as usize / 2).saturating_sub(1);
            return Some(std::ffi::OsString::from_wide(&buf[..len]).to_string_lossy().to_string());
        }
        None
    }
}

pub fn detect_install_mode() -> InstallMode {
    let exe_dir = match std::env::current_exe().ok().and_then(|p| p.parent().map(|d| d.to_path_buf())) {
        Some(d) => d,
        None => return InstallMode::Portable,
    };
    let exe_dir_n = normalize_path(&exe_dir);

    // The uninstall entry written by our Inno Setup installer is authoritative.
    if let Some(location) = read_uninstall_install_location() {
        if normalize_path(std::path::Path::new(&location)) == exe_dir_n {
            return InstallMode::Installed;
        }
    }

    // Fallback: the default user-level install directory.
    if let Some(local_app_data) = dirs::data_local_dir() {
        let default_dir = local_app_data.join("Programs").join("BindX");
        if normalize_path(&default_dir) == exe_dir_n {
            return InstallMode::Installed;
        }
    }

    InstallMode::Portable
}

#[derive(Debug, Deserialize)]
struct GithubAsset {
    name: String,
    browser_download_url: String,
}

#[derive(Debug, Deserialize)]
struct GithubRelease {
    tag_name: String,
    name: Option<String>,
    body: Option<String>,
    html_url: String,
    published_at: Option<String>,
    #[serde(default)]
    assets: Vec<GithubAsset>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateProgress {
    pub status: String, // "downloading" | "applying" | "done" | "error"
    pub percent: f64,
    pub downloaded_bytes: u64,
    pub total_bytes: u64,
    pub message: String,
}

pub async fn check_for_updates(update_url: &str) -> Result<UpdateCheckResult, String> {
    let current_version = env!("CARGO_PKG_VERSION").to_string();
    let url = if update_url.trim().is_empty() {
        "https://api.github.com/repos/GOTOgxy/BindX/releases/latest"
    } else {
        update_url.trim()
    };

    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(15))
        .build()
        .unwrap_or_default();

    let res = client
        .get(url)
        .header(USER_AGENT, "BindX-App")
        .send()
        .await
        .map_err(|e| format!("检查更新网络请求失败: {}", e))?;

    if res.status() == reqwest::StatusCode::NOT_FOUND {
        // GitHub returns 404 when no releases have been published to the repository yet
        return Ok(UpdateCheckResult {
            has_update: false,
            current_version: format!("v{}", current_version),
            latest_version: format!("v{}", current_version),
            release_name: "当前已是最新".to_string(),
            release_notes: "云端仓库暂无新发布的 Release 版本，当前本地运行版本为最新。".to_string(),
            published_at: String::new(),
            download_url: String::new(),
            setup_download_url: String::new(),
            release_page_url: "https://github.com/GOTOgxy/BindX/releases".to_string(),
        });
    }

    if !res.status().is_success() {
        return Err(format!("检查更新失败，服务器返回: HTTP {}", res.status().as_u16()));
    }

    let release: GithubRelease = res
        .json()
        .await
        .map_err(|e| format!("解析版本信息失败: {}", e))?;

    let latest_tag = release.tag_name.trim().trim_start_matches('v');
    let has_update = compare_semver(latest_tag, &current_version);

    // Strictly prioritize bindx.exe first, then any .exe, and only fallback to .zip
    let exe_asset = release
        .assets
        .iter()
        .find(|a| a.name.eq_ignore_ascii_case("bindx.exe"))
        .or_else(|| release.assets.iter().find(|a| a.name.ends_with(".exe")))
        .or_else(|| release.assets.iter().find(|a| a.name.ends_with(".zip")));

    let download_url = exe_asset
        .map(|a| a.browser_download_url.clone())
        .unwrap_or_else(|| release.html_url.clone());

    let setup_download_url = release
        .assets
        .iter()
        .find(|a| a.name.eq_ignore_ascii_case("bindx-setup.exe"))
        .map(|a| a.browser_download_url.clone())
        .unwrap_or_default();

    Ok(UpdateCheckResult {
        has_update,
        current_version: format!("v{}", current_version),
        latest_version: format!("v{}", latest_tag),
        release_name: release.name.unwrap_or_else(|| release.tag_name.clone()),
        release_notes: release.body.unwrap_or_default(),
        published_at: release.published_at.unwrap_or_default(),
        download_url,
        setup_download_url,
        release_page_url: release.html_url,
    })
}

/// Stream `url` into `dest`, emitting update-progress events along the way.
/// Returns the final file size after a sanity check.
async fn download_with_progress<R: tauri::Runtime>(
    app: &tauri::AppHandle<R>,
    url: &str,
    dest: &std::path::Path,
) -> Result<u64, String> {
    use std::io::Write;

    if dest.exists() {
        let _ = std::fs::remove_file(dest);
    }

    let _ = app.emit("update-progress", UpdateProgress {
        status: "downloading".to_string(),
        percent: 0.0,
        downloaded_bytes: 0,
        total_bytes: 0,
        message: "正在连接更新服务器...".to_string(),
    });

    let client = reqwest::Client::builder()
        .connect_timeout(Duration::from_secs(30))
        .build()
        .map_err(|e| format!("创建网络客户端失败: {}", e))?;

    let mut res = client
        .get(url)
        .header(USER_AGENT, "BindX-App")
        .send()
        .await
        .map_err(|e| {
            let err = format!("请求下载失败: {}", e);
            let _ = app.emit("update-progress", UpdateProgress {
                status: "error".to_string(),
                percent: 0.0,
                downloaded_bytes: 0,
                total_bytes: 0,
                message: err.clone(),
            });
            err
        })?;

    if !res.status().is_success() {
        let err = format!("下载失败，服务器返回 HTTP {}", res.status().as_u16());
        let _ = app.emit("update-progress", UpdateProgress {
            status: "error".to_string(),
            percent: 0.0,
            downloaded_bytes: 0,
            total_bytes: 0,
            message: err.clone(),
        });
        return Err(err);
    }

    let total_bytes = res.content_length().unwrap_or(0);
    let mut downloaded_bytes: u64 = 0;

    let mut file = std::fs::File::create(dest)
        .map_err(|e| {
            let err = format!("无法创建临时文件 ({}): {}", dest.display(), e);
            let _ = app.emit("update-progress", UpdateProgress {
                status: "error".to_string(),
                percent: 0.0,
                downloaded_bytes: 0,
                total_bytes,
                message: err.clone(),
            });
            err
        })?;

    let mut last_emit_percent = -1;
    let mut last_emit_time = std::time::Instant::now();

    while let Some(chunk) = res.chunk().await.map_err(|e| {
        let err = format!("数据传输中断: {}", e);
        let _ = app.emit("update-progress", UpdateProgress {
            status: "error".to_string(),
            percent: 0.0,
            downloaded_bytes,
            total_bytes,
            message: err.clone(),
        });
        err
    })? {
        file.write_all(&chunk).map_err(|e| format!("写入文件失败: {}", e))?;
        downloaded_bytes += chunk.len() as u64;

        let percent = if total_bytes > 0 {
            (downloaded_bytes as f64 / total_bytes as f64) * 100.0
        } else {
            0.0
        };

        let current_percent_int = percent as i32;
        if current_percent_int != last_emit_percent || last_emit_time.elapsed().as_millis() > 150 {
            last_emit_percent = current_percent_int;
            last_emit_time = std::time::Instant::now();

            let mb_down = downloaded_bytes as f64 / 1_048_576.0;
            let mb_total = total_bytes as f64 / 1_048_576.0;
            let msg = if total_bytes > 0 {
                format!("已下载 {:.1} MB / {:.1} MB ({:.0}%)", mb_down, mb_total, percent)
            } else {
                format!("已下载 {:.1} MB", mb_down)
            };

            let _ = app.emit("update-progress", UpdateProgress {
                status: "downloading".to_string(),
                percent: (percent * 10.0).round() / 10.0,
                downloaded_bytes,
                total_bytes,
                message: msg,
            });
        }
    }

    file.flush().map_err(|e| format!("保存文件失败: {}", e))?;
    drop(file);

    // Verify downloaded file size
    let meta = std::fs::metadata(dest)
        .map_err(|e| format!("读取已下载文件元信息失败: {}", e))?;
    if meta.len() < 1_000_000 {
        let _ = std::fs::remove_file(dest);
        let err = format!("下载文件异常 (大小仅 {} 字节)，可能下载不完整", meta.len());
        let _ = app.emit("update-progress", UpdateProgress {
            status: "error".to_string(),
            percent: 0.0,
            downloaded_bytes: meta.len(),
            total_bytes,
            message: err.clone(),
        });
        return Err(err);
    }

    Ok(meta.len())
}

/// Installed-mode update: fetch the silent installer, run it over the original
/// directory, then exit so the installer can replace the running executable.
/// The installer relaunches BindX afterwards; config lives in %APPDATA% and is untouched.
async fn install_via_setup<R: tauri::Runtime>(
    app: tauri::AppHandle<R>,
    setup_url: String,
) -> Result<(), String> {
    use std::os::windows::process::CommandExt;
    const DETACHED_PROCESS: u32 = 0x00000008;
    const CREATE_NO_WINDOW: u32 = 0x08000000;

    let setup_path = std::env::temp_dir().join("bindx-setup-update.exe");
    let size = download_with_progress(&app, &setup_url, &setup_path).await?;

    let _ = app.emit("update-progress", UpdateProgress {
        status: "applying".to_string(),
        percent: 100.0,
        downloaded_bytes: size,
        total_bytes: size,
        message: "下载完成，正在启动静默安装程序...".to_string(),
    });

    let spawned = std::process::Command::new(&setup_path)
        .args(["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"])
        .creation_flags(DETACHED_PROCESS | CREATE_NO_WINDOW)
        .spawn();

    match spawned {
        Ok(_) => {
            let _ = app.emit("update-progress", UpdateProgress {
                status: "done".to_string(),
                percent: 100.0,
                downloaded_bytes: size,
                total_bytes: size,
                message: "安装程序已启动，BindX 即将自动退出并完成覆盖安装（配置完整保留）...".to_string(),
            });
            // Give the progress event a moment to reach the webview before exiting.
            std::thread::sleep(Duration::from_millis(600));
            app.exit(0);
            Ok(())
        }
        Err(e) => {
            let _ = std::fs::remove_file(&setup_path);
            let err = format!("启动安装程序失败: {}", e);
            let _ = app.emit("update-progress", UpdateProgress {
                status: "error".to_string(),
                percent: 0.0,
                downloaded_bytes: size,
                total_bytes: size,
                message: err.clone(),
            });
            Err(err)
        }
    }
}

pub async fn download_and_install_update<R: tauri::Runtime>(
    app: tauri::AppHandle<R>,
    download_url: String,
    setup_download_url: Option<String>,
) -> Result<(), String> {
    // Installed deployments update by re-running the silent installer over the
    // original directory; portable deployments keep the in-place exe swap.
    if detect_install_mode() == InstallMode::Installed {
        if let Some(setup_url) = setup_download_url.filter(|s| !s.trim().is_empty()) {
            return install_via_setup(app, setup_url).await;
        }
    }

    let current_exe = std::env::current_exe().map_err(|e| format!("无法定位当前程序路径: {}", e))?;
    let exe_dir = current_exe.parent().ok_or_else(|| "无法获取程序所在目录".to_string())?;
    let temp_file = exe_dir.join("bindx_update.tmp");

    let total = download_with_progress(&app, &download_url, &temp_file).await?;

    let _ = app.emit("update-progress", UpdateProgress {
        status: "applying".to_string(),
        percent: 100.0,
        downloaded_bytes: total,
        total_bytes: total,
        message: "下载完成，正在替换程序文件...".to_string(),
    });

    let old_exe = current_exe.with_extension("old");
    if old_exe.exists() {
        let _ = std::fs::remove_file(&old_exe);
    }

    // Rename current running executable to .old
    if let Err(e) = std::fs::rename(&current_exe, &old_exe) {
        let _ = std::fs::remove_file(&temp_file);
        let err = format!("备份原程序失败 (可能是权限受限): {}", e);
        let _ = app.emit("update-progress", UpdateProgress {
            status: "error".to_string(),
            percent: 0.0,
            downloaded_bytes: total,
            total_bytes: total,
            message: err.clone(),
        });
        return Err(err);
    }

    // Move downloaded temp file to current_exe
    if let Err(e) = std::fs::rename(&temp_file, &current_exe) {
        // Rollback
        let _ = std::fs::rename(&old_exe, &current_exe);
        let err = format!("替换新版本失败 (已自动回滚为原版本): {}", e);
        let _ = app.emit("update-progress", UpdateProgress {
            status: "error".to_string(),
            percent: 0.0,
            downloaded_bytes: total,
            total_bytes: total,
            message: err.clone(),
        });
        return Err(err);
    }

    let _ = app.emit("update-progress", UpdateProgress {
        status: "done".to_string(),
        percent: 100.0,
        downloaded_bytes: total,
        total_bytes: total,
        message: "更新已成功就绪！点击立即重启生效。".to_string(),
    });

    Ok(())
}

fn compare_semver(remote: &str, current: &str) -> bool {
    let r_parts: Vec<u64> = remote.split('.').filter_map(|s| s.parse().ok()).collect();
    let c_parts: Vec<u64> = current.split('.').filter_map(|s| s.parse().ok()).collect();

    for i in 0..r_parts.len().max(c_parts.len()) {
        let r = r_parts.get(i).copied().unwrap_or(0);
        let c = c_parts.get(i).copied().unwrap_or(0);
        if r > c {
            return true;
        } else if r < c {
            return false;
        }
    }
    false
}
