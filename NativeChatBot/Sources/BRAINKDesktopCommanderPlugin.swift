import Foundation

enum BRAINKDesktopCommanderPlugin {
    private static let runtimePath = "runtime/host_control/braink_desktop_commander_runtime.py"

    static func status(repoRoot: String) -> String {
        let state = NSString(string: "~/.braink/host-control/desktop-commander-state.json").expandingTildeInPath
        guard FileManager.default.fileExists(atPath: state),
              let data = FileManager.default.contents(atPath: state),
              let text = String(data: data, encoding: .utf8) else {
            return "Desktop Commander host-control: UNOBSERVED"
        }
        return "Desktop Commander host-control state:\n\(text)"
    }

    static func launchRemote(repoRoot: String) -> String {
        let script = URL(fileURLWithPath: repoRoot).appendingPathComponent(runtimePath).path
        guard FileManager.default.fileExists(atPath: script) else {
            return "Desktop Commander plugin error: runtime script missing at \(script)"
        }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        process.arguments = ["python3", script, "run", "--mode", "remote"]
        do {
            try process.run()
            return "Desktop Commander host-control launch dispatched; pid=\(process.processIdentifier). Read runtime state before promoting READY."
        } catch {
            return "Desktop Commander plugin launch failed: \(error.localizedDescription)"
        }
    }

    static func selfTest(repoRoot: String) -> String {
        let script = URL(fileURLWithPath: repoRoot).appendingPathComponent(runtimePath).path
        let process = Process()
        let out = Pipe()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        process.arguments = ["python3", script, "self-test"]
        process.standardOutput = out
        process.standardError = out
        do {
            try process.run()
            process.waitUntilExit()
            let data = out.fileHandleForReading.readDataToEndOfFile()
            let text = String(data: data, encoding: .utf8) ?? ""
            return "Desktop Commander self-test exit=\(process.terminationStatus):\n\(text)"
        } catch {
            return "Desktop Commander self-test failed: \(error.localizedDescription)"
        }
    }
}
