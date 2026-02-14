//
//  KeychainHelper.swift
//  Umuve
//
//  Secure storage for JWT tokens via the system Keychain.
//

import Foundation
import Security

enum KeychainHelper {
    private static let service = "com.goumuve.app"
    private static let legacyService = "com.goumuve.customer"
    private static let userDefaultsMigrationKey = "_keychain_migration_complete"

    static func save(_ data: Data, forKey key: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
        ]
        // Delete any existing item first
        SecItemDelete(query as CFDictionary)

        var newItem = query
        newItem[kSecValueData as String] = data
        newItem[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        SecItemAdd(newItem as CFDictionary, nil)
    }

    static func save(_ string: String, forKey key: String) {
        guard let data = string.data(using: .utf8) else { return }
        save(data, forKey: key)
    }

    static func load(forKey key: String) -> Data? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        if status == errSecSuccess, let data = result as? Data {
            return data
        }

        // Migration 1: try reading from legacy keychain service
        let legacyQuery: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: legacyService,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var legacyResult: AnyObject?
        let legacyStatus = SecItemCopyMatching(legacyQuery as CFDictionary, &legacyResult)
        if legacyStatus == errSecSuccess, let oldData = legacyResult as? Data {
            // Migrate to new service key
            save(oldData, forKey: key)
            // Delete old entry
            let deleteQuery: [String: Any] = [
                kSecClass as String: kSecClassGenericPassword,
                kSecAttrService as String: legacyService,
                kSecAttrAccount as String: key,
            ]
            SecItemDelete(deleteQuery as CFDictionary)
            return oldData
        }

        // Migration 2: one-time migration from UserDefaults (AUTH-01)
        // Only check UserDefaults if we haven't completed migration before
        if !UserDefaults.standard.bool(forKey: userDefaultsMigrationKey) {
            if let userDefaultsValue = UserDefaults.standard.string(forKey: key),
               let data = userDefaultsValue.data(using: .utf8) {
                // Migrate to Keychain
                save(data, forKey: key)
                // Remove from UserDefaults
                UserDefaults.standard.removeObject(forKey: key)
                // Mark migration as complete for this key
                UserDefaults.standard.set(true, forKey: userDefaultsMigrationKey)
                return data
            }
        }

        return nil
    }

    static func loadString(forKey key: String) -> String? {
        guard let data = load(forKey: key) else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func delete(forKey key: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
        ]
        SecItemDelete(query as CFDictionary)

        // Also clean up legacy key if it exists
        let legacyQuery: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: legacyService,
            kSecAttrAccount as String: key,
        ]
        SecItemDelete(legacyQuery as CFDictionary)
    }
}
