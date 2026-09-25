import SwiftUI
import UniformTypeIdentifiers

struct MessageBubble: View {
    let message: ChatMessage

    private var bubbleColor: Color {
        switch message.role {
        case .user:
            return Color.blue.opacity(0.25)
        case .assistant:
            return Color.green.opacity(0.22)
        case .system:
            return Color.orange.opacity(0.22)
        }
    }

    private var textColor: Color {
        message.role == .user ? .blue : .primary
    }

    var body: some View {
        HStack {
            if message.role == .user { Spacer() }
            VStack(alignment: .leading, spacing: 4) {
                Text(message.text)
                    .font(.system(.body, design: .rounded))
                    .foregroundStyle(textColor)
                    .padding(10)
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(bubbleColor)
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(Color.white.opacity(0.12), lineWidth: 1)
                    )
                Text("route: \(message.route)")
                    .font(.caption.monospaced())
                    .foregroundStyle(.secondary)
            }
            if message.role != .user { Spacer() }
        }
    }
}

struct TraceRow: View {
    let trace: ModuleTrace

    var body: some View {
        HStack {
            Text(trace.module)
                .font(.caption.bold())
                .frame(width: 92, alignment: .leading)
            Text("\(trace.output)")
                .font(.caption2.monospaced())
                .foregroundStyle(.secondary)
            Spacer()
            Text(String(format: "%.2f", trace.confidence))
                .font(.caption2.monospaced())
                .foregroundStyle(trustColor(trace.confidence))
                .frame(width: 42, alignment: .trailing)
        }
    }

    func trustColor(_ confidence: Double) -> Color {
        if confidence > 0.65 { return .green }
        if confidence > 0.35 { return .yellow }
        return .red
    }
}

struct DashboardRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Text(label)
                .font(.caption.bold())
                .foregroundStyle(.secondary)
                .frame(width: 86, alignment: .leading)
            Text(value)
                .font(.caption2.monospaced())
                .foregroundStyle(.primary)
            Spacer()
        }
    }
}

struct DashboardCard<Content: View>: View {
    let title: String
    let content: Content

    init(title: String, @ViewBuilder content: () -> Content) {
        self.title = title
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.subheadline.bold())
            content
        }
        .padding(10)
        .background(Color.black.opacity(0.22))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(Color.white.opacity(0.08), lineWidth: 1)
        )
    }
}

struct DashboardOutcomeBadge: View {
    let outcome: String

    private var tint: Color {
        switch outcome {
        case "DONE":
            return .green
        case "REPAIR_REQUIRED":
            return .orange
        default:
            return .secondary
        }
    }

    var body: some View {
        Text(outcome)
            .font(.caption.bold())
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(tint.opacity(0.22))
            .clipShape(Capsule())
            .overlay(
                Capsule()
                    .stroke(tint.opacity(0.6), lineWidth: 1)
            )
    }
}

struct ChatInputBar: View {
    @ObservedObject var engine: BRAINKChatEngine
    @Binding var input: String

    var body: some View {
        HStack(spacing: 10) {
            TextField("Ask BRAINK…", text: $input, axis: .vertical)
                .textFieldStyle(.plain)
                .padding(10)
                .background(Color.black.opacity(0.2))
                .cornerRadius(8)
                .lineLimit(4)
                .onSubmit(send)

            Button("Send", action: send)
                .buttonStyle(.borderedProminent)
                .disabled(engine.isBusy || input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)

            Button("Clear") {
                engine.clear()
            }
            .buttonStyle(.bordered)
            .disabled(engine.messages.isEmpty)

            if engine.isBusy {
                ProgressView().scaleEffect(0.7)
            }
        }
    }

    private func send() {
        let copy = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !copy.isEmpty else { return }
        input = ""
        Task { await engine.send(userInput: copy) }
    }
}

struct BrainkNativeChatbotView: View {
    @StateObject private var engine = BRAINKChatEngine()
    @State private var input = ""
    @State private var isDraggingILLLMTarget = false

    private func handleILLLMDrop(_ providers: [NSItemProvider]) -> Bool {
        let fileProviders = providers.filter { $0.canLoadObject(ofClass: NSURL.self) }
        guard !fileProviders.isEmpty else { return false }

        for provider in fileProviders {
            provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier, options: nil) { item, _ in
                if let urlData = item as? Data,
                   let url = URL(dataRepresentation: urlData, relativeTo: nil) {
                    Task { @MainActor in engine.attachILLLMRuntimePath(url) }
                } else if let nsurl = item as? NSURL, let url = nsurl as URL? {
                    Task { @MainActor in engine.attachILLLMRuntimePath(url) }
                } else if let rawPath = item as? String {
                    Task { @MainActor in engine.attachILLLMRuntimePath(URL(fileURLWithPath: rawPath)) }
                }
            }
        }
        return true
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Ask BRAINK")
                        .font(.title2.bold())
                    Text("Describe the outcome. Runtime, model and VFS resolution stay behind the task.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
            }
            .padding()

            Divider()

            ScrollViewReader { proxy in
                ScrollView {
                    VStack(spacing: 10) {
                        ForEach(engine.messages) { message in
                            MessageBubble(message: message)
                                .id(message.id)
                        }
                    }
                    .padding()
                }
                .onChange(of: engine.messages.count) { _, _ in
                    if let last = engine.messages.last {
                        withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
                    }
                }
            }

            Divider()

            ChatInputBar(engine: engine, input: $input)
                .padding(.horizontal)
                .padding(.vertical, 8)
                .background(Color.black.opacity(0.12))
                .onDrop(of: [UTType.fileURL], isTargeted: $isDraggingILLLMTarget, perform: handleILLLMDrop)
                .overlay(
                    RoundedRectangle(cornerRadius: 0)
                        .stroke(isDraggingILLLMTarget ? Color.accentColor : Color.clear, lineWidth: 2)
                        .animation(.easeOut(duration: 0.2), value: isDraggingILLLMTarget)
                )

            if isDraggingILLLMTarget {
                Text("Drop a file or folder to make it available to the current BRAINK context.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .padding(.bottom, 6)
            }
        }
        .background(Color.black.opacity(0.03))
    }
}

@main
struct BRAINKNativeChatBotApp: App {
    var body: some Scene {
        WindowGroup {
            BRAINKWorkspaceShell()
                .frame(minWidth: 1080, minHeight: 720)
                .preferredColorScheme(.dark)
        }
        .windowStyle(.titleBar)
    }
}
