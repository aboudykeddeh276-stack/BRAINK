import Foundation

final class BRAINKZeroLessAPIRuntime {
    private let coreRuntime = BRAINKZeroLessRuntime()

    func handleHTTPRequest(path: String, body: Data) async -> (status: Int, response: String, errorContext: String?) {
        let input = String(data: body, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        guard !input.isEmpty else {
            return (400, "Empty zero-less runtime request body for path \(path)", nil)
        }
        let result = await coreRuntime.executeProcessChain(userInput: input)

        if result.success {
            return (200, result.output, nil)
        }
        if let error = result.errorContext {
            return (500, result.output, error.toLiteralStateMapping())
        }
        return (500, "Unknown zero-less runtime error", nil)
    }
}
