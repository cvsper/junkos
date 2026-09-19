import XCTest
@testable import UmuveDesk

final class UmuveDeskTests: XCTestCase {
    func testWhoisDisplayNameFallsBackSensibly() throws {
        let json = #"{"kind":"unknown","phone":"(561) 555-0100","phone_digits":"5615550100"}"#.data(using: .utf8)!
        let w = try JSONDecoder().decode(Whois.self, from: json)
        XCTAssertEqual(w.displayName, "Unknown caller")
    }

    func testDeskSessionDecodesTheLoginShape() throws {
        let json = #"{"token":"t","name":"Tracy","full_name":"Tracy Young","email":"t@x","role":"va","is_manager":false}"#.data(using: .utf8)!
        let s = try JSONDecoder().decode(DeskSession.self, from: json)
        XCTAssertEqual(s.name, "Tracy"); XCTAssertFalse(s.isManager)
    }
}
