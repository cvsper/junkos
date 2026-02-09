//
//  InviteCodeStepView.swift
//  JunkOS Driver
//
//  Optional invite code field shown before the truck type selection step.
//

import SwiftUI

struct InviteCodeStepView: View {
    @Bindable var viewModel: RegistrationViewModel

    var body: some View {
        VStack(spacing: 24) {
            // Illustration
            Image(systemName: "envelope.open.fill")
                .font(.system(size: 48))
                .foregroundStyle(.accentColor)
                .padding(.top, 16)

            VStack(spacing: 8) {
                Text("Have an Invite Code?")
                    .font(.title3)
                    .fontWeight(.bold)

                Text("If a fleet operator invited you, enter their code below. You can also skip this step.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 16)
            }

            // Code Input
            TextField("Enter invite code", text: $viewModel.inviteCode)
                .font(.system(.title3, design: .monospaced))
                .textInputAutocapitalization(.characters)
                .multilineTextAlignment(.center)
                .padding(.vertical, 16)
                .padding(.horizontal, 24)
                .background(Color(.systemGray6))
                .clipShape(RoundedRectangle(cornerRadius: 14))
                .padding(.horizontal, 32)

            Text("This is optional. You can register as an independent contractor without a code.")
                .font(.caption)
                .foregroundStyle(.tertiary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)

            Spacer()
        }
    }
}
