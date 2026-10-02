import AppKit
import SwiftUI
import Foundation

struct BRAINKWindowDescriptor: Codable, Identifiable, Hashable {
    let instanceID: String
    var logicalAddress: String
    var title: String
    var visible: Bool
    var windowNumber: Int
    var stateDigest: String
    var updatedAt: Date

    var id: String { instanceID }
}

struct BRAINKWindowProjectionView: View {
    let address: String
    let title: String
    let state: String

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Circle()
                    .fill(Color.green)
                    .frame(width: 10, height: 10)
                Text("BRAINK VISUAL RUNTIME")
                    .font(.headline.monospaced())
                Spacer()
                Text("ADDRESSABLE")
                    .font(.caption.bold().monospaced())
                    .foregroundStyle(.green)
            }

            Divider()

            Text(title)
                .font(.largeTitle.bold())

            VStack(alignment: .leading, spacing: 6) {
                Text("logical address")
                    .font(.caption.bold())
                    .foregroundStyle(.secondary)
                Text(address)
                    .font(.body.monospaced())
            }

            VStack(alignment: .leading, spacing: 6) {
                Text("projection state")
                    .font(.caption.bold())
                    .foregroundStyle(.secondary)
                Text(state)
                    .font(.body.monospaced())
                    .textSelection(.enabled)
            }

            Spacer()

            Text("The window is a persistent runtime projection. Its logical identity is independent of the native NSWindow carrier.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(24)
        .frame(minWidth: 620, minHeight: 360)
    }
}

@MainActor
final class BRAINKWindowRegistry: NSObject, ObservableObject, NSWindowDelegate {
    static let shared = BRAINKWindowRegistry()

    @Published private(set) var windows: [BRAINKWindowDescriptor] = []

    private var controllers: [String: NSWindowController] = [:]
    private var hosts: [String: NSHostingController<BRAINKWindowProjectionView>] = [:]
    private var commandTimer: Timer?
    private var commandOffset: UInt64 = 0

    private let rootURL: URL = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent(".braink/window-runtime", isDirectory: true)

    private var registryURL: URL { rootURL.appendingPathComponent("registry.json") }
    private var commandURL: URL { rootURL.appendingPathComponent("commands.jsonl") }

    private override init() {
        super.init()
        try? FileManager.default.createDirectory(at: rootURL, withIntermediateDirectories: true)
        loadRegistry()
        startCommandLoop()
    }

    func startCommandLoop() {
        guard commandTimer == nil else { return }
        commandTimer = Timer.scheduledTimer(withTimeInterval: 0.20, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.consumeCommands()
            }
        }
    }

    func open(
        logicalAddress: String,
        title: String = "BRAINK Visual",
        state: String = "ACTIVE"
    ) {
        if let controller = controllers[logicalAddress], let window = controller.window {
            window.makeKeyAndOrderFront(nil)
            return
        }

        let instanceID = "window-" + UUID().uuidString.lowercased()
        let view = BRAINKWindowProjectionView(
            address: logicalAddress,
            title: title,
            state: state
        )
        let host = NSHostingController(rootView: view)
        let window = NSWindow(
            contentViewController: host
        )
        window.title = title
        window.styleMask = [.titled, .closable, .miniaturizable, .resizable]
        window.setFrameAutosaveName("BRAINK." + instanceID)
        window.isRestorable = true
        window.delegate = self
        window.identifier = NSUserInterfaceItemIdentifier(logicalAddress)
        window.center()

        let controller = NSWindowController(window: window)
        controller.showWindow(nil)

        controllers[logicalAddress] = controller
        hosts[logicalAddress] = host

        let descriptor = BRAINKWindowDescriptor(
            instanceID: instanceID,
            logicalAddress: logicalAddress,
            title: title,
            visible: true,
            windowNumber: window.windowNumber,
            stateDigest: digest(title + "|" + logicalAddress + "|" + state),
            updatedAt: Date()
        )
        windows.append(descriptor)
        persist()
    }

    func project(
        logicalAddress: String,
        title: String? = nil,
        state: String
    ) {
        guard let host = hosts[logicalAddress] else { return }

        let current = windows.first(where: { $0.logicalAddress == logicalAddress })
        let nextTitle = title ?? current?.title ?? "BRAINK Visual"

        host.rootView = BRAINKWindowProjectionView(
            address: logicalAddress,
            title: nextTitle,
            state: state
        )

        if let controller = controllers[logicalAddress] {
            controller.window?.title = nextTitle
        }

        updateDescriptor(logicalAddress) { item in
            item.title = nextTitle
            item.stateDigest = digest(nextTitle + "|" + logicalAddress + "|" + state)
            item.visible = controllerIsVisible(logicalAddress)
            item.updatedAt = Date()
        }
        persist()
    }

    func readdress(
        from oldAddress: String,
        to newAddress: String
    ) {
        guard oldAddress != newAddress,
              let controller = controllers.removeValue(forKey: oldAddress),
              let host = hosts.removeValue(forKey: oldAddress)
        else { return }

        controllers[newAddress] = controller
        hosts[newAddress] = host
        controller.window?.identifier = NSUserInterfaceItemIdentifier(newAddress)

        if let index = windows.firstIndex(where: { $0.logicalAddress == oldAddress }) {
            windows[index].logicalAddress = newAddress
            windows[index].stateDigest = digest(
                windows[index].title + "|" + newAddress
            )
            windows[index].updatedAt = Date()
        }
        persist()
    }

    func focus(logicalAddress: String) {
        controllers[logicalAddress]?.window?.makeKeyAndOrderFront(nil)
        updateDescriptor(logicalAddress) { item in
            item.visible = true
            item.updatedAt = Date()
        }
        persist()
    }

    func close(logicalAddress: String) {
        guard let controller = controllers.removeValue(forKey: logicalAddress) else { return }
        hosts.removeValue(forKey: logicalAddress)
        controller.close()
        windows.removeAll { $0.logicalAddress == logicalAddress }
        persist()
    }

    func readback() -> [BRAINKWindowDescriptor] {
        windows
    }

    func windowWillClose(_ notification: Notification) {
        guard
            let window = notification.object as? NSWindow,
            let identifier = window.identifier?.rawValue
        else { return }

        let address = controllers.first(where: { $0.value.window === window })?.key ?? identifier
        controllers.removeValue(forKey: address)
        hosts.removeValue(forKey: address)
        windows.removeAll { $0.logicalAddress == address }
        persist()
    }

    private func controllerIsVisible(_ address: String) -> Bool {
        controllers[address]?.window?.isVisible ?? false
    }

    private func updateDescriptor(
        _ address: String,
        mutate: (inout BRAINKWindowDescriptor) -> Void
    ) {
        guard let index = windows.firstIndex(where: { $0.logicalAddress == address }) else { return }
        mutate(&windows[index])
    }

    private func persist() {
        do {
            let data = try JSONEncoder().encode(windows)
            try data.write(to: registryURL, options: .atomic)
        } catch {
            NSLog("BRAINK window registry persistence failed: %{public}@", error.localizedDescription)
        }
    }

    private func loadRegistry() {
        guard let data = try? Data(contentsOf: registryURL),
              let saved = try? JSONDecoder().decode([BRAINKWindowDescriptor].self, from: data)
        else { return }
        windows = saved
    }

    private func consumeCommands() {
        guard FileManager.default.fileExists(atPath: commandURL.path) else { return }

        do {
            let attributes = try FileManager.default.attributesOfItem(atPath: commandURL.path)
            let size = (attributes[.size] as? NSNumber)?.uint64Value ?? 0
            if size < commandOffset {
                commandOffset = 0
            }
            guard size > commandOffset else { return }

            let handle = try FileHandle(forReadingFrom: commandURL)
            try handle.seek(toOffset: commandOffset)
            let data = try handle.read(upToCount: Int(size - commandOffset)) ?? Data()
            commandOffset = size
            try handle.close()

            guard let text = String(data: data, encoding: .utf8) else { return }

            for line in text.split(whereSeparator: \.isNewline) {
                guard
                    let lineData = line.data(using: .utf8),
                    let command = try? JSONSerialization.jsonObject(with: lineData) as? [String: Any],
                    let action = command["action"] as? String
                else { continue }

                switch action {
                case "OPEN":
                    if let address = command["address"] as? String {
                        open(
                            logicalAddress: address,
                            title: command["title"] as? String ?? "BRAINK Visual",
                            state: command["state"] as? String ?? "ACTIVE"
                        )
                    }
                case "PROJECT":
                    if let address = command["address"] as? String {
                        project(
                            logicalAddress: address,
                            title: command["title"] as? String,
                            state: command["state"] as? String ?? "UPDATED"
                        )
                    }
                case "READDRESS":
                    if let from = command["from"] as? String,
                       let to = command["to"] as? String {
                        readdress(from: from, to: to)
                    }
                case "FOCUS":
                    if let address = command["address"] as? String {
                        focus(logicalAddress: address)
                    }
                case "CLOSE":
                    if let address = command["address"] as? String {
                        close(logicalAddress: address)
                    }
                default:
                    break
                }
            }
        } catch {
            NSLog("BRAINK window command read failed: %{public}@", error.localizedDescription)
        }
    }

    private func digest(_ value: String) -> String {
        var hash: UInt64 = 14695981039346656037
        for byte in value.utf8 {
            hash ^= UInt64(byte)
            hash &*= 1099511628211
        }
        return String(format: "%016llx", hash)
    }
}
