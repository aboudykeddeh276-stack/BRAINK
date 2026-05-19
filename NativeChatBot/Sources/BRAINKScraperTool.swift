import Foundation

struct BRAINKScrapeResult: Codable {
    let status: String
    let url: String
    let title: String
    let linkCount: Int
    let links: [String]
    let excerpt: String
    let generatedAt: String
    let reason: String?
}

enum BRAINKScraperTool {
    static func scrape(urlString: String, maxLinks: Int = 15, excerptLimit: Int = 1200) async -> String {
        let normalized = normalizeURLString(urlString)
        guard let url = URL(string: normalized), ["http", "https"].contains(url.scheme?.lowercased() ?? "") else {
            return encodeResult(
                BRAINKScrapeResult(
                    status: "NOT DONE",
                    url: normalized,
                    title: "",
                    linkCount: 0,
                    links: [],
                    excerpt: "",
                    generatedAt: ISO8601DateFormatter().string(from: Date()),
                    reason: "invalid_or_unsupported_url"
                )
            )
        }

        var request = URLRequest(url: url)
        request.timeoutInterval = 20
        request.setValue("BRAINKNativeScraper/1.0", forHTTPHeaderField: "User-Agent")

        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse, 200..<300 ~= http.statusCode else {
                return encodeResult(
                    BRAINKScrapeResult(
                        status: "NOT DONE",
                        url: normalized,
                        title: "",
                        linkCount: 0,
                        links: [],
                        excerpt: "",
                        generatedAt: ISO8601DateFormatter().string(from: Date()),
                        reason: "http_status_not_ok"
                    )
                )
            }

            let html = String(data: data, encoding: .utf8) ?? ""
            let title = extractTitle(html)
            let links = Array(Set(extractLinks(html))).prefix(maxLinks).map { $0 }
            let excerpt = extractTextExcerpt(html, limit: excerptLimit)

            return encodeResult(
                BRAINKScrapeResult(
                    status: "DONE",
                    url: normalized,
                    title: title,
                    linkCount: links.count,
                    links: links,
                    excerpt: excerpt,
                    generatedAt: ISO8601DateFormatter().string(from: Date()),
                    reason: nil
                )
            )
        } catch {
            return encodeResult(
                BRAINKScrapeResult(
                    status: "NOT DONE",
                    url: normalized,
                    title: "",
                    linkCount: 0,
                    links: [],
                    excerpt: "",
                    generatedAt: ISO8601DateFormatter().string(from: Date()),
                    reason: "network_error: \(error.localizedDescription)"
                )
            )
        }
    }

    private static func normalizeURLString(_ input: String) -> String {
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.hasPrefix("http://") || trimmed.hasPrefix("https://") {
            return trimmed
        }
        return trimmed.isEmpty ? "https://example.com" : "https://\(trimmed)"
    }

    private static func extractTitle(_ html: String) -> String {
        guard let regex = try? NSRegularExpression(pattern: "<title[^>]*>(.*?)</title>", options: [.caseInsensitive, .dotMatchesLineSeparators]) else {
            return ""
        }
        let range = NSRange(location: 0, length: (html as NSString).length)
        guard let match = regex.firstMatch(in: html, options: [], range: range), match.numberOfRanges > 1 else {
            return ""
        }
        let title = (html as NSString).substring(with: match.range(at: 1))
        return decodeHTML(title).trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private static func extractLinks(_ html: String) -> [String] {
        guard let regex = try? NSRegularExpression(pattern: "href\\s*=\\s*['\\\"]([^'\\\"]+)['\\\"]", options: [.caseInsensitive]) else {
            return []
        }
        let ns = html as NSString
        let range = NSRange(location: 0, length: ns.length)
        let matches = regex.matches(in: html, options: [], range: range)
        return matches.compactMap { match in
            guard match.numberOfRanges > 1 else { return nil }
            let link = ns.substring(with: match.range(at: 1))
            return link.trimmingCharacters(in: .whitespacesAndNewlines)
        }.filter { !$0.isEmpty }
    }

    private static func extractTextExcerpt(_ html: String, limit: Int) -> String {
        let withoutScripts = html.replacingOccurrences(of: "<script[\\s\\S]*?</script>", with: " ", options: .regularExpression)
            .replacingOccurrences(of: "<style[\\s\\S]*?</style>", with: " ", options: .regularExpression)
        let stripped = withoutScripts.replacingOccurrences(of: "<[^>]+>", with: " ", options: .regularExpression)
        let compact = decodeHTML(stripped)
            .replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return String(compact.prefix(limit))
    }

    private static func decodeHTML(_ text: String) -> String {
        text
            .replacingOccurrences(of: "&amp;", with: "&")
            .replacingOccurrences(of: "&lt;", with: "<")
            .replacingOccurrences(of: "&gt;", with: ">")
            .replacingOccurrences(of: "&quot;", with: "\"")
            .replacingOccurrences(of: "&#39;", with: "'")
            .replacingOccurrences(of: "&nbsp;", with: " ")
    }

    private static func encodeResult(_ result: BRAINKScrapeResult) -> String {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        guard let data = try? encoder.encode(result),
              let text = String(data: data, encoding: .utf8) else {
            return "{\"status\":\"NOT DONE\",\"reason\":\"encoding_error\"}"
        }
        return text
    }
}
