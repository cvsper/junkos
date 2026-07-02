//
//  ActiveJobViewModel.swift
//  Umuve Pro
//
//  Active job status progression, photos, and navigation.
//

import Foundation
import UIKit

@Observable
final class ActiveJobViewModel {
    var job: DriverJob?
    var beforePhotos: [UIImage] = []
    var afterPhotos: [UIImage] = []
    var isUpdating = false
    var errorMessage: String?
    var showCompletion = false

    private let api = DriverAPIClient.shared
    private let locationManager = LocationManager()

    var currentStatus: JobStatus {
        job?.jobStatus ?? .accepted
    }

    // MARK: - Status Transitions

    func markEnRoute() async {
        await updateStatus("en_route")
    }

    func markArrived() async {
        await updateStatus("arrived")
    }

    func markStarted() async {
        // Upload before photos first. A failed upload must BLOCK the status
        // transition — otherwise proof photos silently vanish.
        guard let photoUrls = await uploadPhotosOrFail(beforePhotos) else { return }
        await updateStatus("started", beforePhotos: photoUrls.isEmpty ? nil : photoUrls)
    }

    func markCompleted() async {
        // Upload after photos first — same blocking rule as markStarted().
        guard let photoUrls = await uploadPhotosOrFail(afterPhotos) else { return }
        await updateStatus("completed", afterPhotos: photoUrls.isEmpty ? nil : photoUrls)
        if job?.jobStatus == .completed {
            showCompletion = true
        }
    }

    /// Uploads proof photos. Returns the URLs (empty array when there are no
    /// photos to upload), or nil on failure — after setting `errorMessage` so
    /// the user can retry instead of losing the photos.
    private func uploadPhotosOrFail(_ photos: [UIImage]) async -> [String]? {
        guard !photos.isEmpty else { return [] }
        isUpdating = true
        defer { isUpdating = false }
        do {
            return try await ImageUploadService.shared.uploadPhotos(photos)
        } catch {
            errorMessage = "Couldn't upload your photos — check your connection and tap the button to try again."
            HapticManager.shared.error()
            return nil
        }
    }

    private func updateStatus(
        _ status: String,
        beforePhotos: [String]? = nil,
        afterPhotos: [String]? = nil
    ) async {
        guard let jobId = job?.id else { return }
        isUpdating = true
        errorMessage = nil
        do {
            let response = try await api.updateJobStatus(
                jobId: jobId,
                status: status,
                beforePhotos: beforePhotos,
                afterPhotos: afterPhotos
            )
            job = response.job
            HapticManager.shared.success()

            // Start/stop location streaming based on status
            if status == "en_route", let contractorId = response.job.driverId {
                locationManager.startActiveJobTracking(jobId: jobId, contractorId: contractorId)
            } else if status == "completed" {
                locationManager.stopActiveJobTracking()
            }
        } catch {
            errorMessage = error.localizedDescription
            HapticManager.shared.error()
        }
        isUpdating = false
    }
}
