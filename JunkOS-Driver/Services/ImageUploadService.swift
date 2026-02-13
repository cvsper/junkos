//
//  ImageUploadService.swift
//  Umuve Pro
//
//  Multipart photo upload service for before/after job photos.
//

import Foundation
import UIKit

actor ImageUploadService {
    static let shared = ImageUploadService()

    private let session: URLSession
    private let baseURL: String

    private init() {
        self.session = URLSession.shared
        self.baseURL = AppConfig.shared.baseURL
    }

    /// Compress a UIImage to JPEG data at the given quality.
    nonisolated func compressImage(_ image: UIImage, maxSizeKB: Int = 500) -> Data? {
        var quality: CGFloat = 0.8
        var data = image.jpegData(compressionQuality: quality)
        while let d = data, d.count > maxSizeKB * 1024, quality > 0.1 {
            quality -= 0.1
            data = image.jpegData(compressionQuality: quality)
        }
        return data
    }

    /// Upload multiple photos in a single request. Returns array of URL strings.
    func uploadPhotos(_ images: [UIImage]) async throws -> [String] {
        guard let url = URL(string: baseURL + "/api/upload/photos") else {
            throw APIError.invalidURL
        }

        let boundary = UUID().uuidString
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        if let token = KeychainHelper.loadString(forKey: "authToken") {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        var body = Data()
        for (index, image) in images.enumerated() {
            guard let imageData = compressImage(image) else { continue }
            body.append("--\(boundary)\r\n".data(using: .utf8)!)
            body.append("Content-Disposition: form-data; name=\"files\"; filename=\"photo_\(index).jpg\"\r\n".data(using: .utf8)!)
            body.append("Content-Type: image/jpeg\r\n\r\n".data(using: .utf8)!)
            body.append(imageData)
            body.append("\r\n".data(using: .utf8)!)
        }
        body.append("--\(boundary)--\r\n".data(using: .utf8)!)
        req.httpBody = body

        let (data, response) = try await session.data(for: req)

        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw APIError.server("Photo upload failed")
        }

        struct UploadResponse: Codable {
            let success: Bool
            let urls: [String]
        }

        let result = try JSONDecoder().decode(UploadResponse.self, from: data)
        return result.urls
    }
}
