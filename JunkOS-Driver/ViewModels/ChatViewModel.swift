//
//  ChatViewModel.swift
//  Umuve Pro
//
//  ViewModel for the in-app chat between driver and customer.
//  Uses @Observable (Observation framework) matching driver app patterns.
//

import Foundation

struct ChatMessage: Codable, Identifiable, Equatable {
    let id: String
    let jobId: String
    let senderId: String
    let senderRole: String
    let message: String
    let createdAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case jobId = "job_id"
        case senderId = "sender_id"
        case senderRole = "sender_role"
        case message
        case createdAt = "created_at"
    }

    var isFromCurrentUser: Bool {
        senderRole == "driver"
    }

    var formattedTime: String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]

        let date = formatter.date(from: createdAt) ?? ISO8601DateFormatter().date(from: createdAt)

        guard let parsed = date else { return "" }

        let display = DateFormatter()
        display.timeStyle = .short
        return display.string(from: parsed)
    }
}

private struct ChatMessagesResponse: Codable {
    let success: Bool
    let messages: [ChatMessage]
}

private struct SendMessageResponse: Codable {
    let success: Bool
    let message: ChatMessage?
}

@Observable
final class ChatViewModel {
    var messages: [ChatMessage] = []
    var newMessageText: String = ""
    var isLoading = false
    var isSending = false
    var errorMessage: String?

    let jobId: String
    private var timer: Timer?

    init(jobId: String) {
        self.jobId = jobId
    }

    // MARK: - Fetch Messages

    func fetchMessages() async {
        do {
            guard let url = URL(string: AppConfig.shared.baseURL + "/api/chat/\(jobId)/messages") else {
                throw APIError.invalidURL
            }

            var request = URLRequest(url: url)
            request.httpMethod = "GET"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")

            if let token = KeychainHelper.loadString(forKey: "authToken") {
                request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            }

            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode >= 200 && httpResponse.statusCode < 300 else {
                return
            }

            let decoded = try JSONDecoder().decode(ChatMessagesResponse.self, from: data)
            messages = decoded.messages
            errorMessage = nil
        } catch {
            print("Chat fetch error: \(error.localizedDescription)")
        }
    }

    func loadInitialMessages() async {
        isLoading = true
        await fetchMessages()
        isLoading = false
    }

    // MARK: - Send Message

    func sendMessage() async {
        let text = newMessageText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !isSending else { return }

        isSending = true
        errorMessage = nil

        // Optimistically add message
        let optimisticMessage = ChatMessage(
            id: UUID().uuidString,
            jobId: jobId,
            senderId: KeychainHelper.loadString(forKey: "userId") ?? "me",
            senderRole: "driver",
            message: text,
            createdAt: ISO8601DateFormatter().string(from: Date())
        )
        messages.append(optimisticMessage)
        newMessageText = ""

        do {
            let body: [String: String] = ["message": text]
            let jsonData = try JSONEncoder().encode(body)

            guard let url = URL(string: AppConfig.shared.baseURL + "/api/chat/\(jobId)/messages") else {
                throw APIError.invalidURL
            }

            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")

            if let token = KeychainHelper.loadString(forKey: "authToken") {
                request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            }

            request.httpBody = jsonData

            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode >= 200 && httpResponse.statusCode < 300 else {
                messages.removeAll { $0.id == optimisticMessage.id }
                newMessageText = text
                throw APIError.server("Failed to send message")
            }

            if let decoded = try? JSONDecoder().decode(SendMessageResponse.self, from: data),
               let serverMessage = decoded.message {
                if let index = messages.firstIndex(where: { $0.id == optimisticMessage.id }) {
                    messages[index] = serverMessage
                }
            }

            HapticManager.shared.lightTap()
        } catch {
            errorMessage = "Failed to send message"
            HapticManager.shared.error()
        }

        isSending = false
    }

    // MARK: - Polling

    func startPolling() {
        timer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
            Task { [weak self] in
                await self?.fetchMessages()
            }
        }
    }

    func stopPolling() {
        timer?.invalidate()
        timer = nil
    }
}
