//
//  OperatorWebRedirectView.swift
//  JunkOS Driver
//
//  Shown after an operator registers. Directs them to the web dashboard.
//

import SwiftUI

struct OperatorWebRedirectView: View {
    var appState: AppState

    var body: some View {
        VStack(spacing: 0) {
            Spacer()

            VStack(spacing: 16) {
                Image(systemName: "desktopcomputer")
                    .font(.system(size: 64))
                    .foregroundStyle(.accentColor)

                Text("Manage from the Web")
                    .font(.title2)
                    .fontWeight(.bold)

                Text("As a fleet operator, you manage jobs and contractors through the web dashboard. Open it in your browser to get started.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }

            Spacer()

            VStack(spacing: 12) {
                // Open Dashboard Button
                Button {
                    if let url = URL(string: dashboardURL) {
                        UIApplication.shared.open(url)
                    }
                } label: {
                    HStack {
                        Image(systemName: "safari.fill")
                        Text("Open Dashboard")
                    }
                    .font(.headline)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
                    .background(Color.accentColor)
                    .foregroundColor(.white)
                    .clipShape(RoundedRectangle(cornerRadius: 14))
                }

                // Sign Out
                Button {
                    appState.auth.signOut()
                    appState.selectedRole = nil
                    appState.contractorProfile = nil
                } label: {
                    Text("Sign Out")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                .padding(.top, 4)
            }
            .padding(.horizontal, 24)
            .padding(.bottom, 32)
        }
    }

    private var dashboardURL: String {
        let base = DriverAPIClient.shared.baseURL
            .replacingOccurrences(of: "/api", with: "")
            .replacingOccurrences(of: ":5001", with: ":3000")
        return "\(base)/operator"
    }
}
