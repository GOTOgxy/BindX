use std::ffi::OsStr;
use std::os::windows::ffi::OsStrExt;
use windows::core::PCWSTR;
use windows::Win32::Foundation::ERROR_SUCCESS;
use windows::Win32::System::Registry::{
    RegCloseKey, RegDeleteValueW, RegOpenKeyExW, RegQueryValueExW, RegSetValueExW,
    HKEY_CURRENT_USER, KEY_QUERY_VALUE, KEY_SET_VALUE, REG_SZ,
};

const RUN_KEY: &str = "Software\\Microsoft\\Windows\\CurrentVersion\\Run";
const APP_NAME: &str = "BindX";

fn to_wide_chars(s: &str) -> Vec<u16> {
    OsStr::new(s).encode_wide().chain(std::iter::once(0)).collect()
}

pub fn is_autostart_enabled() -> bool {
    let subkey = to_wide_chars(RUN_KEY);
    let app_val = to_wide_chars(APP_NAME);
    let mut hkey = windows::Win32::System::Registry::HKEY::default();

    unsafe {
        if RegOpenKeyExW(
            HKEY_CURRENT_USER,
            PCWSTR(subkey.as_ptr()),
            0,
            KEY_QUERY_VALUE,
            &mut hkey,
        ) != ERROR_SUCCESS
        {
            return false;
        }

        let mut data_type = REG_SZ;
        let mut data_len = 0u32;
        let status = RegQueryValueExW(
            hkey,
            PCWSTR(app_val.as_ptr()),
            None,
            Some(&mut data_type),
            None,
            Some(&mut data_len),
        );
        let _ = RegCloseKey(hkey);
        status == ERROR_SUCCESS
    }
}

pub fn set_autostart(enable: bool) -> Result<(), String> {
    let subkey = to_wide_chars(RUN_KEY);
    let app_val = to_wide_chars(APP_NAME);
    let mut hkey = windows::Win32::System::Registry::HKEY::default();

    unsafe {
        if RegOpenKeyExW(
            HKEY_CURRENT_USER,
            PCWSTR(subkey.as_ptr()),
            0,
            KEY_SET_VALUE,
            &mut hkey,
        ) != ERROR_SUCCESS
        {
            return Err("无法打开 Windows 注册表开机启动项".to_string());
        }

        let res = if enable {
            let current_exe = std::env::current_exe()
                .map_err(|e| format!("获取程序路径失败: {}", e))?;
            let exe_str = format!("\"{}\"", current_exe.to_string_lossy());
            let exe_wide = to_wide_chars(&exe_str);
            let byte_len = (exe_wide.len() * 2) as u32;

            RegSetValueExW(
                hkey,
                PCWSTR(app_val.as_ptr()),
                0,
                REG_SZ,
                Some(std::slice::from_raw_parts(exe_wide.as_ptr() as *const u8, byte_len as usize)),
            )
        } else {
            RegDeleteValueW(hkey, PCWSTR(app_val.as_ptr()))
        };

        let _ = RegCloseKey(hkey);
        if res == ERROR_SUCCESS || (!enable && res.0 as u32 == 2) /* ERROR_FILE_NOT_FOUND */ {
            Ok(())
        } else {
            Err(format!("注册表操作失败: 错误码 {}", res.0))
        }
    }
}
