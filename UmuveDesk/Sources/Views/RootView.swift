//  RootView.swift — Umuve Desk
//  Signed out → sign in. Signed in → home. A live call takes over everything.

import SwiftUI

struct RootView: View {
    @EnvironmentObject private var model: AppModel
    @EnvironmentObject private var voice: VoiceManager

    var body: some View {
        ZStack {
            Color.canvas.ignoresSafeArea()
            if !model.signedIn {
                SignInView()
            } else if let call = voice.activeCall {
                CallView(call: call)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            } else {
                HomeView()
            }
        }
        .animation(.spring(response: 0.42, dampingFraction: 0.86), value: voice.activeCall?.id)
    }
}
