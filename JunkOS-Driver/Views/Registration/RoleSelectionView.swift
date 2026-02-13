//
//  RoleSelectionView.swift
//  Umuve Pro
//
//  Two cards: "Contractor" / "Fleet Operator" role selection.
//

import SwiftUI

struct RoleSelectionView: View {
    var appState: AppState

    var body: some View {
        VStack(spacing: 0) {
            Spacer()

            // Header
            VStack(spacing: 8) {
                Image(systemName: "person.2.circle.fill")
                    .font(.system(size: 56))
                    .foregroundStyle(.primary)

                Text("How will you use Umuve?")
                    .font(.title2)
                    .fontWeight(.bold)

                Text("Choose your role to get started")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            .padding(.bottom, 40)

            // Role Cards
            VStack(spacing: 16) {
                RoleCard(
                    icon: "truck.box.fill",
                    title: "Contractor",
                    subtitle: "Pick up junk, complete jobs, and earn money",
                    isSelected: appState.selectedRole == .contractor
                ) {
                    withAnimation(.snappy) {
                        appState.selectedRole = .contractor
                    }
                }

                RoleCard(
                    icon: "building.2.fill",
                    title: "Fleet Operator",
                    subtitle: "Manage a fleet of contractors and delegate jobs",
                    isSelected: appState.selectedRole == .operator_
                ) {
                    withAnimation(.snappy) {
                        appState.selectedRole = .operator_
                    }
                }
            }
            .padding(.horizontal, 24)

            Spacer()

            // Continue Button
            if appState.selectedRole != nil {
                Button {
                    HapticManager.shared.mediumTap()
                } label: {
                    Text("Continue")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                        .background(Color.accentColor)
                        .foregroundColor(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 14))
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 32)
                .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
    }
}

struct RoleCard: View {
    let icon: String
    let title: String
    let subtitle: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 16) {
                Image(systemName: icon)
                    .font(.title2)
                    .foregroundStyle(isSelected ? .white : .primary)
                    .frame(width: 48, height: 48)
                    .background(isSelected ? Color.accentColor : Color(.systemGray6))
                    .clipShape(Circle())

                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(.headline)
                        .foregroundStyle(.primary)

                    Text(subtitle)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.leading)
                }

                Spacer()

                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.title3)
                    .foregroundStyle(isSelected ? Color.accentColor : Color.secondary)
            }
            .padding(16)
            .background(Color(.systemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .stroke(isSelected ? Color.accentColor : Color(.systemGray5), lineWidth: isSelected ? 2 : 1)
            )
            .shadow(color: .black.opacity(0.04), radius: 8, y: 4)
        }
        .buttonStyle(.plain)
    }
}
