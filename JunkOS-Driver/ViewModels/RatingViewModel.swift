//
//  RatingViewModel.swift
//  Umuve Pro
//
//  ViewModel for driver rating submission after completing a job.
//

import Foundation

@Observable
final class RatingViewModel {
    var stars: Int = 0
    var comment: String = ""
    var isSubmitting = false
    var isSubmitted = false
    var errorMessage: String?

    let jobId: String

    private let api = DriverAPIClient.shared

    init(jobId: String) {
        self.jobId = jobId
    }

    var canSubmit: Bool {
        stars >= 1 && !isSubmitting
    }

    func submitRating() async {
        guard canSubmit else { return }

        isSubmitting = true
        errorMessage = nil

        do {
            let body: [String: Any] = [
                "job_id": jobId,
                "stars": stars,
                "comment": comment
            ]

            let jsonData = try JSONSerialization.data(withJSONObject: body)

            guard let url = URL(string: AppConfig.shared.baseURL + "/api/ratings") else {
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

            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.invalidResponse
            }

            if httpResponse.statusCode >= 200 && httpResponse.statusCode < 300 {
                isSubmitted = true
                HapticManager.shared.success()
            } else {
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let errorMsg = json["error"] as? String {
                    throw APIError.server(errorMsg)
                }
                throw APIError.server("Failed to submit rating (\(httpResponse.statusCode))")
            }
        } catch let error as APIError {
            errorMessage = error.errorDescription
            HapticManager.shared.error()
        } catch {
            errorMessage = "Something went wrong. Please try again."
            HapticManager.shared.error()
        }

        isSubmitting = false
    }
}
