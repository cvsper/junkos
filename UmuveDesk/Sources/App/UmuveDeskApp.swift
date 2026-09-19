//  UmuveDeskApp.swift — Umuve Desk

import SwiftUI

@main
struct UmuveDeskApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @StateObject private var model = AppModel()
    @StateObject private var voice = VoiceManager.shared

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(model)
                .environmentObject(voice)
                .preferredColorScheme(.light)
                .task {
                    #if DEBUG
                    if Demo.mode != nil { Demo.apply(to: model, voice: voice); return }
                    #endif
                    await model.boot()
                }
        }
    }
}

final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        // PushKit must be armed at launch — a VoIP push can be the thing that
        // launches the app in the first place.
        Task { @MainActor in VoiceManager.shared.start() }
        return true
    }
}
