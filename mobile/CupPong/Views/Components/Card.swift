import SwiftUI

/// Rounded white surface with a hairline border, used for the table and option cards.
struct CardBackground: ViewModifier {
    var cornerRadius: CGFloat = 24
    var borderColor: Color = .primary.opacity(0.07)
    var borderWidth: CGFloat = 1

    func body(content: Content) -> some View {
        let shape = RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
        content
            .background(shape.fill(Color(.systemBackground)))
            .overlay(shape.strokeBorder(borderColor, lineWidth: borderWidth))
            .shadow(color: .black.opacity(0.04), radius: 10, y: 4)
    }
}

extension View {
    func card(cornerRadius: CGFloat = 24, borderColor: Color = .primary.opacity(0.07), borderWidth: CGFloat = 1) -> some View {
        modifier(CardBackground(cornerRadius: cornerRadius, borderColor: borderColor, borderWidth: borderWidth))
    }
}
