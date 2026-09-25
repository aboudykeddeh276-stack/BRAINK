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
            }
            if message.role != .user { Spacer() }
        }
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
                    Text("Describe the outcome. BRAINK handles the supporting system work behind it.")
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
                        ForEach(engine.messages.filter { $0.role != .system }) { message in
                            MessageBubble(message: message)
                                .id(message.id)
                        }
                    }
                    .padding()
                }
                .onChange(of: engine.messages.count) { _ in
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
