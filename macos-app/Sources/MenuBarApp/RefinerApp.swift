import RefinerCore
import SwiftUI

@main
struct RefinerApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate

    var body: some Scene {
        // 응용 프로그램에서 직접 실행하면 중앙에 표시되는 로그인 창
        WindowGroup {
            RootView()
        }
        .windowResizability(.contentSize)

        // 메뉴바 상주 아이콘
        MenuBarExtra {
            PopoverView()
        } label: {
            Image(systemName: "wand.and.stars")
        }
        .menuBarExtraStyle(.window)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        AppFont.registerAll()
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)

        // 백엔드 서버 자동 기동 (이미 살아있으면 재사용)
        ServerManager.shared.bootstrap()
    }

    func applicationWillTerminate(_ notification: Notification) {
        // 앱이 직접 띄운 서버만 정리
        ServerManager.shared.shutdown()
    }
}
