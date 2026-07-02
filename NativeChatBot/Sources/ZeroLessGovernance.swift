import Foundation

enum ZeroLessIndex: Int, CaseIterable, Codable {
    case stateNeg3 = -3
    case stateNeg2 = -2
    case observerSingular1 = 1
    case statePos2 = 2
    case statePos3 = 3
}

enum ZeroLessGovernanceError: LocalizedError {
    case invalidIndex(Int)

    var errorDescription: String? {
        switch self {
        case .invalidIndex(let index):
            return "Zero-less governance rejected index \(index). Allowed indices: [-3, -2, 1, 2, 3]."
        }
    }
}

enum ZeroLessGovernance {
    static let allowedIndexSpectrum: [Int] = ZeroLessIndex.allCases.map(\.rawValue)

    static func validate(index: Int) throws -> ZeroLessIndex {
        guard let zeroLessIndex = ZeroLessIndex(rawValue: index) else {
            throw ZeroLessGovernanceError.invalidIndex(index)
        }
        return zeroLessIndex
    }

    static func hardwareSlot(for index: Int) throws -> String {
        let validated = try validate(index: index)
        return "HARDWARE_SLOT_\(validated.rawValue)"
    }
}

enum BRAINKRouteIdentifier: String, CaseIterable, Codable {
    case frontierSeal = "frontier_seal"
    case lineRegistryAdd = "line_registry_add"
    case lineRegistryList = "line_registry_list"
    case illlmUpdate = "illlm_update"
    case illlmCompatibility = "illlm_compatibility"
    case illlmWorkflow = "illlm_workflow"
    case innerRuntime = "inner_runtime"
    case selfSustainedCoder = "self_sustained_coder"
    case kexHyperdrive = "kex_hyperdrive"
    case knowledgeCenterStatus = "knowledge_center_status"
    case authOAuth = "auth.oauth"
    case chromeBrowser = "chrome_browser"
    case scrapeTool = "scrape_tool"
    case stackAudit = "stack_audit"
    case learnAllFiles = "learn_all_files"
    case runtimeTrace = "runtime_trace"
    case proofPacket = "proof_packet"
    case constraintFlags = "constraint_flags"
    case moduleManifest = "module_manifest"
    case platformInitialize = "platform_initialize"
    case platformStatus = "platform_status"
    case platformIndex = "platform_index"
    case platformSearch = "platform_search"
    case platformExecute = "platform_execute"
    case platformPacket = "platform_packet"
    case build = "build"
    case illlmBundle = "illlm_bundle"
    case illlmBootstrap = "illlm_bootstrap"
    case illlmQuery = "illlm_query"
    case alignCheck = "align-check"
    case evidence = "evidence"
    case general = "general"

    static func from(rawRoute: String) -> BRAINKRouteIdentifier {
        BRAINKRouteIdentifier(rawValue: rawRoute) ?? .general
    }

    var governanceRouteID: String {
        switch self {
        case .frontierSeal: return "route:sys:frontier_seal"
        case .lineRegistryAdd: return "route:sys:line_registry_add"
        case .lineRegistryList: return "route:sys:line_registry_list"
        case .illlmUpdate: return "route:engine:illlm_update"
        case .illlmCompatibility: return "route:engine:illlm_compatibility"
        case .illlmWorkflow: return "route:engine:illlm_workflow"
        case .innerRuntime: return "route:engine:inner_runtime"
        case .selfSustainedCoder: return "route:engine:self_sustained_coder"
        case .kexHyperdrive: return "route:engine:kex_hyperdrive"
        case .knowledgeCenterStatus: return "route:engine:knowledge_center_status"
        case .authOAuth: return "route:svc:oauth"
        case .chromeBrowser: return "route:svc:chrome_browser"
        case .scrapeTool: return "route:svc:scrape_tool"
        case .stackAudit: return "route:sys:stack_audit"
        case .learnAllFiles: return "route:engine:learn_all_files"
        case .runtimeTrace: return "route:sys:runtime_trace"
        case .proofPacket: return "route:svc:proof_packet"
        case .constraintFlags: return "route:sys:constraint_flags"
        case .moduleManifest: return "route:sys:module_manifest"
        case .platformInitialize: return "route:svc:platform_initialize"
        case .platformStatus: return "route:svc:platform_status"
        case .platformIndex: return "route:svc:platform_index"
        case .platformSearch: return "route:svc:platform_search"
        case .platformExecute: return "route:svc:platform_execute"
        case .platformPacket: return "route:svc:platform_packet"
        case .build: return "route:sys:build"
        case .illlmBundle: return "route:engine:illlm_bundle"
        case .illlmBootstrap: return "route:engine:illlm_bootstrap"
        case .illlmQuery: return "route:engine:illlm_query"
        case .alignCheck: return "route:sys:align_check"
        case .evidence: return "route:svc:evidence"
        case .general: return "route:sys:general"
        }
    }
}
