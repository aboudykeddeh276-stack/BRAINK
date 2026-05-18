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
        HStack(spacing: 0) {
                VStack(spacing: 0) {
                HStack {
                    Text("BRAINK Native Chat Bot")
                        .font(.title3.bold())
                    Spacer()
                    Text("Native deterministic path")
                        .font(.caption)
                        .foregroundStyle(.secondary)
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

                Spacer()

                VStack(alignment: .leading, spacing: 4) {
                    Text("Runtime")
                        .font(.subheadline.bold())
                    Text("LOCAL_ONLY=\(ProcessInfo.processInfo.environment["BRAINK_CHAT_RUNTIME"] == nil ? "yes" : "no")")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    if let endpoint = ProcessInfo.processInfo.environment["BRAINK_CHAT_RUNTIME"] {
                        Text("endpoint: \(endpoint)")
                            .font(.caption2.monospaced())
                            .foregroundStyle(.secondary)
                    }
                    Text("IL_LLM_RUNTIME_PATH=\(engine.ilLlmRuntimePath)")
                        .font(.caption2.monospaced())
                        .foregroundStyle(.secondary)
                    Text("IL-LLM loaded: \(engine.ilLlmLoadedCount) docs")
                        .font(.caption2.monospaced())
                        .foregroundStyle(.secondary)
                    Text(engine.ilLlmLoadedStatus)
                        .font(.caption2.monospaced())
                        .foregroundStyle(.secondary)
                    if isDraggingILLLMTarget {
                        Text("Drop IL-LLM folder or file here to rebind runtime.")
                            .font(.caption)
                            .foregroundStyle(.yellow)
                    }
                }
                .padding()
            }
            .frame(minWidth: 320)
            .background(Color(NSColor.windowBackgroundColor).opacity(0.85))
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
