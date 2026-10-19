use crate::config::{BindxConfig, WebDavConfig, save_config};
use reqwest::{Client, Method, StatusCode};
use std::time::Duration;

pub struct WebDavClient {
    client: Client,
}

impl WebDavClient {
    pub fn new() -> Self {
        let client = Client::builder()
            .timeout(Duration::from_secs(12))
            .build()
            .unwrap_or_default();
        Self { client }
    }

    fn build_remote_url(cfg: &WebDavConfig) -> Result<String, String> {
        let base = cfg.server_url.trim().trim_end_matches('/');
        if base.is_empty() {
            return Err("WebDAV 服务器地址不能为空".to_string());
        }
        let file = cfg.remote_filename.trim().trim_start_matches('/');
        let file = if file.is_empty() { "bindx_config.json" } else { file };
        Ok(format!("{}/{}", base, file))
    }

    pub async fn test_connection(&self, cfg: &WebDavConfig) -> Result<String, String> {
        let base = cfg.server_url.trim();
        if base.is_empty() {
            return Err("WebDAV 服务器地址不能为空".to_string());
        }

        let mut req = self.client.request(Method::from_bytes(b"PROPFIND").unwrap(), base);
        if !cfg.username.is_empty() {
            req = req.basic_auth(&cfg.username, Some(&cfg.password));
        }
        req = req.header("Depth", "0");

        let res = match req.send().await {
            Ok(r) => r,
            Err(_) => {
                // Try fallback to GET or HEAD if PROPFIND failed (some simple servers don't accept PROPFIND on root)
                let mut fallback_req = self.client.get(base);
                if !cfg.username.is_empty() {
                    fallback_req = fallback_req.basic_auth(&cfg.username, Some(&cfg.password));
                }
                fallback_req.send().await.map_err(|e| format!("无法连接至服务器: {}", e))?
            }
        };

        match res.status() {
            StatusCode::OK | StatusCode::MULTI_STATUS | StatusCode::NO_CONTENT => {
                Ok("WebDAV 连接成功！".to_string())
            }
            StatusCode::UNAUTHORIZED => {
                Err("WebDAV 认证失败 (401)：用户名或密码错误".to_string())
            }
            StatusCode::FORBIDDEN => {
                Err("WebDAV 访问被拒绝 (403)：请检查访问权限".to_string())
            }
            StatusCode::NOT_FOUND => {
                Err("WebDAV 服务器路径不存在 (404)：请检查 URL 路径".to_string())
            }
            status => {
                if status.is_success() {
                    Ok(format!("WebDAV 响应正常 (HTTP {})", status.as_u16()))
                } else {
                    Err(format!("WebDAV 服务器返回错误状态码: HTTP {}", status.as_u16()))
                }
            }
        }
    }

    pub async fn upload_config(&self, cfg: &WebDavConfig, json_str: &str) -> Result<String, String> {
        let url = Self::build_remote_url(cfg)?;
        let mut req = self.client.put(&url)
            .header("Content-Type", "application/json; charset=utf-8")
            .body(json_str.to_string());

        if !cfg.username.is_empty() {
            req = req.basic_auth(&cfg.username, Some(&cfg.password));
        }

        let res = req.send().await.map_err(|e| format!("上传请求发送失败: {}", e))?;
        if res.status().is_success() || res.status() == StatusCode::CREATED || res.status() == StatusCode::NO_CONTENT {
            Ok("配置已成功上传至 WebDAV 云端！".to_string())
        } else {
            Err(format!("上传失败，服务器返回: HTTP {}", res.status().as_u16()))
        }
    }

    pub async fn download_config(&self, cfg: &WebDavConfig) -> Result<BindxConfig, String> {
        let url = Self::build_remote_url(cfg)?;
        let mut req = self.client.get(&url);

        if !cfg.username.is_empty() {
            req = req.basic_auth(&cfg.username, Some(&cfg.password));
        }

        let res = req.send().await.map_err(|e| format!("下载请求发送失败: {}", e))?;
        if !res.status().is_success() {
            return Err(format!("下载配置失败，服务器返回: HTTP {}", res.status().as_u16()));
        }

        let body = res.text().await.map_err(|e| format!("读取响应内容失败: {}", e))?;
        let parsed_config: BindxConfig = serde_json::from_str(&body)
            .map_err(|e| format!("云端配置解析失败（格式不兼容或非合法 JSON）: {}", e))?;

        // Save downloaded config to local disk
        save_config(&parsed_config)?;

        Ok(parsed_config)
    }
}
