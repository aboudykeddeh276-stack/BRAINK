import SwiftUI
import AppKit
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
        HStack(alignment: .bottom, spacing: 12) {
            TextField("Describe what you want to get done…", text: $input, axis: .vertical)
                .textFieldStyle(.plain)
                .padding(12)
                .background(Color.white.opacity(0.06))
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .lineLimit(5)

            Button("Send") {
                Task {
                    let copy = input
                    input = ""
                    await engine.send(userInput: copy)
                }
            }
            .buttonStyle(.borderedProminent)
            .disabled(engine.isBusy || input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)

            if engine.isBusy {
                ProgressView()
                    .controlSize(.small)
            }
        }
    }
}

enum WorkspaceSection: String, CaseIterable, Identifiable {
    case home = "Home"
    case ai = "AI"
    case documents = "Documents"
    case files = "Files"
    case legal = "Legal work"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .home: return "house"
        case .ai: return "sparkles"
        case .documents: return "doc.text"
        case .files: return "folder"
        case .legal: return "briefcase"
        }
    }
}

struct WorkflowCard<Content: View>: View {
    let title: String
    let subtitle: String
    let icon: String
    let content: Content

    init(title: String, subtitle: String, icon: String, @ViewBuilder content: () -> Content) {
        self.title = title
        self.subtitle = subtitle
        self.icon = icon
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 10) {
                Image(systemName: icon)
                    .font(.title3)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.title3.weight(.semibold))
                    Text(subtitle)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                Spacer()
            }
            content
        }
        .padding(20)
        .background(Color.white.opacity(0.055))
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color.white.opacity(0.08), lineWidth: 1)
        )
    }
}

struct StatusBar: View {
    @ObservedObject var engine: BRAINKChatEngine

    private var stateText: String {
        if engine.isBusy { return "Working" }
        if engine.ilLlmLoadedCount > 0 { return "Ready" }
        return "Ready"
    }

    var body: some View {
        HStack(spacing: 8) {
            Circle()
                .fill(engine.isBusy ? Color.orange : Color.green)
                .frame(width: 7, height: 7)
            Text(stateText)
                .font(.caption)
            Text("•")
                .foregroundStyle(.tertiary)
            Text("Your work is saved automatically")
                .font(.caption)
                .foregroundStyle(.secondary)
            Spacer()
            if engine.isBusy {
                Text("Processing")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 7)
        .background(Color.black.opacity(0.18))
    }
}

struct HomeWorkspaceView: View {
    @ObservedObject var engine: BRAINKChatEngine
    @Binding var selection: WorkspaceSection
    @Binding var input: String
    @Binding var showDiagnostics: Bool
    @Binding var showAdministration: Bool

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("What do you need to get done?")
                        .font(.system(size: 34, weight: .bold))
                    Text("Ask BRAINK to handle the work, or open the area you need.")
                        .font(.title3)
                        .foregroundStyle(.secondary)
                }

                WorkflowCard(
                    title: "Ask BRAINK",
                    subtitle: "Describe the outcome. BRAINK handles the underlying workflow.",
                    icon: "sparkles"
                ) {
                    HStack(spacing: 10) {
                        TextField("For example: prepare this matter from the documents I have…", text: $input)
                            .textFieldStyle(.plain)
                            .padding(11)
                            .background(Color.black.opacity(0.22))
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                        Button("Ask") {
                            selection = .ai
                        }
                        .buttonStyle(.borderedProminent)
                    }
                }

                HStack(alignment: .top, spacing: 16) {
                    WorkflowCard(
                        title: "Documents",
                        subtitle: "Create, review and prepare documents.",
                        icon: "doc.text"
                    ) {
                        HStack {
                            Button("Open documents") { selection = .documents }
                                .buttonStyle(.borderedProminent)
                            Button("New document") {
                                input = "Create a new document"
                                selection = .ai
                            }
                            .buttonStyle(.bordered)
                        }
                    }

                    WorkflowCard(
                        title: "Files",
                        subtitle: "Browse files and bring source material into your work.",
                        icon: "folder"
                    ) {
                        Button("Browse files") { selection = .files }
                            .buttonStyle(.borderedProminent)
                    }
                }

                WorkflowCard(
                    title: "Legal work",
                    subtitle: "Start a matter, organise evidence and prepare a legal work package.",
                    icon: "briefcase"
                ) {
                    HStack {
                        Button("Open legal work") { selection = .legal }
                            .buttonStyle(.borderedProminent)
                        Button("Start a matter") {
                            input = "Start a new legal matter"
                            selection = .ai
                        }
                        .buttonStyle(.bordered)
                    }
                }
            }
            .frame(maxWidth: 980, alignment: .leading)
            .padding(32)
        }
        .toolbar {
            ToolbarItemGroup(placement: .automatic) {
                Button("Diagnostics") { showDiagnostics = true }
                    .help("Technical diagnostics and maintenance")
                Button("Administration") { showAdministration = true }
                    .help("Administrative controls")
            }
        }
    }
}

struct AIWorkspaceView: View {
    @ObservedObject var engine: BRAINKChatEngine
    @Binding var input: String
    @State private var isDragging = false

    private func handleDrop(_ providers: [NSItemProvider]) -> Bool {
        let fileProviders = providers.filter { $0.canLoadObject(ofClass: NSURL.self) }
        guard !fileProviders.isEmpty else { return false }
        for provider in fileProviders {
            provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier, options: nil) { item, _ in
                if let data = item as? Data, let url = URL(dataRepresentation: data, relativeTo: nil) {
                    Task { @MainActor in engine.attachILLLMRuntimePath(url) }
                } else if let nsurl = item as? NSURL, let url = nsurl as URL? {
                    Task { @MainActor in engine.attachILLLMRuntimePath(url) }
                }
            }
        }
        return true
    }

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(spacing: 12) {
                        if engine.messages.isEmpty {
                            VStack(alignment: .leading, spacing: 10) {
                                Text("Ask BRAINK")
                                    .font(.system(size: 30, weight: .bold))
                                Text("Describe the result you need. You do not need to know which runtime, service or tool performs it.")
                                    .foregroundStyle(.secondary)
                            }
                            .frame(maxWidth: 820, alignment: .leading)
                            .padding(.top, 50)
                        }
                        ForEach(engine.messages) { message in
                            MessageBubble(message: message)
                                .id(message.id)
                        }
                    }
                    .frame(maxWidth: 900)
                    .padding(28)
                }
                .onChange(of: engine.messages.count) { _, _ in
                    if let last = engine.messages.last {
                        withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
                    }
                }
            }

            Divider()

            ChatInputBar(engine: engine, input: $input)
                .padding(16)
                .onDrop(of: [UTType.fileURL], isTargeted: $isDragging, perform: handleDrop)
                .overlay {
                    if isDragging {
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(Color.accentColor, lineWidth: 2)
                            .padding(8)
                    }
                }
        }
    }
}

struct DocumentsWorkspaceView: View {
    @ObservedObject var engine: BRAINKChatEngine
    @Binding var input: String
    @State private var showImporter = false
    @State private var selectedFiles: [URL] = []

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                HStack {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Documents")
                            .font(.system(size: 30, weight: .bold))
                        Text("Create and work with documents without managing the underlying storage.")
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button("Open files") { showImporter = true }
                        .buttonStyle(.borderedProminent)
                    Button("New document") {
                        input = "Create a new document"
                    }
                    .buttonStyle(.bordered)
                }

                WorkflowCard(
                    title: "Start with what you have",
                    subtitle: "Bring source material in, then ask BRAINK what you want done with it.",
                    icon: "arrow.down.doc"
                ) {
                    VStack(alignment: .leading, spacing: 10) {
                        if selectedFiles.isEmpty {
                            Text("No files selected in this session.")
                                .foregroundStyle(.secondary)
                        } else {
                            ForEach(selectedFiles, id: \.self) { url in
                                HStack {
                                    Image(systemName: "doc")
                                    Text(url.lastPathComponent)
                                    Spacer()
                                    Button("Open") { NSWorkspace.shared.open(url) }
                                        .buttonStyle(.borderless)
                                }
                            }
                        }
                        Button("Add source files") { showImporter = true }
                            .buttonStyle(.bordered)
                    }
                }

                WorkflowCard(
                    title: "Document actions",
                    subtitle: "Use plain-language tasks rather than system commands.",
                    icon: "wand.and.stars"
                ) {
                    HStack(spacing: 10) {
                        Button("Summarise a document") { input = "Summarise the selected document" }
                        Button("Prepare a draft") { input = "Prepare a draft from the selected material" }
                        Button("Review for gaps") { input = "Review the selected material for missing information" }
                    }
                    .buttonStyle(.bordered)
                }
            }
            .frame(maxWidth: 980, alignment: .leading)
            .padding(32)
        }
        .fileImporter(
            isPresented: $showImporter,
            allowedContentTypes: [.item],
            allowsMultipleSelection: true
        ) { result in
            switch result {
            case .success(let urls):
                selectedFiles = urls
                for url in urls { engine.attachILLLMRuntimePath(url) }
            case .failure(let error):
                input = "I could not open the selected files: \(error.localizedDescription)"
            }
        }
    }
}

struct FilesWorkspaceView: View {
    @ObservedObject var engine: BRAINKChatEngine
    @State private var showImporter = false
    @State private var selectedFiles: [URL] = []

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                HStack {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Files")
                            .font(.system(size: 30, weight: .bold))
                        Text("Browse and open source material. The system handles the plumbing behind the task.")
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button("Browse") { showImporter = true }
                        .buttonStyle(.borderedProminent)
                }

                WorkflowCard(
                    title: "Selected files",
                    subtitle: "Files you choose become available to the workspace.",
                    icon: "folder"
                ) {
                    if selectedFiles.isEmpty {
                        Text("Choose files to begin.")
                            .foregroundStyle(.secondary)
                    } else {
                        VStack(alignment: .leading, spacing: 8) {
                            ForEach(selectedFiles, id: \.self) { url in
                                HStack {
                                    Image(systemName: "doc")
                                    Text(url.lastPathComponent)
                                    Spacer()
                                    Button("Open") { NSWorkspace.shared.open(url) }
                                        .buttonStyle(.borderless)
                                }
                            }
                        }
                    }
                }
            }
            .frame(maxWidth: 980, alignment: .leading)
            .padding(32)
        }
        .fileImporter(
            isPresented: $showImporter,
            allowedContentTypes: [.item],
            allowsMultipleSelection: true
        ) { result in
            if case .success(let urls) = result {
                selectedFiles = urls
                for url in urls { engine.attachILLLMRuntimePath(url) }
            }
        }
    }
}

struct LegalWorkspaceView: View {
    @Binding var input: String

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Legal work")
                        .font(.system(size: 30, weight: .bold))
                    Text("Organise a matter, evidence and documents as one workflow.")
                        .foregroundStyle(.secondary)
                }

                WorkflowCard(
                    title: "Start a matter",
                    subtitle: "Begin with the facts and source material you have.",
                    icon: "briefcase"
                ) {
                    Button("Start a matter") {
                        input = "Start a new legal matter. Begin with the facts and source material I provide."
                    }
                    .buttonStyle(.borderedProminent)
                }

                HStack(alignment: .top, spacing: 16) {
                    WorkflowCard(
                        title: "Evidence",
                        subtitle: "Organise evidence and identify gaps.",
                        icon: "doc.text.magnifyingglass"
                    ) {
                        Button("Review evidence") {
                            input = "Review the evidence for this matter, organise it chronologically, and identify source gaps."
                        }
                    }

                    WorkflowCard(
                        title: "Prepare documents",
                        subtitle: "Turn the matter record into a structured document package.",
                        icon: "doc.badge.gearshape"
                    ) {
                        Button("Prepare package") {
                            input = "Prepare a structured document package for this legal matter from the available source material."
                        }
                    }
                }
                .buttonStyle(.bordered)
            }
            .frame(maxWidth: 980, alignment: .leading)
            .padding(32)
        }
    }
}

struct DiagnosticsPanel: View {
    @ObservedObject var engine: BRAINKChatEngine
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 12) {
                Text("Technical diagnostics")
                    .font(.title2.bold())
                Text("This panel is intentionally separate from normal work.")
                    .foregroundStyle(.secondary)

                List {
                    Section("Execution trace") {
                        ForEach(engine.traces) { trace in
                            TraceRow(trace: trace)
                        }
                    }
                    Section("Audit") {
                        DashboardRow(label: "Outcome", value: engine.dashboardAuditOutcome)
                        DashboardRow(label: "Alignment", value: engine.dashboardAuditWeightedAlignment)
                        DashboardRow(label: "Counts", value: engine.dashboardAuditCounts)
                        DashboardRow(label: "Next", value: engine.dashboardAuditNextMove)
                    }
                    Section("Learning state") {
                        DashboardRow(label: "Loaded", value: engine.ilLlmLoadedStatus)
                        DashboardRow(label: "Growth", value: engine.ilLlmGrowthStatus)
                        DashboardRow(label: "Memory", value: engine.ilLlmMemoryStatus)
                    }
                }
            }
            .padding()
            .navigationTitle("Diagnostics")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
        .frame(minWidth: 720, minHeight: 560)
    }
}

struct AdministrationPanel: View {
    @ObservedObject var engine: BRAINKChatEngine
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section("Workspace administration") {
                    LabeledContent("IL-LLM source", value: engine.ilLlmRuntimePath)
                    Button("Reload workspace data") {
                        engine.reloadILLLMBundle()
                    }
                }

                Section("Native window runtime") {
                    Text("Window and projection controls are administrative operations and are not exposed on the home dashboard.")
                        .foregroundStyle(.secondary)
                    Button("Open visual runtime") {
                        BRAINKWindowRegistry.shared.open(
                            logicalAddress: "window://braink/visual/admin",
                            title: "BRAINK Visual Runtime",
                            state: "ADMIN_OPENED"
                        )
                    }
                    Button("Read window state") {
                        _ = BRAINKWindowRegistry.shared.readback()
                    }
                }

                Section("Advanced") {
                    Text("Maintenance is performed automatically where possible. Manual controls remain here for administrators.")
                        .foregroundStyle(.secondary)
                    Button("Run compatibility check") {
                        Task { await engine.send(userInput: "illlm compatibility") }
                    }
                    Button("Run proof packet") {
                        Task { await engine.send(userInput: "proof packet") }
                    }
                }
            }
            .padding()
            .navigationTitle("Administration")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
        .frame(minWidth: 620, minHeight: 500)
    }
}

struct BrainkNativeChatbotView: View {
    @StateObject private var engine = BRAINKChatEngine()
    @StateObject private var nodeTemplates = BRAINKNodeTemplateStore()
    @State private var input = ""
    @State private var selection: WorkspaceSection = .home
    @State private var showDiagnostics = false
    @State private var showAdministration = false

    var body: some View {
        ScreenContainer {
            NavigationSplitView {
                List(WorkspaceSection.allCases, selection: $selection) { section in
                    Label(section.rawValue, systemImage: section.icon)
                        .tag(section)
                }
                .navigationTitle("BRAINK")
                .listStyle(.sidebar)
            } detail: {
                Group {
                    switch selection {
                    case .home:
                        HomeWorkspaceView(
                            engine: engine,
                            selection: $selection,
                            input: $input,
                            showDiagnostics: $showDiagnostics,
                            showAdministration: $showAdministration
                        )
                    case .ai:
                        AIWorkspaceView(engine: engine, input: $input)
                    case .documents:
                        DocumentsWorkspaceView(engine: engine, input: $input)
                    case .files:
                        FilesWorkspaceView(engine: engine)
                    case .legal:
                        LegalWorkspaceView(input: $input)
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            .safeAreaInset(edge: .bottom) {
                StatusBar(engine: engine)
            }
        }
        .sheet(isPresented: $showDiagnostics) {
            DiagnosticsPanel(engine: engine)
        }
        .sheet(isPresented: $showAdministration) {
            AdministrationPanel(engine: engine)
        }
        .task {
            nodeTemplates.reload()
        }
    }
}

@main
struct BRAINKNativeChatBotApp: App {
    var body: some Scene {
        WindowGroup {
            BrainkNativeChatbotView()
                .frame(minWidth: 1120, minHeight: 760)
                .preferredColorScheme(.dark)
        }
        .windowStyle(.titleBar)
    }
}
