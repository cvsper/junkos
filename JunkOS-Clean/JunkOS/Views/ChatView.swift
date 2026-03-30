//
//  ChatView.swift
//  Umuve
//
//  In-app chat view for communication between customer and driver.
//  Fetches messages, displays chat bubbles, sends new messages,
//  and auto-refreshes via timer-based polling every 5 seconds.
//

import SwiftUI

struct ChatView: View {
    @StateObject private var viewModel: ChatViewModel
    @Environment(\.dismiss) private var dismiss

    init(jobId: String) {
        _viewModel = StateObject(wrappedValue: ChatViewModel(jobId: jobId))
    }

    var body: some View {
        VStack(spacing: 0) {
            // Navigation header
            chatHeader

            Divider()
                .foregroundColor(.umuveDivider)

            // Messages
            if viewModel.isLoading && viewModel.messages.isEmpty {
                Spacer()
                ProgressView()
                    .progressViewStyle(CircularProgressViewStyle(tint: .umuvePrimary))
                Spacer()
            } else if viewModel.messages.isEmpty {
                emptyState
            } else {
                messagesList
            }

            Divider()
                .foregroundColor(.umuveDivider)

            // Input bar
            inputBar
        }
        .background(Color.umuveBackground.ignoresSafeArea())
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
                    .foregroundColor(.umuveText)
            }

            Spacer()

            VStack(spacing: 2) {
                Text("Chat")
                    .font(UmuveTypography.h3Font)
                    .foregroundColor(.umuveText)

                Text("Job #\(viewModel.jobId.prefix(8))")
                    .font(UmuveTypography.captionFont)
                    .foregroundColor(.umuveTextMuted)
            }

            Spacer()

            // Spacer for symmetry
            Color.clear.frame(width: 24, height: 24)
        }
        .padding(.horizontal, UmuveSpacing.normal)
        .padding(.vertical, UmuveSpacing.medium)
        .background(Color.umuveSurface)
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: UmuveSpacing.normal) {
            Spacer()

            Image(systemName: "bubble.left.and.bubble.right")
                .font(.system(size: 48))
                .foregroundColor(.umuveTextTertiary)

            Text("No messages yet")
                .font(UmuveTypography.h3Font)
                .foregroundColor(.umuveText)

            Text("Send a message to your driver")
                .font(UmuveTypography.bodySmallFont)
                .foregroundColor(.umuveTextMuted)

            Spacer()
        }
    }

    // MARK: - Messages List

    private var messagesList: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: UmuveSpacing.small) {
                    ForEach(viewModel.messages) { message in
                        ChatBubble(
                            message: message,
                            isCurrentUser: message.isFromCurrentUser
                        )
                        .id(message.id)
                    }
                }
                .padding(.horizontal, UmuveSpacing.normal)
                .padding(.vertical, UmuveSpacing.small)
            }
            .onChange(of: viewModel.messages.count) { _ in
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
        HStack(spacing: UmuveSpacing.medium) {
            TextField("Type a message...", text: $viewModel.newMessageText, axis: .vertical)
                .font(UmuveTypography.bodyFont)
                .lineLimit(1...4)
                .padding(.horizontal, UmuveSpacing.normal)
                .padding(.vertical, UmuveSpacing.medium)
                .background(Color.white)
                .cornerRadius(24)
                .overlay(
                    RoundedRectangle(cornerRadius: 24)
                        .stroke(Color.umuveBorder, lineWidth: 1)
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
                        ? .umuveTextTertiary
                        : .umuvePrimary
                    )
            }
            .disabled(
                viewModel.newMessageText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                || viewModel.isSending
            )
        }
        .padding(.horizontal, UmuveSpacing.normal)
        .padding(.vertical, UmuveSpacing.medium)
        .background(Color.umuveSurface)
    }
}

// MARK: - Chat Bubble

struct ChatBubble: View {
    let message: ChatMessage
    let isCurrentUser: Bool

    var body: some View {
        HStack {
            if isCurrentUser { Spacer(minLength: 60) }

            VStack(alignment: isCurrentUser ? .trailing : .leading, spacing: 4) {
                Text(message.message)
                    .font(UmuveTypography.bodyFont)
                    .foregroundColor(isCurrentUser ? .white : .umuveText)
                    .padding(.horizontal, UmuveSpacing.normal)
                    .padding(.vertical, UmuveSpacing.medium)
                    .background(
                        isCurrentUser
                        ? Color.umuvePrimary
                        : Color.white
                    )
                    .clipShape(ChatBubbleShape(isCurrentUser: isCurrentUser))
                    .shadow(color: .black.opacity(0.04), radius: 2, x: 0, y: 1)

                Text(message.formattedTime)
                    .font(UmuveTypography.smallFont)
                    .foregroundColor(.umuveTextTertiary)
                    .padding(.horizontal, 4)
            }

            if !isCurrentUser { Spacer(minLength: 60) }
        }
    }
}

// MARK: - Chat Bubble Shape

struct ChatBubbleShape: Shape {
    let isCurrentUser: Bool

    func path(in rect: CGRect) -> Path {
        let radius: CGFloat = 16
        let tailSize: CGFloat = 6

        var path = Path()

        if isCurrentUser {
            // Current user: rounded corners with bottom-right tail
            path.addRoundedRect(
                in: CGRect(x: 0, y: 0, width: rect.width - tailSize, height: rect.height),
                cornerSize: CGSize(width: radius, height: radius)
            )
            // Small tail on right
            path.move(to: CGPoint(x: rect.width - tailSize, y: rect.height - radius))
            path.addLine(to: CGPoint(x: rect.width, y: rect.height))
            path.addLine(to: CGPoint(x: rect.width - tailSize, y: rect.height))
        } else {
            // Other user: rounded corners with bottom-left tail
            path.addRoundedRect(
                in: CGRect(x: tailSize, y: 0, width: rect.width - tailSize, height: rect.height),
                cornerSize: CGSize(width: radius, height: radius)
            )
            // Small tail on left
            path.move(to: CGPoint(x: tailSize, y: rect.height - radius))
            path.addLine(to: CGPoint(x: 0, y: rect.height))
            path.addLine(to: CGPoint(x: tailSize, y: rect.height))
        }

        return path
    }
}

#Preview {
    ChatView(jobId: "test-job-123")
}
