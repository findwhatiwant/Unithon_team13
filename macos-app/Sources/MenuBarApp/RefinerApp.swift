import RefinerCore
import SwiftUI

@main
struct RefinerApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate

    var body: some Scene {
        // 응용 프로그램에서 직접 실행하면 중앙에 표시되는 로그인 창
        WindowGroup("로그인") {
            LoginView()
        }
        .windowResizability(.contentSize)

        // 메뉴바 상주 아이콘
        MenuBarExtra {
            PopoverView(viewModel: RefineViewModel())
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
    }
}
