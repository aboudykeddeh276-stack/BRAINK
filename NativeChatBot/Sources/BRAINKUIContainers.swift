import SwiftUI

struct ScreenContainer<Content: View>: View {
    let content: () -> Content
    var background: Color = Color.black.opacity(0.03)

    init(background: Color = Color.black.opacity(0.03), @ViewBuilder content: @escaping () -> Content) {
        self.background = background
        self.content = content
    }

    var body: some View {
        ZStack {
            background.ignoresSafeArea()
            content()
        }
    }
}

struct ThemedPanel<Content: View>: View {
    let content: () -> Content
    var panelColor: Color = Color(NSColor.windowBackgroundColor).opacity(0.85)

    init(panelColor: Color = Color(NSColor.windowBackgroundColor).opacity(0.85), @ViewBuilder content: @escaping () -> Content) {
        self.panelColor = panelColor
        self.content = content
    }

    var body: some View {
        content()
            .background(panelColor)
    }
}

// MARK: - NestedRuntimeDashboard

/// Skeleton dashboard for the Nested Runtime.
/// Binds to spectrum slots [1, 2, 3, 4, 5] (zero-less: no slot 0).
/// Slot meanings:
///   1 = state   (illlm_bundle)  — IL-LLM inventory snapshot
///   2 = memory  (illlm_query)   — knowledge retrieval context
///   3 = reasoning (self_sustained_coder) — self-existence coding output
///   4 = governance (kex_hyperdrive)     — transition/definition governance
///   5 = orchestration (reserved)        — native orchestration layer
///
/// IL-LLM circular path: slot 1 → slot 2 → slot 3 → slot 1 (3 becomes 1).
/// State bindings will be wired once Copilot's NestedRuntimeCore (PR #14) merges.
struct NestedRuntimeDashboard: View {
    /// Observable state for each spectrum slot (slots 1–5).
    /// These will be bound to Copilot's NestedRuntimeCore published properties on merge.
    var slot1Status: String = "PENDING"   // state
    var slot2Status: String = "PENDING"   // memory
    var slot3Status: String = "PENDING"   // reasoning
    var slot4Status: String = "PENDING"   // governance
    var slot5Status: String = "PENDING"   // orchestration (reserved)

    /// Circular path label, updated when slot 3 feeds back to slot 1.
    var circularPathLabel: String = "1 → 2 → 3 → 1"

    private let spectrumSlots: [(Int, String, String)] = [
        (1, "State",         "illlm_bundle"),
        (2, "Memory",        "illlm_query"),
        (3, "Reasoning",     "self_sustained_coder"),
        (4, "Governance",    "kex_hyperdrive"),
        (5, "Orchestration", "reserved")
    ]

    var body: some View {
        ThemedPanel {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text("Nested Runtime Dashboard")
                        .font(.headline)
                    Spacer()
                    Text("IL-LLM Path: \(circularPathLabel)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .padding([.horizontal, .top])

                ForEach(spectrumSlots, id: \.0) { slot, label, route in
                    NestedRuntimeSlotRow(
                        slotIndex: slot,
                        label: label,
                        route: route,
                        status: statusForSlot(slot)
                    )
                }

                Divider()

                Text("Proof: All spectrum slots ∈ [1,2,3,4,5] — zero-less, no slot 0.")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                    .padding([.horizontal, .bottom])
            }
        }
    }

    private func statusForSlot(_ slot: Int) -> String {
        switch slot {
        case 1: return slot1Status
        case 2: return slot2Status
        case 3: return slot3Status
        case 4: return slot4Status
        case 5: return slot5Status
        default: return "BLOCKED"
        }
    }
}

// MARK: - NestedRuntimeSlotRow

/// A single row displaying one spectrum slot in the NestedRuntimeDashboard.
struct NestedRuntimeSlotRow: View {
    let slotIndex: Int
    let label: String
    let route: String
    let status: String

    var body: some View {
        HStack(spacing: 8) {
            Text("[\(slotIndex)]")
                .font(.system(.caption, design: .monospaced))
                .foregroundColor(.secondary)
                .frame(width: 28, alignment: .leading)

            Text(label)
                .font(.system(.body, design: .default))
                .frame(width: 100, alignment: .leading)

            Text(route)
                .font(.system(.caption, design: .monospaced))
                .foregroundColor(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)

            Text(status)
                .font(.system(.caption, design: .monospaced))
                .foregroundColor(statusColor(status))
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(statusColor(status).opacity(0.12))
                .cornerRadius(4)
        }
        .padding(.horizontal)
    }

    private func statusColor(_ s: String) -> Color {
        switch s.uppercased() {
        case "COMPLETED": return .green
        case "PENDING":   return .orange
        case "BLOCKED":   return .red
        case "FAILED":    return .red
        default:          return .secondary
        }
    }
}
