//  SignInView.swift — Umuve Desk
//  Same account as the browser desk. Nothing to explain.

import SwiftUI

struct SignInView: View {
    @EnvironmentObject private var model: AppModel
    @State private var email = ""
    @State private var password = ""
    @FocusState private var focus: Field?
    private enum Field { case email, password }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Spacer(minLength: 40)
            Text("Umuve Desk").font(Type.display(44)).tracking(-1.6).foregroundStyle(Color.ink)
            Text("Sign in with your desk account.").font(Type.body).foregroundStyle(Color.muted).padding(.top, 8)

            VStack(spacing: 12) {
                TextField("Email", text: $email)
                    .textContentType(.username).keyboardType(.emailAddress)
                    .textInputAutocapitalization(.never).autocorrectionDisabled()
                    .focused($focus, equals: .email).submitLabel(.next)
                    .onSubmit { focus = .password }
                SecureField("Password", text: $password)
                    .textContentType(.password).focused($focus, equals: .password).submitLabel(.go)
                    .onSubmit { submit() }
            }
            .textFieldStyle(DeskField())
            .padding(.top, 28)

            if let n = model.notice {
                Text(n).font(Type.small).foregroundStyle(Color.stop).padding(.top, 12)
            }

            Spacer()
            PillButton(title: "Sign in", tone: .dark, busy: model.busy) { submit() }
                .disabled(email.isEmpty || password.isEmpty)
                .opacity(email.isEmpty || password.isEmpty ? 0.5 : 1)
            Text("Don't have a desk account? Ask Shamar to add you.")
                .font(Type.small).foregroundStyle(Color.faint).padding(.top, 14)
        }
        .padding(.horizontal, 22).padding(.bottom, 24)
    }

    private func submit() {
        guard !email.isEmpty, !password.isEmpty else { return }
        Task { await model.signIn(email: email.trimmingCharacters(in: .whitespaces), password: password) }
    }
}

struct DeskField: TextFieldStyle {
    func _body(configuration: TextField<Self._Label>) -> some View {
        configuration
            .font(Type.body)
            .padding(.horizontal, 16).frame(minHeight: 54)
            .background(Color.raise, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).stroke(Color.ink.opacity(0.14)))
    }
}
