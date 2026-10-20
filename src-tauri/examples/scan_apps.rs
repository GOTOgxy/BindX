// Dev helper: print installed browser web apps discovered from Start Menu shortcuts.
// Run: CARGO_TARGET_DIR=D:/bindx-target cargo run --release --example scan_apps
fn main() {
    let apps = bindx::engine::win32::list_installed_web_apps();
    println!("found {} installed web app(s)", apps.len());
    for a in &apps {
        println!(
            "name={} | id={} | profile={} | browser={} | app_url={}",
            a.name, a.id, a.profile, a.browser_exe, a.app_url
        );
    }
    let probe = bindx::engine::win32::find_installed_web_app_for_url(
        "https://www.qianwen.com/",
        &["千问".to_string()],
    );
    println!("probe qianwen url+hint => {:?}", probe.map(|a| a.name));
    let probe2 = bindx::engine::win32::find_installed_web_app_for_url(
        "https://gemini.google.com/u/2/app",
        &["Gemini".to_string()],
    );
    println!("probe gemini url+hint => {:?}", probe2.map(|a| a.name));
}
