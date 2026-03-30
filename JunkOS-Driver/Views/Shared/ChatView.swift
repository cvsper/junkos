//
//  ChatView.swift
//  Umuve Pro
//
//  In-app chat view for communication between driver and customer.
//  Uses @Observable pattern and Driver design system.
//  Auto-refreshes messages via 5-second polling.
//

import SwiftUI

struct ChatView: View {
    @State private var viewModel: ChatViewModel
    @Environment(\.dismiss) private var dismiss

    init(jobId: String) {
        _viewModel = State(wrappedValue: ChatViewModel(jobId: jobId))
    }

    var body: some View {
        VStack(spacing: 0) {
            // Navigation header
            chatHeader

            Divider()
                .foregroundColor(.driverDivider)

            // Messages
            if viewModel.isLoading && viewModel.messages.isEmpty {
                Spacer()
                ProgressView()
                    .progressViewStyle(CircularProgressViewStyle(tint: .driverPrimary))
                Spacer()
            } else if viewModel.messages.isEmpty {
                emptyState
            } else {
                messagesList
            }

            Divider()
                .foregroundColor(.driverDivider)

            // Input bar
            inputBar
        }
        .background(Color.driverBackground.ignoresSafeArea())
        .task {
            await viewModel.loadInitialMessages()
        }
        .onAppear {
            viewModel.startPolling()
        }
        .onDisappear {
            viewModel.stopPolling()
        }
    }

    // MARK: - Header

    private var chatHeader: some View {
        HStack {
            Button(action: { dismiss() }) {
                Image(systemName: "chevron.left")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundColor(.driverText)
            }

            Spacer()

            VStack(spacing: 2) {
                Text("Chat")
                    .font(DriverTypography.headline)
                    .foregroundColor(.driverText)

                Text("Job #\(viewModel.jobId.prefix(8))")
                    .font(DriverTypography.caption)
                    .foregroundColor(.driverTextSecondary)
            }

            Spacer()

            Color.clear.frame(width: 24, height: 24)
        }
        .padding(.horizontal, DriverSpacing.md)
        .padding(.vertical, DriverSpacing.sm)
        .background(Color.driverSurface)
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: DriverSpacing.md) {
            Spacer()

            Image(systemName: "bubble.left.and.bubble.right")
                .font(.system(size: 48))
                .foregroundColor(.driverTextTertiary)

            Text("No messages yet")
                .font(DriverTypography.headline)
                .foregroundColor(.driverText)

            Text("Send a message to the customer")
                .font(DriverTypography.footnote)
                .foregroundColor(.driverTextSecondary)

            Spacer()
        }
    }

    // MARK: - Messages List

    private var messagesList: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: DriverSpacing.xs) {
                    ForEach(viewModel.messages) { message in
                        DriverChatBubble(
                            message: message,
                            isCurrentUser: message.isFromCurrentUser
                        )
                        .id(message.id)
                    }
                }
                .padding(.horizontal, DriverSpacing.md)
                .padding(.vertical, DriverSpacing.xs)
            }
            .onChange(of: viewModel.messages.count) {
                if let last = viewModel.messages.last {
                    withAnimation(AnimationConstants.fastEase) {
                        proxy.scrollTo(last.id, anchor: .bottom)
                    }
                }
            }
            .onAppear {
                if let last = viewModel.messages.last {
                    proxy.scrollTo(last.id, anchor: .bottom)
                }
            }
        }
    }

    // MARK: - Input Bar

    private var inputBar: some View {
        HStack(spacing: DriverSpacing.sm) {
            TextField("Type a message...", text: $viewModel.newMessageText, axis: .vertical)
                .font(DriverTypography.body)
                .lineLimit(1...4)
                .padding(.horizontal, DriverSpacing.md)
                .padding(.vertical, DriverSpacing.sm)
                .background(Color.white)
                .clipShape(RoundedRectangle(cornerRadius: 24))
                .overlay(
                    RoundedRectangle(cornerRadius: 24)
                        .stroke(Color.driverBorder, lineWidth: 1)
                )

            Button(action: {
                Task {
                    await viewModel.sendMessage()
                }
            }) {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 36))
                    .foregroundColor(
                        viewModel.newMessageText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                        ? .driverTextTertiary
                        : .driverPrimary
                    )
            }
            .disabled(
                viewModel.newMessageText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                || viewModel.isSending
            )
        }
        .padding(.horizontal, DriverSpacing.md)
        .padding(.vertical, DriverSpacing.sm)
        .background(Color.driverSurface)
    }
}

// MARK: - Driver Chat Bubble

struct DriverChatBubble: View {
    let message: ChatMessage
    let isCurrentUser: Bool

    var body: some View {
        HStack {
            if isCurrentUser { Spacer(minLength: 60) }

            VStack(alignment: isCurrentUser ? .trailing : .leading, spacing: 4) {
                Text(message.message)
                    .font(DriverTypography.body)
                    .foregroundColor(isCurrentUser ? .white : .driverText)
                    .padding(.horizontal, DriverSpacing.md)
                    .padding(.vertical, DriverSpacing.sm)
                    .background(
                        isCurrentUser
                        ? Color.driverPrimary
                        : Color.white
                    )
                    .clipShape(DriverChatBubbleShape(isCurrentUser: isCurrentUser))
                    .shadow(color: .black.opacity(0.04), radius: 2, x: 0, y: 1)

                Text(message.formattedTime)
                    .font(DriverTypography.caption2)
                    .foregroundColor(.driverTextTertiary)
                    .padding(.horizontal, 4)
            }

            if !isCurrentUser { Spacer(minLength: 60) }
        }
    }
}

// MARK: - Chat Bubble Shape

struct DriverChatBubbleShape: Shape {
    let isCurrentUser: Bool

    func path(in rect: CGRect) -> Path {
        let radius: CGFloat = 16
        let tailSize: CGFloat = 6

        var path = Path()

        if isCurrentUser {
            path.addRoundedRect(
                in: CGRect(x: 0, y: 0, width: rect.width - tailSize, height: rect.height),
                cornerSize: CGSize(width: radius, height: radius)
            )
            path.move(to: CGPoint(x: rect.width - tailSize, y: rect.height - radius))
            path.addLine(to: CGPoint(x: rect.width, y: rect.height))
            path.addLine(to: CGPoint(x: rect.width - tailSize, y: rect.height))
        } else {
            path.addRoundedRect(
                in: CGRect(x: tailSize, y: 0, width: rect.width - tailSize, height: rect.height),
                cornerSize: CGSize(width: radius, height: radius)
            )
            path.move(to: CGPoint(x: tailSize, y: rect.height - radius))
            path.addLine(to: CGPoint(x: 0, y: rect.height))
            path.addLine(to: CGPoint(x: tailSize, y: rect.height))
        }

        return path
    }
}

#Preview {
    ChatView(jobId: "test-job-456")
}
