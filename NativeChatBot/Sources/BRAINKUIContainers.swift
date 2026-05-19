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
