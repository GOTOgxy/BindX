// Dev probe: print title + AppUserModelID for visible windows.
// Run from repo root (needs WebView2Loader.dll beside it).
use windows::Win32::Foundation::{BOOL, HWND, LPARAM};
use windows::Win32::UI::Shell::PropertiesSystem::{SHGetPropertyStoreForWindow, IPropertyStore, PROPERTYKEY};
use windows::Win32::UI::WindowsAndMessaging::{
    EnumWindows, GetWindowTextLengthW, GetWindowTextW, IsWindowVisible,
};

// PKEY_AppUserModel_ID = {9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}, 5
fn pkey_aumid() -> PROPERTYKEY {
    PROPERTYKEY {
        fmtid: windows::core::GUID::from_u128(0x9F4C2855_9F79_4B39_A8D0_E1D42DE1D5F3),
        pid: 5,
    }
}

unsafe extern "system" fn proc(hwnd: HWND, _lparam: LPARAM) -> BOOL {
    if !IsWindowVisible(hwnd).as_bool() {
        return BOOL(1);
    }
    let len = GetWindowTextLengthW(hwnd);
    if len == 0 {
        return BOOL(1);
    }
    let mut buf = vec![0u16; len as usize + 1];
    let got = GetWindowTextW(hwnd, &mut buf);
    if got == 0 {
        return BOOL(1);
    }
    let title = String::from_utf16_lossy(&buf[..got as usize]);
    let aumid: Option<String> = (|| {
        let store: IPropertyStore = SHGetPropertyStoreForWindow(hwnd).ok()?;
        let key = pkey_aumid();
        let v = store.GetValue(&key as *const PROPERTYKEY).ok()?;
        let r = v.as_raw();
        let vt = r.Anonymous.Anonymous.vt;
        if vt != 8 && vt != 31 {
            return Some(String::new());
        }
        let p = r.Anonymous.Anonymous.Anonymous.bstrVal as *const u16;
        if p.is_null() {
            return Some(String::new());
        }
        let mut n = 0usize;
        while *p.add(n) != 0 {
            n += 1;
        }
        Some(String::from_utf16_lossy(std::slice::from_raw_parts(p, n)))
    })();
    println!("title={:?} aumid={:?}", title, aumid);
    BOOL(1)
}

unsafe extern "system" fn close_proc(hwnd: HWND, lparam: LPARAM) -> BOOL {
    let needle = &*(lparam.0 as *const String);
    if !IsWindowVisible(hwnd).as_bool() {
        return BOOL(1);
    }
    let len = GetWindowTextLengthW(hwnd);
    if len == 0 {
        return BOOL(1);
    }
    let mut buf = vec![0u16; len as usize + 1];
    let got = GetWindowTextW(hwnd, &mut buf);
    if got == 0 {
        return BOOL(1);
    }
    let title = String::from_utf16_lossy(&buf[..got as usize]);
    if title.contains(needle.as_str()) {
        let _ = windows::Win32::UI::WindowsAndMessaging::PostMessageW(
            hwnd,
            windows::Win32::UI::WindowsAndMessaging::WM_CLOSE,
            None,
            LPARAM(0),
        );
        println!("closed {:?}", title);
    }
    BOOL(1)
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    unsafe {
        if args.len() > 2 && args[1] == "close" {
            let _ = EnumWindows(Some(close_proc), LPARAM(&args[2] as *const String as isize));
        } else {
            let _ = EnumWindows(Some(proc), LPARAM(0));
        }
    }
}
