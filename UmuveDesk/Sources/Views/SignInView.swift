//  SignInView.swift — Umuve Desk

import SwiftUI

struct SignInView: View {
    @EnvironmentObject private var model: AppModel
    @State private var email = ""
    @State private var password = ""
    @FocusState private var focus: Field?
    private enum Field { case email, password }
    private var ready: Bool { !email.isEmpty && !password.isEmpty }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Spacer(minLength: 30)
            Image("BrandMark").resizable().scaledToFit().frame(width: 56, height: 56)
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                .shadow(color: Color.stop.opacity(0.25), radius: 18, y: 10)
            Text("Umuve Desk").font(Type.display(42)).tracking(-1.8).foregroundStyle(Color.ink).padding(.top, 22)
            Text("The desk line, in your pocket.").font(Type.body).foregroundStyle(Color.muted).padding(.top, 6)

            VStack(spacing: 10) {
                TextField("Email", text: $email)
                    .textContentType(.username).keyboardType(.emailAddress)
                    .textInputAutocapitalization(.never).autocorrectionDisabled()
                    .focused($focus, equals: .email).submitLabel(.next).onSubmit { focus = .password }
                SecureField("Password", text: $password)
                    .textContentType(.password).focused($focus, equals: .password).submitLabel(.go).onSubmit(submit)
                if let n = model.notice {
                    HStack(spacing: 8) { Dot(color: .stop, size: 6); Text(n).font(Type.small).foregroundStyle(Color.stop) }
                        .frame(maxWidth: .infinity, alignment: .leading).padding(.top, 4)
                }
            }
            .textFieldStyle(DeskField())
            .glass(14)
            .padding(.top, 28)

            Spacer()
            PillButton(title: "Sign in", tone: .dark, busy: model.busy, action: submit)
                .disabled(!ready).opacity(ready ? 1 : 0.55)
            Text("Same account as the browser desk. No account? Ask Shamar.")
                .font(Type.small).foregroundStyle(Color.faint).padding(.top, 14)
        }
        .padding(.horizontal, 22).padding(.bottom, 22)
    }

    private func submit() {
        guard ready else { return }
        Task { await model.signIn(email: email.trimmingCharacters(in: .whitespaces), password: password) }
    }
}
