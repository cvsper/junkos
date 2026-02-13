//
//  AppRouter.swift
//  Umuve Pro
//
//  Navigation path enum for NavigationStack-based routing.
//

import Foundation

enum AppRoute: Hashable {
    // Auth
    case login
    case signup

    // Registration
    case registration

    // Main tabs
    case dashboard
    case jobFeed
    case earnings
    case profile

    // Job detail
    case jobDetail(jobId: String)

    // Active job
    case activeJob(jobId: String)
}
