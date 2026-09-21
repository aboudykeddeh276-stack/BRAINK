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


struct TemplateBackedPanel<Content: View>: View {
    let node: BRAINKNodeInstanceIdentity
    let content: () -> Content
    var panelColor: Color = Color(NSColor.windowBackgroundColor).opacity(0.85)

    init(
        node: BRAINKNodeInstanceIdentity,
        panelColor: Color = Color(NSColor.windowBackgroundColor).opacity(0.85),
        @ViewBuilder content: @escaping () -> Content
    ) {
        self.node = node
        self.panelColor = panelColor
        self.content = content
    }

    var body: some View {
        BRAINKTemplateBackedView(node: node) {
            content()
                .background(panelColor)
        }
    }
}


struct GovernedTemplatePanel<Content: View>: View {
    let node: BRAINKNodeInstanceIdentity?
    let unboundReason: String
    let content: () -> Content

    init(
        node: BRAINKNodeInstanceIdentity?,
        unboundReason: String = "",
        @ViewBuilder content: @escaping () -> Content
    ) {
        self.node = node
        self.unboundReason = unboundReason
        self.content = content
    }

    @ViewBuilder
    var body: some View {
        if let node {
            TemplateBackedPanel(node: node) {
                content()
            }
        } else {
            VStack(spacing: 0) {
                HStack {
                    Text("NODE TEMPLATE UNBOUND")
                        .font(.caption.bold().monospaced())
                        .foregroundStyle(.orange)
                    Spacer()
                    Text(unboundReason.isEmpty ? "bootstrap required" : unboundReason)
                        .font(.caption2.monospaced())
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                ThemedPanel {
                    content()
                }
            }
        }
    }
}
