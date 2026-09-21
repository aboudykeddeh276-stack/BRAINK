import Foundation
import SwiftUI

enum BRAINKNodeCapabilityClass: String, Codable {
    case dumbNode = "DUMB_NODE"
    case smartNode = "SMART_NODE"
    case agenticNode = "AGENTIC_NODE"
    case systemNode = "SYSTEM_NODE"
}

struct BRAINKNodeObserverRelation: Codable, Hashable {
    let observerRelationID: String
    let observerContext: String

    enum CodingKeys: String, CodingKey {
        case observerRelationID = "observer_relation_id"
        case observerContext = "observer_context"
    }
}

struct BRAINKNodeIntegrationEdge: Codable, Hashable {
    let edgeID: String
    let direction: String?
    let source: String?
    let target: String?
    let interface: String?
    let state: String?

    enum CodingKeys: String, CodingKey {
        case edgeID = "edge_id"
        case direction, source, target, interface, state
    }
}

struct BRAINKNodeInstanceIdentity: Codable, Identifiable {
    let instanceID: String
    let templateID: String
    let definitionID: String
    let templateVersion: String
    let lineageRoot: String
    let proofRoot: String
    let capabilityClass: BRAINKNodeCapabilityClass?
    let observerRelations: [BRAINKNodeObserverRelation]
    let integrationEdges: [BRAINKNodeIntegrationEdge]

    var id: String { instanceID }

    enum CodingKeys: String, CodingKey {
        case instanceID = "instance_id"
        case templateID = "template_id"
        case definitionID = "definition_id"
        case templateVersion = "template_version"
        case lineageRoot = "lineage_root"
        case proofRoot = "proof_root"
        case capabilityClass = "capability_class"
        case observerRelations = "observer_relations"
        case integrationEdges = "integration_edges"
    }

    static func load(from url: URL) throws -> BRAINKNodeInstanceIdentity {
        let data = try Data(contentsOf: url)
        return try JSONDecoder().decode(BRAINKNodeInstanceIdentity.self, from: data)
    }
}

struct BRAINKTemplateBackedView<Content: View>: View {
    let node: BRAINKNodeInstanceIdentity
    @ViewBuilder let content: () -> Content

    var body: some View {
        content()
            .accessibilityIdentifier("braink.node.\(node.instanceID)")
            .environment(\.brainkNodeInstanceID, node.instanceID)
            .environment(\.brainkNodeTemplateID, node.templateID)
    }
}

private struct BRAINKNodeInstanceIDKey: EnvironmentKey {
    static let defaultValue = ""
}
private struct BRAINKNodeTemplateIDKey: EnvironmentKey {
    static let defaultValue = ""
}

extension EnvironmentValues {
    var brainkNodeInstanceID: String {
        get { self[BRAINKNodeInstanceIDKey.self] }
        set { self[BRAINKNodeInstanceIDKey.self] = newValue }
    }
    var brainkNodeTemplateID: String {
        get { self[BRAINKNodeTemplateIDKey.self] }
        set { self[BRAINKNodeTemplateIDKey.self] = newValue }
    }
}

enum BRAINKNodeTemplateLaw {
    static func validate(_ node: BRAINKNodeInstanceIdentity) -> [String] {
        var errors: [String] = []
        if node.instanceID.isEmpty { errors.append("INSTANCE_ID_EMPTY") }
        if node.templateID.isEmpty { errors.append("TEMPLATE_ID_EMPTY") }
        if node.definitionID.isEmpty { errors.append("DEFINITION_ID_EMPTY") }
        if node.templateVersion.isEmpty { errors.append("TEMPLATE_VERSION_EMPTY") }
        if node.lineageRoot.count != 64 { errors.append("LINEAGE_ROOT_INVALID") }
        if node.proofRoot.count != 64 { errors.append("PROOF_ROOT_INVALID") }
        return errors
    }
}


@MainActor
final class BRAINKNodeTemplateStore: ObservableObject {
    @Published private(set) var nativeDashboard: BRAINKNodeInstanceIdentity?
    @Published private(set) var nativeDashboardError: String = ""

    static var nativeDashboardURL: URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".braink/node-instances/node_hci_native-dashboard.json")
    }

    func reload() {
        do {
            let node = try BRAINKNodeInstanceIdentity.load(from: Self.nativeDashboardURL)
            let errors = BRAINKNodeTemplateLaw.validate(node)
            guard errors.isEmpty else {
                nativeDashboard = nil
                nativeDashboardError = errors.joined(separator: ",")
                return
            }
            guard node.templateID == "TPL_HCI_STATUS_CARD_V1",
                  node.definitionID == "HCI_PRIMITIVE_STATUS_CARD" else {
                nativeDashboard = nil
                nativeDashboardError = "NATIVE_DASHBOARD_TEMPLATE_IDENTITY_MISMATCH"
                return
            }
            nativeDashboard = node
            nativeDashboardError = ""
        } catch {
            nativeDashboard = nil
            nativeDashboardError = "NODE_TEMPLATE_INSTANCE_UNBOUND: \(error.localizedDescription)"
        }
    }
}
