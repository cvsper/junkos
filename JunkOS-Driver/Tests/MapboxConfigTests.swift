import XCTest
@testable import JunkOS_Driver

final class MapboxConfigTests: XCTestCase {
    func testEnvironmentTokenOverridesInfoPlistToken() throws {
        let token = try MapboxConfig.resolveAccessToken(
            environment: ["MAPBOX_PUBLIC_ACCESS_TOKEN": "env-token"],
            infoDictionary: ["MBXAccessToken": "plist-token"]
        )

        XCTAssertEqual(token, "env-token")
    }

    func testInfoPlistTokenIsUsedWhenEnvironmentMissing() throws {
        let token = try MapboxConfig.resolveAccessToken(
            environment: [:],
            infoDictionary: ["MBXAccessToken": "plist-token"]
        )

        XCTAssertEqual(token, "plist-token")
    }

    func testMissingTokenThrows() {
        XCTAssertThrowsError(
            try MapboxConfig.resolveAccessToken(environment: [:], infoDictionary: [:])
        ) { error in
            XCTAssertEqual(error as? MapboxConfigError, .missingAccessToken)
        }
    }
}
