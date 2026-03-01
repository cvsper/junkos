//
//  DriverNavigationContainerView.swift
//  Umuve Pro
//
//  SwiftUI bridge for the UIKit navigation controller.
//

import SwiftUI

struct DriverNavigationContainerView: UIViewControllerRepresentable {
    let coordinator: NavigationCoordinator

    func makeUIViewController(context: Context) -> DriverNavigationViewController {
        DriverNavigationViewController(coordinator: coordinator)
    }

    func updateUIViewController(_ uiViewController: DriverNavigationViewController, context: Context) {
        uiViewController.applyCameraMode(coordinator.cameraMode, animated: true)
        uiViewController.setVoiceMuted(coordinator.isMuted)
    }
}
