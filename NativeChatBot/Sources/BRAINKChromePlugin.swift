import Foundation
#if canImport(AppKit)
import AppKit
#endif

enum BRAINKChromePlugin {
    private static let chromeBundleID = "com.google.Chrome"

    static func isChromeInstalled() -> Bool {
        #if canImport(AppKit)
        return NSWorkspace.shared.urlForApplication(withBundleIdentifier: chromeBundleID) != nil
        #else
        return false
        #endif
    }

    static func open(urlString: String) -> String {
        let normalized = normalizeURLString(urlString)
        guard let url = URL(string: normalized) else {
            return "Chrome plugin error: invalid URL '\(urlString)'."
        }

        #if canImport(AppKit)
        if let chromeAppURL = NSWorkspace.shared.urlForApplication(withBundleIdentifier: chromeBundleID) {
            let config = NSWorkspace.OpenConfiguration()
            NSWorkspace.shared.open([url], withApplicationAt: chromeAppURL, configuration: config) { _, error in
                if let error {
                    print("Chrome plugin open error: \(error.localizedDescription)")
                }
            }
            return "Chrome plugin done: opened \(url.absoluteString)"
        }

        NSWorkspace.shared.open(url)
        return "Chrome plugin done (fallback): Chrome not installed, opened \(url.absoluteString) in default browser."
        #else
        return "Chrome plugin unavailable on this platform: validated URL \(url.absoluteString) but AppKit browser launch is macOS-only."
        #endif
    }

    static func statusText() -> String {
        if isChromeInstalled() {
            return "Chrome plugin ready: bundle \(chromeBundleID) detected."
        }
        return "Chrome plugin ready (fallback mode): bundle \(chromeBundleID) not found, default browser routing is active."
    }

    private static func normalizeURLString(_ input: String) -> String {
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.hasPrefix("http://") || trimmed.hasPrefix("https://") {
            return trimmed
        }
        if trimmed.isEmpty {
            return "https://www.google.com"
        }
        return "https://\(trimmed)"
    }
}
