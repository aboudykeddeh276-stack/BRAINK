import Foundation
#if canImport(CryptoKit)
import CryptoKit
#endif

struct BRAINKILLLMKnowledgeSnapshot: Codable {
    let architect: String
    let organization: String
    let signature: String
    let status: String
    let statusReason: String?
    let runtimePath: String
    let indexedFileCount: Int
    let loadedSnippetCount: Int
    let memoryBudgetChars: Int
    let memoryUsedChars: Int
    let growthEventCount: Int
    let topConcepts: [String]
    let lastRefreshAt: String
    let refreshedBy: String
}

struct BRAINKILLLMKnowledgeContext {
    let preview: String
    let matchedPaths: [String]
    let snapshot: BRAINKILLLMKnowledgeSnapshot
}

private struct BRAINKILLLMSnippet {
    let path: String
    let text: String
    let tokens: Set<String>
}

final class BRAINKILLLMKnowledgeCenter {
    private(set) var runtimePath: String
    private var snippets: [BRAINKILLLMSnippet] = []
    private var conceptCounts: [String: Int] = [:]
    private var lastFingerprint = ""
    private var lastRefreshDate: Date?
    private var growthEventCount = 0
    private var idfTable: [String: Double] = [:]
    private static let scoreTolerance: Double = 1e-9

    private let supportedExtensions: Set<String> = [
        "md", "txt", "json", "py", "ts", "tsx", "js", "swift",
        "cpp", "c", "go", "java", "yaml", "yml", "toml"
    ]
    private let maxInventoryFiles = 5_000
    private let maxSnippetFiles = 500
    private let maxSnippetChars = 700
    private let memoryBudgetChars = 120_000
    private let refreshCooldownSeconds: TimeInterval = 6

    init(runtimePath: String) {
        self.runtimePath = runtimePath
    }

    func setRuntimePath(_ newPath: String) {
        runtimePath = newPath.trimmingCharacters(in: .whitespacesAndNewlines)
        snippets.removeAll()
        lastFingerprint = ""
        lastRefreshDate = nil
    }

    func refresh(force: Bool, reason: String) -> BRAINKILLLMKnowledgeSnapshot {
        let trimmedPath = runtimePath.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedPath.isEmpty else {
            let snapshot = makeSnapshot(
                status: "BLOCKED",
                statusReason: "runtime_path_missing",
                indexedFileCount: 0,
                refreshedBy: reason
            )
            persist(snapshot)
            return snapshot
        }

        var isDirectory: ObjCBool = false
        guard FileManager.default.fileExists(atPath: trimmedPath, isDirectory: &isDirectory) else {
            let snapshot = makeSnapshot(
                status: "BLOCKED",
                statusReason: "runtime_path_not_found",
                indexedFileCount: 0,
                refreshedBy: reason
            )
            persist(snapshot)
            return snapshot
        }

        if !force,
           let lastRefreshDate,
           Date().timeIntervalSince(lastRefreshDate) <= refreshCooldownSeconds,
           !snippets.isEmpty {
            let snapshot = makeSnapshot(
                status: "DONE",
                statusReason: nil,
                indexedFileCount: snippets.count,
                refreshedBy: reason
            )
            persist(snapshot)
            return snapshot
        }

        let files = collectFiles(rootPath: trimmedPath, isDirectory: isDirectory.boolValue)
        if files.isEmpty {
            snippets = []
            let snapshot = makeSnapshot(
                status: "NOT DONE",
                statusReason: "no_supported_files_found",
                indexedFileCount: 0,
                refreshedBy: reason
            )
            persist(snapshot)
            return snapshot
        }

        let fingerprint = fingerprintFor(files: files)
        if !lastFingerprint.isEmpty && fingerprint != lastFingerprint {
            growthEventCount += 1
        }
        lastFingerprint = fingerprint

        var loaded: [BRAINKILLLMSnippet] = []
        var memoryUsed = 0
        for path in files {
            if loaded.count >= maxSnippetFiles || memoryUsed >= memoryBudgetChars { break }
            guard let data = try? Data(contentsOf: URL(fileURLWithPath: path)),
                  let text = String(data: data, encoding: .utf8) else {
                continue
            }
            let trimmed = String(text.prefix(maxSnippetChars))
                .trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmed.isEmpty else { continue }
            let remaining = max(0, memoryBudgetChars - memoryUsed)
            let bounded = String(trimmed.prefix(remaining))
            guard !bounded.isEmpty else { continue }
            memoryUsed += bounded.count
            loaded.append(BRAINKILLLMSnippet(path: path, text: bounded, tokens: Set(tokenize(bounded))))
        }

        snippets = loaded
        lastRefreshDate = Date()
        idfTable = buildIDF(from: loaded)

        let status = loaded.isEmpty ? "NOT DONE" : "DONE"
        let reasonText = loaded.isEmpty ? "supported_files_unreadable" : nil
        let snapshot = makeSnapshot(
            status: status,
            statusReason: reasonText,
            indexedFileCount: files.count,
            refreshedBy: reason
        )
        persist(snapshot)
        return snapshot
    }

    func context(for userInput: String) -> BRAINKILLLMKnowledgeContext {
        let baseline = refresh(force: false, reason: "always_on_query")
        guard baseline.status == "DONE", !snippets.isEmpty else {
            return BRAINKILLLMKnowledgeContext(
                preview: "",
                matchedPaths: [],
                snapshot: baseline
            )
        }

        let queryTokens = tokenize(userInput).filter { $0.count > 2 }
        let ranked = snippets.compactMap { snippet -> (BRAINKILLLMSnippet, Double)? in
            guard !queryTokens.isEmpty else { return (snippet, 1.0) }
            // TF-IDF: sum(tf(t,d) * idf(t)) over query tokens found in the document.
            // tf is normalised by document token count; idf uses smoothed corpus statistics.
            let score = queryTokens.reduce(0.0) { running, token in
                guard snippet.tokens.contains(token) else { return running }
                let tf = 1.0 / Double(max(snippet.tokens.count, 1))
                let idf = idfTable[token] ?? (log(Double(snippets.count + 2) / 2.0) + 1.0)
                return running + tf * idf
            }
            return score > 0 ? (snippet, score) : nil
        }
        .sorted { lhs, rhs in
            if abs(lhs.1 - rhs.1) < BRAINKILLLMKnowledgeCenter.scoreTolerance { return lhs.0.path < rhs.0.path }
            return lhs.1 > rhs.1
        }

        for token in queryTokens.prefix(24) {
            conceptCounts[token, default: 0] += 1
        }
        if let first = ranked.first {
            for token in first.0.tokens.sorted().prefix(16) {
                conceptCounts[token, default: 0] += 1
            }
        }

        let top = ranked.prefix(3)
        let preview = top.enumerated().map { index, item in
            let file = URL(fileURLWithPath: item.0.path).lastPathComponent
            let compact = item.0.text.replacingOccurrences(of: "\n", with: " ")
            return "\(index + 1). \(file) [tfidf=\(String(format: "%.4f", item.1))] \(compact)"
        }.joined(separator: "\n")

        let snapshot = makeSnapshot(
            status: baseline.status,
            statusReason: baseline.statusReason,
            indexedFileCount: baseline.indexedFileCount,
            refreshedBy: "always_on_query"
        )
        persist(snapshot)
        return BRAINKILLLMKnowledgeContext(
            preview: preview,
            matchedPaths: top.map { $0.0.path },
            snapshot: snapshot
        )
    }

    private func collectFiles(rootPath: String, isDirectory: Bool) -> [String] {
        if !isDirectory {
            let ext = URL(fileURLWithPath: rootPath).pathExtension.lowercased()
            if supportedExtensions.contains(ext) || ext.isEmpty {
                return [rootPath]
            }
            return []
        }

        var paths: [String] = []
        let rootURL = URL(fileURLWithPath: rootPath, isDirectory: true)
        if let enumerator = FileManager.default.enumerator(
            at: rootURL,
            includingPropertiesForKeys: [.isRegularFileKey],
            options: [.skipsHiddenFiles]
        ) {
            for case let fileURL as URL in enumerator {
                let isFile = (try? fileURL.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile) ?? false
                guard isFile else { continue }
                let ext = fileURL.pathExtension.lowercased()
                if supportedExtensions.contains(ext) || ext.isEmpty {
                    paths.append(fileURL.path)
                }
                if paths.count >= maxInventoryFiles { break }
            }
        }
        return paths.sorted()
    }

    private func fingerprintFor(files: [String]) -> String {
        var joined = ""
        for path in files.prefix(maxInventoryFiles) {
            let attrs = (try? FileManager.default.attributesOfItem(atPath: path)) ?? [:]
            let size = (attrs[.size] as? NSNumber)?.intValue ?? 0
            let date = (attrs[.modificationDate] as? Date)?.timeIntervalSince1970 ?? 0
            joined.append(path)
            joined.append("|")
            joined.append("\(size)")
            joined.append("|")
            joined.append("\(date)")
            joined.append("\n")
        }
        return stableHexDigest(Data(joined.utf8))
    }

    private func stableHexDigest(_ data: Data) -> String {
        #if canImport(CryptoKit)
        let digest = SHA256.hash(data: data)
        return digest.map { String(format: "%02x", $0) }.joined()
        #else
        var hash: UInt64 = 0xcbf29ce484222325
        for byte in data {
            hash ^= UInt64(byte)
            hash = hash &* 0x100000001b3
        }
        return String(format: "%016llx", hash)
        #endif
    }

    private func makeSnapshot(
        status: String,
        statusReason: String?,
        indexedFileCount: Int,
        refreshedBy: String
    ) -> BRAINKILLLMKnowledgeSnapshot {
        let usedChars = snippets.reduce(0) { $0 + $1.text.count }
        let topConcepts = conceptCounts
            .sorted { lhs, rhs in
                if lhs.value == rhs.value { return lhs.key < rhs.key }
                return lhs.value > rhs.value
            }
            .prefix(12)
            .map(\.key)

        return BRAINKILLLMKnowledgeSnapshot(
            architect: BRAINKConstants.architectName,
            organization: BRAINKConstants.organizationName,
            signature: BRAINKConstants.authorshipSignature,
            status: status,
            statusReason: statusReason,
            runtimePath: runtimePath,
            indexedFileCount: indexedFileCount,
            loadedSnippetCount: snippets.count,
            memoryBudgetChars: memoryBudgetChars,
            memoryUsedChars: usedChars,
            growthEventCount: growthEventCount,
            topConcepts: topConcepts,
            lastRefreshAt: ISO8601DateFormatter().string(from: Date()),
            refreshedBy: refreshedBy
        )
    }

    private func tokenize(_ text: String) -> [String] {
        text.lowercased()
            .components(separatedBy: CharacterSet.alphanumerics.inverted)
            .filter { $0.count >= 3 }
    }

    /// Builds an IDF (inverse document frequency) table from a corpus of snippets.
    /// IDF(t) = log(N / df(t)) + 1 where N = number of documents and df(t) = document
    /// frequency of token t.  The +1 smoothing prevents zero weights for common terms.
    private func buildIDF(from snippets: [BRAINKILLLMSnippet]) -> [String: Double] {
        let N = Double(max(snippets.count, 1))
        var df: [String: Int] = [:]
        for snippet in snippets {
            for token in snippet.tokens {
                df[token, default: 0] += 1
            }
        }
        return df.mapValues { count in log(N / Double(max(count, 1))) + 1.0 }
    }

    private func persist(_ snapshot: BRAINKILLLMKnowledgeSnapshot) {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        guard let data = try? encoder.encode(snapshot) else { return }
        let url = URL(fileURLWithPath: BRAINKConstants.illlmKnowledgeStatePath)
        do {
            try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            try data.write(to: url)
        } catch {
            return
        }
    }
}
