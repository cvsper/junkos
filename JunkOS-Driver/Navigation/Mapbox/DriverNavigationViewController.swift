//
//  DriverNavigationViewController.swift
//  Umuve Pro
//
//  Full-screen UIKit navigation surface for the driver home screen.
//

import CoreLocation
import UIKit

#if canImport(MapboxDirections) && canImport(MapboxMaps) && canImport(MapboxNavigationCore) && canImport(MapboxNavigationUIKit)
import MapboxDirections
import MapboxMaps
import MapboxNavigationCore
import MapboxNavigationUIKit

@MainActor
final class DriverNavigationViewController: UIViewController {
    private let coordinator: NavigationCoordinator
    private let navigationProvider: MapboxNavigationProvider
    private var mapboxNavigation: MapboxNavigation {
        navigationProvider.mapboxNavigation
    }
    private var embeddedNavigationViewController: NavigationViewController?

    private lazy var modeButton: UIButton = makeCapsuleButton(title: "Overview")
    private lazy var muteButton: UIButton = makeCapsuleButton(title: "Mute")
    private lazy var closeButton: UIButton = makeCapsuleButton(title: "End")

    init(coordinator: NavigationCoordinator) {
        self.coordinator = coordinator
        let accessToken = (try? MapboxConfig.resolveAccessToken()) ?? ""
        MapboxOptions.accessToken = accessToken
        self.navigationProvider = MapboxNavigationProvider(coreConfig: .init())
        super.init(nibName: nil, bundle: nil)
        self.coordinator.boundViewController = self
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        configureControls()

        Task {
            do {
                try await loadNavigation()
            } catch {
                coordinator.failNavigation(error)
                dismiss(animated: true)
            }
        }
    }

    func applyCameraMode(_ mode: NavigationCoordinator.CameraMode, animated: Bool) {
        guard let mapView = embeddedNavigationViewController?.navigationMapView?.mapView else { return }

        switch mode {
        case .following:
            let followState = mapView.viewport.makeFollowPuckViewportState(
                options: FollowPuckViewportStateOptions(
                    zoom: 16.5,
                    bearing: .heading,
                    pitch: 55
                )
            )
            mapView.viewport.transition(to: followState)
            modeButton.setTitle("Overview", for: .normal)
        case .overview:
            if let embeddedNavigationViewController,
               let navigationRoutes = embeddedNavigationViewController.navigationRoutes,
               let routeShape = navigationRoutes.mainRoute.route.shape {
                let overviewState = mapView.viewport.makeOverviewViewportState(
                    options: OverviewViewportStateOptions(
                        geometry: routeShape,
                        geometryPadding: .init(top: 140, left: 40, bottom: 220, right: 40),
                        bearing: nil,
                        pitch: 0
                    )
                )
                mapView.viewport.transition(to: overviewState)
            }
            modeButton.setTitle("Follow", for: .normal)
        }
    }

    func setVoiceMuted(_ isMuted: Bool) {
        navigationProvider.routeVoiceController.speechSynthesizer.muted = isMuted
        muteButton.setTitle(isMuted ? "Unmute" : "Mute", for: .normal)
    }

    func stopNavigationSession() {
        embeddedNavigationViewController?.dismiss(animated: false)
        embeddedNavigationViewController?.willMove(toParent: nil)
        embeddedNavigationViewController?.view.removeFromSuperview()
        embeddedNavigationViewController?.removeFromParent()
        embeddedNavigationViewController = nil
    }

    private func loadNavigation() async throws {
        guard let routeRequest = coordinator.routeRequest else {
            throw NavigationCoordinatorError.routeRequestUnavailable
        }

        let options = NavigationRouteOptions(
            waypoints: [
                Waypoint(coordinate: routeRequest.origin),
                Waypoint(coordinate: routeRequest.destination),
            ]
        )

        let request = mapboxNavigation.routingProvider().calculateRoutes(options: options)
        let navigationRoutes: NavigationRoutes
        switch await request.result {
        case .failure(let error):
            throw error
        case .success(let routes):
            navigationRoutes = routes
        }
        let navigationOptions = NavigationOptions(
            mapboxNavigation: mapboxNavigation,
            voiceController: navigationProvider.routeVoiceController,
            eventsManager: navigationProvider.eventsManager()
        )

        let navigationViewController = NavigationViewController(
            navigationRoutes: navigationRoutes,
            navigationOptions: navigationOptions
        )
        navigationViewController.delegate = self
        navigationViewController.routeLineTracksTraversal = true
        navigationViewController.showsContinuousAlternatives = true

        if let navigationMapView = navigationViewController.navigationMapView {
            try CustomPuckSetup.apply(to: navigationMapView.mapView)
        }

        embed(navigationViewController)
        embeddedNavigationViewController = navigationViewController
        setVoiceMuted(coordinator.isMuted)
        coordinator.markNavigationReady()
        applyCameraMode(.following, animated: false)
    }

    private func embed(_ child: UIViewController) {
        addChild(child)
        view.insertSubview(child.view, at: 0)
        child.view.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            child.view.topAnchor.constraint(equalTo: view.topAnchor),
            child.view.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            child.view.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            child.view.bottomAnchor.constraint(equalTo: view.bottomAnchor),
        ])
        child.didMove(toParent: self)
    }

    private func configureControls() {
        let stack = UIStackView(arrangedSubviews: [closeButton, modeButton, muteButton])
        stack.axis = .horizontal
        stack.spacing = 12
        stack.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(stack)

        NSLayoutConstraint.activate([
            stack.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 16),
            stack.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -16),
        ])

        modeButton.addTarget(self, action: #selector(toggleMode), for: .touchUpInside)
        muteButton.addTarget(self, action: #selector(toggleMute), for: .touchUpInside)
        closeButton.addTarget(self, action: #selector(closeTapped), for: .touchUpInside)
    }

    private func makeCapsuleButton(title: String) -> UIButton {
        var configuration = UIButton.Configuration.filled()
        configuration.title = title
        configuration.baseForegroundColor = .white
        configuration.baseBackgroundColor = UIColor(red: 0.78, green: 0.12, blue: 0.16, alpha: 0.95)
        configuration.cornerStyle = .capsule
        return UIButton(configuration: configuration)
    }

    @objc
    private func toggleMode() {
        coordinator.toggleCameraMode()
    }

    @objc
    private func toggleMute() {
        coordinator.toggleMute()
    }

    @objc
    private func closeTapped() {
        coordinator.stopNavigation()
        dismiss(animated: true)
    }
}

extension DriverNavigationViewController: @preconcurrency NavigationViewControllerDelegate {
    nonisolated func navigationViewController(
        _ navigationViewController: NavigationViewController,
        routeLineLayerWithIdentifier identifier: String,
        sourceIdentifier: String
    ) -> LineLayer? {
        var lineLayer = LineLayer(id: identifier, source: sourceIdentifier)
        lineLayer.lineColor = .constant(.init(identifier.contains("main") ? UIColor.systemRed : UIColor.systemGray3))
        lineLayer.lineWidth = .constant(7)
        lineLayer.lineJoin = .constant(.round)
        lineLayer.lineCap = .constant(.round)
        return lineLayer
    }

    nonisolated func navigationViewController(
        _ navigationViewController: NavigationViewController,
        routeCasingLineLayerWithIdentifier identifier: String,
        sourceIdentifier: String
    ) -> LineLayer? {
        var lineLayer = LineLayer(id: identifier, source: sourceIdentifier)
        lineLayer.lineColor = .constant(.init(identifier.contains("main") ? UIColor.black : UIColor.darkGray))
        lineLayer.lineWidth = .constant(9)
        lineLayer.lineJoin = .constant(.round)
        lineLayer.lineCap = .constant(.round)
        return lineLayer
    }

    nonisolated func navigationViewControllerDidDismiss(
        _ navigationViewController: NavigationViewController,
        byCanceling canceled: Bool
    ) {
        Task { @MainActor in
            coordinator.stopNavigation()
        }
    }
}

#else

@MainActor
final class DriverNavigationViewController: UIViewController {
    private let coordinator: NavigationCoordinator

    init(coordinator: NavigationCoordinator) {
        self.coordinator = coordinator
        super.init(nibName: nil, bundle: nil)
        self.coordinator.boundViewController = self
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black

        let label = UILabel()
        label.numberOfLines = 0
        label.textAlignment = .center
        label.textColor = .white
        label.text = "Mapbox Navigation SDK is not linked into this build."
        label.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(label)

        NSLayoutConstraint.activate([
            label.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            label.centerYAnchor.constraint(equalTo: view.centerYAnchor),
            label.leadingAnchor.constraint(greaterThanOrEqualTo: view.leadingAnchor, constant: 24),
            label.trailingAnchor.constraint(lessThanOrEqualTo: view.trailingAnchor, constant: -24),
        ])

        coordinator.failNavigation(NavigationCoordinatorError.mapboxUnavailable)
    }

    func applyCameraMode(_ mode: NavigationCoordinator.CameraMode, animated: Bool) {}
    func setVoiceMuted(_ isMuted: Bool) {}
    func stopNavigationSession() {}
}

#endif
