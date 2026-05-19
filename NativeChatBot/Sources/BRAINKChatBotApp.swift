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

struct ChatInputBar: View {
    @ObservedObject var engine: BRAINKChatEngine
    @Binding var input: String

    var body: some View {
        HStack(spacing: 10) {
            TextField("Ask BRAINK native bot...", text: $input, axis: .vertical)
                .textFieldStyle(.plain)
                .padding(10)
                .background(Color.black.opacity(0.2))
                .cornerRadius(8)
                .lineLimit(4)

            Button("Send") {
                Task {
                    let copy = input
                    input = ""
                    await engine.send(userInput: copy)
                }
            }
            .buttonStyle(.borderedProminent)
            .disabled(engine.isBusy || input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)

            Button("Clear") {
                engine.clear()
            }
            .buttonStyle(.bordered)
            .disabled(engine.messages.isEmpty)
            
            Button("Load My Data") {
                engine.reloadILLLMBundle()
            }
            .buttonStyle(.borderedProminent)
            .disabled(engine.isBusy)

            Button("Audit Stack") {
                Task {
                    await engine.send(userInput: "stack audit line for line module alignment")
                }
            }
            .buttonStyle(.bordered)
            .disabled(engine.isBusy)

            Button("Learn Files") {
                Task {
                    await engine.send(userInput: "learn every last file and code and skill")
                }
            }
            .buttonStyle(.bordered)
            .disabled(engine.isBusy)

            Button("Knowledge") {
                Task {
                    await engine.send(userInput: "knowledge center status")
                }
            }
            .buttonStyle(.bordered)
            .disabled(engine.isBusy)

            if engine.isBusy {
                ProgressView().scaleEffect(0.7)
            }
        }
    }
}

struct BrainkNativeChatbotView: View {
    @StateObject private var engine = BRAINKChatEngine()
    @State private var input = ""
    @State private var isDraggingILLLMTarget = false

    private func handleILLLMDrop(_ providers: [NSItemProvider]) -> Bool {
        let fileProviders = providers.filter { $0.canLoadObject(ofClass: NSURL.self) }
        guard !fileProviders.isEmpty else {
            return false
        }

        for provider in fileProviders {
            provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier, options: nil) { item, _ in
                if let urlData = item as? Data,
                   let url = URL(dataRepresentation: urlData, relativeTo: nil) {
                    Task { @MainActor in
                        engine.attachILLLMRuntimePath(url)
                    }
                } else if let nsurl = item as? NSURL, let url = nsurl as URL? {
                    Task { @MainActor in
                        engine.attachILLLMRuntimePath(url)
                    }
                } else if let rawPath = item as? String {
                    let url = URL(fileURLWithPath: rawPath)
                    Task { @MainActor in
                        engine.attachILLLMRuntimePath(url)
                    }
                }
            }
        }
        return true
    }

    var body: some View {
        ScreenContainer {
            HStack(spacing: 0) {
                VStack(spacing: 0) {
                HStack {
                    Text(BRAINKConstants.productSignature)
                        .font(.title3.bold())
                    Spacer()
                    Text("Native deterministic path")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .padding()

                HStack {
                    Text(BRAINKConstants.authorshipSignature)
                        .font(.caption2.monospaced())
                        .foregroundStyle(.secondary)
                    Spacer()
                }
                .padding(.horizontal)

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
                            withAnimation {
                                proxy.scrollTo(last.id, anchor: .bottom)
                            }
                        }
                    }
                }

                Divider()

                VStack(spacing: 8) {
                ChatInputBar(engine: engine, input: $input)
                        .padding(.horizontal)
                        .padding(.vertical, 8)
                        .onDrop(of: [UTType.fileURL], isTargeted: $isDraggingILLLMTarget, perform: handleILLLMDrop)
                }
                .background(Color.black.opacity(0.12))
                .overlay(
                    RoundedRectangle(cornerRadius: 0)
                        .stroke(isDraggingILLLMTarget ? Color.accentColor : Color.clear, lineWidth: 2)
                        .animation(.easeOut(duration: 0.2), value: isDraggingILLLMTarget)
                )
            }
            .frame(minWidth: 700)
            .background(Color.black.opacity(0.03))

            Divider()

            ThemedPanel {
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text("Module Trace")
                            .font(.headline)
                        Spacer()
                        Button("Clear traces") {
                            engine.clearTraces()
                        }
                        .buttonStyle(.plain)
                    }
                    .padding([.horizontal, .top])

                    List {
                        ForEach(engine.traces) { trace in
                            TraceRow(trace: trace)
                        }
                    }

                    ScrollView {
                        VStack(alignment: .leading, spacing: 10) {
                            DashboardCard(title: "User Dashboard") {
                                DashboardRow(label: "Product", value: BRAINKConstants.productSignature)
                                DashboardRow(label: "Author", value: BRAINKConstants.architectName)
                                DashboardRow(label: "Org", value: BRAINKConstants.organizationName)
                                DashboardRow(label: "Session", value: engine.dashboardLastRoute)
                            }

                            DashboardCard(title: "Runtime") {
                                DashboardRow(label: "Mode", value: engine.runtimeModeLabel)
                                DashboardRow(label: "Endpoint", value: engine.runtimeEndpointLabel)
                                DashboardRow(label: "Path", value: engine.ilLlmRuntimePath)
                                DashboardRow(label: "Docs", value: "\(engine.ilLlmLoadedCount)")
                                DashboardRow(label: "Load", value: engine.ilLlmLoadedStatus)
                            }

                            DashboardCard(title: "Knowledge") {
                                DashboardRow(label: "Growth", value: engine.ilLlmGrowthStatus)
                                DashboardRow(label: "Memory", value: engine.ilLlmMemoryStatus)
                                DashboardRow(label: "Concepts", value: engine.ilLlmTopConceptsText)
                            }

                            DashboardCard(title: "Activity") {
                                DashboardRow(
                                    label: "Messages",
                                    value: "\(engine.messages.count) total | u:\(engine.dashboardUserMessageCount) a:\(engine.dashboardAssistantMessageCount) s:\(engine.dashboardSystemMessageCount)"
                                )
                                DashboardRow(label: "Traces", value: "\(engine.traces.count)")
                                DashboardRow(label: "Next", value: engine.dashboardNextAction)
                            }

                            if isDraggingILLLMTarget {
                                Text("Drop IL-LLM folder or file to rebind runtime.")
                                    .font(.caption)
                                    .foregroundStyle(.yellow)
                            }
                        }
                        .padding()
                    }
                }
            }
            .frame(minWidth: 320)
        }
        }
    }
}

@main
struct BRAINKNativeChatBotApp: App {
    var body: some Scene {
        WindowGroup {
            BrainkNativeChatbotView()
                .frame(minWidth: 1080, minHeight: 720)
                .preferredColorScheme(.dark)
        }
        .windowStyle(.titleBar)
    }
}
