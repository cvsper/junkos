//
//  RatingReviewViewModel.swift
//  Umuve
//
//  ViewModel for customer rating/review submission after job completion.
//

import Foundation

@MainActor
class RatingReviewViewModel: ObservableObject {
    @Published var rating: Int = 0
    @Published var comment: String = ""
    @Published var isSubmitting = false
    @Published var isSubmitted = false
    @Published var errorMessage: String?

    let jobId: String

    private let apiClient = APIClient.shared

    init(jobId: String) {
        self.jobId = jobId
    }

    var canSubmit: Bool {
        rating >= 1 && !isSubmitting
    }

    func submitReview() async {
        guard canSubmit else { return }

        isSubmitting = true
        errorMessage = nil

        do {
            let body: [String: Any] = [
                "job_id": jobId,
                "rating": rating,
                "comment": comment
            ]

            let jsonData = try JSONSerialization.data(withJSONObject: body)

            guard let url = URL(string: Config.shared.baseURL + "/api/reviews") else {
                throw APIClientError.invalidURL
            }

            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue(Config.shared.apiKey, forHTTPHeaderField: "X-API-Key")

            if let token = KeychainHelper.loadString(forKey: "authToken") {
                request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            }

            request.httpBody = jsonData

            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIClientError.invalidResponse
            }

            if httpResponse.statusCode >= 200 && httpResponse.statusCode < 300 {
                isSubmitted = true
                HapticManager.shared.success()
            } else {
                // Try to decode error message from backend
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let errorMsg = json["error"] as? String {
                    throw APIClientError.serverError(errorMsg)
                }
                throw APIClientError.serverError("Failed to submit review (\(httpResponse.statusCode))")
            }
        } catch let error as APIClientError {
            errorMessage = error.errorDescription
            HapticManager.shared.error()
        } catch {
            errorMessage = "Something went wrong. Please try again."
            HapticManager.shared.error()
        }

        isSubmitting = false
    }
}
