import Foundation
#if canImport(AppKit)
import AppKit
#endif

enum BRAINKOAuthError: Error, LocalizedError {
    case missingPortalURL
    case missingServerURL
    case missingAppId
    case invalidLoginURL

    var errorDescription: String? {
        switch self {
        case .missingPortalURL:
            return "Missing OAuth portal URL (EXPO_PUBLIC_OAUTH_PORTAL_URL)."
        case .missingServerURL:
            return "Missing OAuth server URL (EXPO_PUBLIC_OAUTH_SERVER_URL)."
        case .missingAppId:
            return "Missing app ID (EXPO_PUBLIC_APP_ID)."
        case .invalidLoginURL:
            return "Unable to construct OAuth login URL."
        }
    }
}

enum BRAINKOAuth {
    static var portalURL: String {
        ProcessInfo.processInfo.environment["EXPO_PUBLIC_OAUTH_PORTAL_URL"] ?? ""
    }

    static var serverURL: String {
        ProcessInfo.processInfo.environment["EXPO_PUBLIC_OAUTH_SERVER_URL"] ?? ""
    }

    static var appId: String {
        ProcessInfo.processInfo.environment["EXPO_PUBLIC_APP_ID"] ?? ""
    }

    static var ownerOpenID: String {
        ProcessInfo.processInfo.environment["EXPO_PUBLIC_OWNER_OPEN_ID"] ?? ""
    }

    static var ownerName: String {
        ProcessInfo.processInfo.environment["EXPO_PUBLIC_OWNER_NAME"] ?? ""
    }

    static var apiBaseURL: String {
        ProcessInfo.processInfo.environment["EXPO_PUBLIC_API_BASE_URL"] ?? ""
    }

    static var deepLinkScheme: String {
        let bundleId = Bundle.main.bundleIdentifier ?? "com.app.aishell"
        let timestamp = bundleId.split(separator: ".").last.map(String.init)?
            .replacingOccurrences(of: "^t", with: "", options: .regularExpression) ?? ""
        return timestamp.isEmpty ? "manus" : "manus\(timestamp)"
    }

    static func resolvedAPIBaseURL() -> String {
        if !apiBaseURL.isEmpty {
            return apiBaseURL.replacingOccurrences(of: "/$", with: "", options: .regularExpression)
        }
        if !serverURL.isEmpty {
            return serverURL.replacingOccurrences(of: "/$", with: "", options: .regularExpression)
        }
        return ""
    }

    static func redirectURI() throws -> String {
        let base = resolvedAPIBaseURL()
        guard !base.isEmpty else {
            throw BRAINKOAuthError.missingServerURL
        }
        return "\(base)/api/oauth/callback"
    }

    static func loginURL() throws -> URL {
        guard !portalURL.isEmpty else {
            throw BRAINKOAuthError.missingPortalURL
        }
        guard !appId.isEmpty else {
            throw BRAINKOAuthError.missingAppId
        }
        let redirect = try redirectURI()
        guard var components = URLComponents(string: "\(portalURL)/app-auth") else {
            throw BRAINKOAuthError.invalidLoginURL
        }

        let stateData = Data(redirect.utf8)
        let state = stateData.base64EncodedString()

        components.queryItems = [
            URLQueryItem(name: "appId", value: appId),
            URLQueryItem(name: "redirectUri", value: redirect),
            URLQueryItem(name: "state", value: state),
            URLQueryItem(name: "type", value: "signIn"),
        ]

        guard let url = components.url else {
            throw BRAINKOAuthError.invalidLoginURL
        }
        return url
    }

    @discardableResult
    static func startOAuthLogin() throws -> URL {
        let url = try loginURL()
        #if canImport(AppKit)
        NSWorkspace.shared.open(url)
        #endif
        return url
    }
}
