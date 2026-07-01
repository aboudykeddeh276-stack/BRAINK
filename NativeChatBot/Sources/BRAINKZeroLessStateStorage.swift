import Foundation

final class BRAINKZeroLessStateStorage {
    private var storageRoot: URL {
        URL(fileURLWithPath: BRAINKConstants.buildRoot).appendingPathComponent("zero_less_state_storage", isDirectory: true)
    }

    @discardableResult
    func persistState(index: ZeroLessIndex, data: [String: Any]) -> String? {
        guard let payload = encodedPayload(data, index: index) else { return nil }
        let targetURL = literalURL(for: index)
        do {
            try FileManager.default.createDirectory(at: storageRoot, withIntermediateDirectories: true)
            try payload.write(to: targetURL)
            return targetURL.path
        } catch {
            return nil
        }
    }

    func fetchState(index: ZeroLessIndex) -> [String: Any]? {
        let targetURL = literalURL(for: index)
        guard let data = try? Data(contentsOf: targetURL),
              let object = try? JSONSerialization.jsonObject(with: data),
              let dictionary = object as? [String: Any] else {
            return nil
        }
        return dictionary
    }

    private func literalURL(for index: ZeroLessIndex) -> URL {
        storageRoot.appendingPathComponent("state_\(index.rawValue).json")
    }

    private func encodedPayload(_ data: [String: Any], index: ZeroLessIndex) -> Data? {
        let enrichedData = data.merging([
            "literal_index_boundary": ZeroLessIndexEngine.mapToUncompressedLiteralState(index: index)
        ]) { current, _ in current }
        return try? JSONSerialization.data(withJSONObject: enrichedData, options: [.prettyPrinted, .sortedKeys])
    }
}
