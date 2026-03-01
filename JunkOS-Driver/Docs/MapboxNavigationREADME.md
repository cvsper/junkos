# Mapbox Navigation Setup

## Packages

Add these Swift packages through `project.yml` / Xcode:

- `https://github.com/mapbox/mapbox-navigation-ios.git`
  - `MapboxNavigationCore`
  - `MapboxNavigationUIKit`
  - `MapboxMaps`

The driver project already contains the package declarations in [project.yml](/Users/sevs/Documents/Programs/webapps/junkos/JunkOS-Driver/project.yml).

## Access Tokens

You need two Mapbox tokens:

1. Public access token for runtime map/navigation requests
2. Secret downloads token with `DOWNLOADS:READ` scope for Swift Package Manager downloads

Recommended runtime setup:

- Put the public token in build settings as `MAPBOX_PUBLIC_ACCESS_TOKEN`
- The app also reads `MBXAccessToken` from `Info.plist`

The runtime resolver is implemented in [MapboxConfig.swift](/Users/sevs/Documents/Programs/webapps/junkos/JunkOS-Driver/Navigation/Mapbox/MapboxConfig.swift).

## Info.plist / Capabilities

Required permissions:

- `NSLocationWhenInUseUsageDescription`
- `NSLocationAlwaysAndWhenInUseUsageDescription`

If you want navigation to continue while the app is backgrounded:

- Enable `location` background mode
- Keep `audio` background mode enabled for spoken instructions

The driver target now declares `audio location` in [project.yml](/Users/sevs/Documents/Programs/webapps/junkos/JunkOS-Driver/project.yml).

## 3D Truck Model

Place the custom truck file here:

- `JunkOS-Driver/red_truck.glb`

If you prefer a dedicated folder, keep it inside the app target sources so it is copied into the bundle.

The puck loader expects:

- filename: `red_truck.glb`
- bundle resource present at runtime

Puck configuration is in [CustomPuckSetup.swift](/Users/sevs/Documents/Programs/webapps/junkos/JunkOS-Driver/Navigation/Mapbox/CustomPuckSetup.swift).

## Testing In Simulator

- Use a fixed GPX route or simulator location preset
- Confirm token resolution before launching navigation
- Verify the follow camera starts at approximately 55 degrees pitch
- Toggle `Overview` and `Follow`
- Toggle `Mute` and `Unmute`

Simulator heading can be unstable. The truck may not rotate smoothly until the route is moving with a consistent course.

## Testing On Device

- Test on a real device with full location permissions
- Confirm the truck model appears instead of the default puck
- Start a job from the driver home screen
- Verify the full-screen navigation controller opens in-app
- Confirm the route line renders and the camera follows heading
- Check spoken instructions in both muted and unmuted states

## Heading Alignment Notes

If the truck points sideways or backwards:

- Adjust `modelRotation` in `CustomPuckSetup.redTruckPuckConfiguration`
- Most `.glb` exports need a 90 or 180 degree yaw correction
- Keep `puckBearing = .heading` so the model rotates with real heading instead of map north
