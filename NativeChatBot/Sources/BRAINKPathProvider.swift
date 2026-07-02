import Foundation

/// Provides environment-aware, configurable paths for BRAINK system.
/// Uses environment variables for configuration, falls back to relative paths.
enum BRAINKPathProvider {
    /// Gets the root directory for BRAINK application.
    /// Priority: BRAINK_ROOT env var > NativeChatBot directory
    static var brainkRoot: String {
        if let envRoot = ProcessInfo.processInfo.environment["BRAINK_ROOT"] {
            return envRoot
        }
        // Fall back to the directory containing NativeChatBot
        let nativeChatBotPath = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .path
        return URL(fileURLWithPath: nativeChatBotPath).deletingLastPathComponent().path
    }
    
    /// Gets the NativeChatBot directory.
    /// Priority: BRAINK_ROOT/NativeChatBot > computed from source location
    static var nativeChatBotRoot: String {
        if let envRoot = ProcessInfo.processInfo.environment["BRAINK_ROOT"] {
            return URL(fileURLWithPath: envRoot).appendingPathComponent("NativeChatBot").path
        }
        return URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .path
    }
    
    /// Gets the build output directory.
    /// Priority: BRAINK_BUILD_DIR env var > brainkRoot/build
    static var buildRoot: String {
        if let envBuildDir = ProcessInfo.processInfo.environment["BRAINK_BUILD_DIR"] {
            return envBuildDir
        }
        return URL(fileURLWithPath: brainkRoot).appendingPathComponent("build").path
    }
    
    /// Gets the IL-LLM runtime path.
    /// Priority: IL_LLM_RUNTIME_PATH env var > computed default
    static var ilLlmRuntimePath: String {
        if let envPath = ProcessInfo.processInfo.environment["IL_LLM_RUNTIME_PATH"] {
            return envPath
        }
        // Fall back to a configurable path relative to brainkRoot
        return URL(fileURLWithPath: brainkRoot).appendingPathComponent("il_llm_runtime").path
    }
    
    /// Gets the root for source files in NativeChatBot
    /// Used for file existence checks and reference documentation
    static var sourceRoot: String {
        if let envRoot = ProcessInfo.processInfo.environment["BRAINK_ROOT"] {
            return URL(fileURLWithPath: envRoot).appendingPathComponent("NativeChatBot").path
        }
        return nativeChatBotRoot
    }
    
    /// Gets the path to a specific source file.
    /// - Parameter fileName: The name of the Swift source file (e.g., "BRAINKChatEngine.swift")
    /// - Returns: Full path to the source file
    static func sourceFilePath(_ fileName: String) -> String {
        return URL(fileURLWithPath: nativeChatBotRoot)
            .appendingPathComponent("Sources")
            .appendingPathComponent(fileName)
            .path
    }
}
