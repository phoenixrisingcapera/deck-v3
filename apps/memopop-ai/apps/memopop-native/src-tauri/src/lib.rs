mod api;

use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_store::Builder::new().build())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            app.manage(api::sidecar::SidecarManager::new());
            Ok(())
        })
        .on_window_event(|window, event| {
            // Both `CloseRequested` (user clicks the close button / Cmd+W) and
            // `Destroyed` (OS finalizes window teardown) need to kill the
            // sidecar. Without `CloseRequested`, on macOS the Python child
            // process can outlive a closed window — leaving stale runs holding
            // the port and shipping work to the wrong code path on the next
            // app launch (the bug that wasted hours of runtime today).
            match event {
                tauri::WindowEvent::CloseRequested { .. }
                | tauri::WindowEvent::Destroyed => {
                    if let Some(manager) =
                        window.app_handle().try_state::<api::sidecar::SidecarManager>()
                    {
                        manager.shutdown();
                    }
                }
                _ => {}
            }
        })
        .invoke_handler(tauri::generate_handler![api::router::api_dispatch])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
