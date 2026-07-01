import Foundation

final class BRAINKZeroLessAPIRuntime {
    private let coreRuntime = BRAINKZeroLessRuntime()

    func handleHTTPRequest(path: String, body: Data) async -> (status: Int, response: String, errorContext: String?) {
        let rawInput = String(data: body, encoding: .utf8) ?? ""
        let input = rawInput.isEmpty ? path : rawInput
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
