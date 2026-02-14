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
        // Upload before photos first
        var photoUrls: [String]? = nil
        if !beforePhotos.isEmpty {
            photoUrls = try? await ImageUploadService.shared.uploadPhotos(beforePhotos)
        }
        await updateStatus("started", beforePhotos: photoUrls)
    }

    func markCompleted() async {
        // Upload after photos first
        var photoUrls: [String]? = nil
        if !afterPhotos.isEmpty {
            photoUrls = try? await ImageUploadService.shared.uploadPhotos(afterPhotos)
        }
        await updateStatus("completed", afterPhotos: photoUrls)
        if job?.jobStatus == .completed {
            showCompletion = true
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
