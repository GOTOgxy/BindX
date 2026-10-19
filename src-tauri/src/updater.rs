use reqwest::header::USER_AGENT;
use serde::{Deserialize, Serialize};
use std::time::Duration;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateCheckResult {
    pub has_update: bool,
    pub current_version: String,
    pub latest_version: String,
    pub release_name: String,
    pub release_notes: String,
    pub published_at: String,
    pub download_url: String,
    pub release_page_url: String,
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

pub async fn check_for_updates(update_url: &str) -> Result<UpdateCheckResult, String> {
    let current_version = env!("CARGO_PKG_VERSION").to_string();
    let url = if update_url.trim().is_empty() {
        "https://api.github.com/repos/GOTOgxy/BindX/releases/latest"
    } else {
        update_url.trim()
    };

    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(10))
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

    // Prefer .exe or .zip from release assets
    let exe_asset = release.assets.iter().find(|a| {
        a.name.ends_with(".exe") || a.name.ends_with(".zip")
    });

    let download_url = exe_asset
        .map(|a| a.browser_download_url.clone())
        .unwrap_or_else(|| release.html_url.clone());

    Ok(UpdateCheckResult {
        has_update,
        current_version: format!("v{}", current_version),
        latest_version: format!("v{}", latest_tag),
        release_name: release.name.unwrap_or_else(|| release.tag_name.clone()),
        release_notes: release.body.unwrap_or_default(),
        published_at: release.published_at.unwrap_or_default(),
        download_url,
        release_page_url: release.html_url,
    })
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
