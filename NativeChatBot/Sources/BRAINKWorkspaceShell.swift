import SwiftUI
import AppKit

enum BRAINKWorkspaceRoute: String, CaseIterable, Identifiable {
    case home = "Home"
    case ai = "AI"
    case tasks = "Tasks"
    case files = "Files"
    case activity = "Activity"
    case admin = "Admin"
    case diagnostics = "Diagnostics"

    var id: String { rawValue }

    var systemImage: String {
        switch self {
        case .home: return "house"
        case .ai: return "bubble.left.and.bubble.right"
        case .tasks: return "checklist"
        case .files: return "folder"
        case .activity: return "clock.arrow.circlepath"
        case .admin: return "gearshape"
        case .diagnostics: return "stethoscope"
        }
    }

    var isPrimary: Bool {
        self == .home || self == .ai || self == .tasks || self == .files
    }
}

struct BRAINKTaskItem: Identifiable, Codable, Hashable {
    let id: UUID
    var title: String
    var completed: Bool
    let createdAt: Date

    init(id: UUID = UUID(), title: String, completed: Bool = false, createdAt: Date = Date()) {
        self.id = id
        self.title = title
        self.completed = completed
        self.createdAt = createdAt
    }
}

@MainActor
final class BRAINKTaskStore: ObservableObject {
    @Published private(set) var items: [BRAINKTaskItem] = []

    private var stateURL: URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".braink", isDirectory: true)
            .appendingPathComponent("ui", isDirectory: true)
            .appendingPathComponent("tasks.json")
    }

    init() {
        load()
    }

    func add(_ title: String) {
        let trimmed = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        items.insert(BRAINKTaskItem(title: trimmed), at: 0)
        persist()
    }

    func toggle(_ id: UUID) {
        guard let index = items.firstIndex(where: { $0.id == id }) else { return }
        items[index].completed.toggle()
        persist()
    }

    func remove(_ id: UUID) {
        items.removeAll { $0.id == id }
        persist()
    }

    private func load() {
        guard let data = try? Data(contentsOf: stateURL),
              let decoded = try? JSONDecoder().decode([BRAINKTaskItem].self, from: data) else {
            items = []
            return
        }
        items = decoded
    }

    private func persist() {
        do {
            try FileManager.default.createDirectory(
                at: stateURL.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            let data = try JSONEncoder().encode(items)
            try data.write(to: stateURL, options: .atomic)
        } catch {
            // Task persistence failure remains non-blocking for the user workflow.
        }
    }
}

@MainActor
final class BRAINKFileWorkspaceStore: ObservableObject {
    @Published var directoryURL: URL?
    @Published private(set) var entries: [URL] = []

    func browse() {
        let panel = NSOpenPanel()
        panel.title = "Choose a workspace folder"
        panel.prompt = "Open"
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        if panel.runModal() == .OK, let url = panel.url {
            open(url)
        }
    }

    func open(_ url: URL) {
        directoryURL = url
        do {
            entries = try FileManager.default.contentsOfDirectory(
                at: url,
                includingPropertiesForKeys: [.isDirectoryKey, .fileSizeKey, .contentModificationDateKey],
                options: [.skipsHiddenFiles]
            ).sorted { $0.lastPathComponent.localizedCaseInsensitiveCompare($1.lastPathComponent) == .orderedAscending }
        } catch {
            entries = []
        }
    }
}

struct BRAINKPrimaryActionCard: View {
    let title: String
    let subtitle: String
    let systemImage: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 12) {
                Image(systemName: systemImage)
                    .font(.title2)
                Text(title)
                    .font(.headline)
                Text(subtitle)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.leading)
                Spacer(minLength: 0)
            }
            .frame(maxWidth: .infinity, minHeight: 110, alignment: .leading)
            .padding(16)
        }
        .buttonStyle(.plain)
        .background(Color.primary.opacity(0.05))
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color.primary.opacity(0.08), lineWidth: 1)
        )
    }
}

struct BRAINKStatusBar: View {
    let taskCount: Int

    var body: some View {
        HStack(spacing: 12) {
            Label("Ready", systemImage: "checkmark.circle")
                .foregroundStyle(.secondary)
            if taskCount > 0 {
                Text("\(taskCount) active task\(taskCount == 1 ? "" : "s")")
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Text("Details in Diagnostics")
                .foregroundStyle(.tertiary)
        }
        .font(.caption)
        .padding(.horizontal, 14)
        .padding(.vertical, 7)
        .background(Color.primary.opacity(0.035))
    }
}

struct BRAINKHomeView: View {
    @Binding var selection: BRAINKWorkspaceRoute
    @ObservedObject var tasks: BRAINKTaskStore
    @ObservedObject var files: BRAINKFileWorkspaceStore

    private var activeTasks: [BRAINKTaskItem] {
        tasks.items.filter { !$0.completed }
    }

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("What do you want to do?")
                            .font(.largeTitle.bold())
                        Text("BRAINK resolves models, VFS, agents and runtime state behind the task.")
                            .foregroundStyle(.secondary)
                    }

                    HStack(alignment: .top, spacing: 14) {
                        BRAINKPrimaryActionCard(
                            title: "Ask BRAINK",
                            subtitle: "Research, plan, analyse, code or continue an existing line of work.",
                            systemImage: "bubble.left.and.bubble.right"
                        ) { selection = .ai }

                        BRAINKPrimaryActionCard(
                            title: "Tasks",
                            subtitle: "Create, resume and complete work without exposing scheduler plumbing.",
                            systemImage: "checklist"
                        ) { selection = .tasks }

                        BRAINKPrimaryActionCard(
                            title: "Files",
                            subtitle: "Browse the working filesystem and open the workspace you actually care about.",
                            systemImage: "folder"
                        ) { selection = .files }
                    }

                    VStack(alignment: .leading, spacing: 12) {
                        Text("Continue working")
                            .font(.headline)

                        if let task = activeTasks.first {
                            Button {
                                selection = .tasks
                            } label: {
                                HStack {
                                    Image(systemName: "play.circle")
                                    Text(task.title)
                                    Spacer()
                                    Text("Resume")
                                        .foregroundStyle(.secondary)
                                }
                                .padding(12)
                            }
                            .buttonStyle(.plain)
                            .background(Color.primary.opacity(0.04))
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                        } else {
                            Text("No active tasks. Start from AI, Tasks or Files.")
                                .foregroundStyle(.secondary)
                        }

                        if let url = files.directoryURL {
                            Button {
                                selection = .files
                            } label: {
                                HStack {
                                    Image(systemName: "folder")
                                    Text(url.path)
                                        .lineLimit(1)
                                        .truncationMode(.middle)
                                    Spacer()
                                    Text("Open")
                                        .foregroundStyle(.secondary)
                                }
                                .padding(12)
                            }
                            .buttonStyle(.plain)
                            .background(Color.primary.opacity(0.04))
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                        }
                    }
                }
                .padding(28)
            }

            BRAINKStatusBar(taskCount: activeTasks.count)
        }
    }
}

struct BRAINKTasksView: View {
    @ObservedObject var store: BRAINKTaskStore
    @State private var title = ""

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                TextField("Add a task…", text: $title)
                    .textFieldStyle(.roundedBorder)
                    .onSubmit(addTask)
                Button("Add", action: addTask)
                    .buttonStyle(.borderedProminent)
                    .disabled(title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
            .padding()

            Divider()

            List {
                ForEach(store.items) { item in
                    HStack(spacing: 10) {
                        Button {
                            store.toggle(item.id)
                        } label: {
                            Image(systemName: item.completed ? "checkmark.circle.fill" : "circle")
                        }
                        .buttonStyle(.plain)
                        .accessibilityLabel(item.completed ? "Mark incomplete" : "Mark complete")

                        Text(item.title)
                            .strikethrough(item.completed)
                            .foregroundStyle(item.completed ? .secondary : .primary)

                        Spacer()

                        Button {
                            store.remove(item.id)
                        } label: {
                            Image(systemName: "trash")
                        }
                        .buttonStyle(.plain)
                        .accessibilityLabel("Delete task")
                    }
                    .padding(.vertical, 4)
                }
            }
        }
        .navigationTitle("Tasks")
    }

    private func addTask() {
        store.add(title)
        title = ""
    }
}

struct BRAINKFilesView: View {
    @ObservedObject var store: BRAINKFileWorkspaceStore

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(store.directoryURL?.path ?? "No workspace folder selected")
                    .lineLimit(1)
                    .truncationMode(.middle)
                    .foregroundStyle(.secondary)
                Spacer()
                Button("Browse Files") {
                    store.browse()
                }
                .buttonStyle(.borderedProminent)
            }
            .padding()

            Divider()

            if store.entries.isEmpty {
                ContentUnavailableView(
                    "No files loaded",
                    systemImage: "folder",
                    description: Text("Choose a workspace folder to browse its contents.")
                )
            } else {
                List(store.entries, id: \.path) { url in
                    HStack {
                        Image(systemName: "doc")
                        Text(url.lastPathComponent)
                        Spacer()
                        Text(url.pathExtension)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
        .navigationTitle("Files")
    }
}

struct BRAINKActivityView: View {
    @ObservedObject var tasks: BRAINKTaskStore

    var body: some View {
        List {
            Section("Task activity") {
                ForEach(tasks.items) { item in
                    HStack {
                        Image(systemName: item.completed ? "checkmark.circle" : "clock")
                        Text(item.title)
                        Spacer()
                        Text(item.completed ? "Completed" : "Active")
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
        .navigationTitle("Activity")
    }
}

struct BRAINKAdminView: View {
    var body: some View {
        Form {
            Section("Administration") {
                LabeledContent("Agents", value: "Managed by BRAINK authority")
                LabeledContent("Integrations", value: "Managed through governed capability bindings")
                LabeledContent("Permissions", value: "Authority-scoped")
                LabeledContent("Configuration", value: "Persistent")
            }
            Text("Administrative configuration stays separate from everyday work.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding()
        .navigationTitle("Admin")
    }
}

struct BRAINKDiagnosticsWorkspaceView: View {
    var body: some View {
        Form {
            Section("Runtime diagnostics") {
                LabeledContent("MCP", value: "System superface")
                LabeledContent("BRAINK authority", value: "braink://local/orchestrator")
                LabeledContent("IL-LLM", value: "Resident dependency / traversal")
                LabeledContent("VFS", value: "vfs://kex/root")
                LabeledContent("Model residency", value: "Readiness-gated")
                LabeledContent("Node state", value: "Observed before READY")
            }
            Text("Low-level model, VFS, node, endpoint and ledger details belong here rather than on Home.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding()
        .navigationTitle("Diagnostics")
    }
}

struct BRAINKWorkspaceShell: View {
    @State private var selection: BRAINKWorkspaceRoute = .home
    @StateObject private var tasks = BRAINKTaskStore()
    @StateObject private var files = BRAINKFileWorkspaceStore()

    var body: some View {
        NavigationSplitView {
            List(selection: $selection) {
                Section("Work") {
                    ForEach(BRAINKWorkspaceRoute.allCases.filter(\.isPrimary)) { route in
                        Label(route.rawValue, systemImage: route.systemImage)
                            .tag(route)
                    }
                }

                Section("System") {
                    ForEach([BRAINKWorkspaceRoute.activity, .admin, .diagnostics]) { route in
                        Label(route.rawValue, systemImage: route.systemImage)
                            .tag(route)
                    }
                }
            }
            .navigationTitle("BRAINK")
            .frame(minWidth: 180)
        } detail: {
            switch selection {
            case .home:
                BRAINKHomeView(selection: $selection, tasks: tasks, files: files)
            case .ai:
                BrainkNativeChatbotView()
            case .tasks:
                BRAINKTasksView(store: tasks)
            case .files:
                BRAINKFilesView(store: files)
            case .activity:
                BRAINKActivityView(tasks: tasks)
            case .admin:
                BRAINKAdminView()
            case .diagnostics:
                BRAINKDiagnosticsWorkspaceView()
            }
        }
    }
}
