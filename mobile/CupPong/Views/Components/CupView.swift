import SwiftUI

/// A single cup seen from above. Removed cups show as a dashed outline.
struct CupView: View {
    let isRemoved: Bool
    let size: CGFloat

    var body: some View {
        ZStack {
            if isRemoved {
                Circle()
                    .strokeBorder(
                        Color.secondary.opacity(0.35),
                        style: StrokeStyle(lineWidth: max(1, size * 0.025), dash: [size * 0.07, size * 0.05])
                    )
                    .transition(.opacity)
            } else {
                Circle()
                    .fill(Color.cupRed)
                    .overlay(Circle().strokeBorder(.white.opacity(0.85), lineWidth: max(1.5, size * 0.06)))
                    .overlay(Circle().fill(.black.opacity(0.08)).padding(size * 0.2))
                    .shadow(color: .black.opacity(0.12), radius: size * 0.04, y: size * 0.02)
                    .transition(.scale(scale: 0.85).combined(with: .opacity))
            }
        }
        .frame(width: size, height: size)
        .contentShape(Circle())
    }
}

extension Color {
    static let cupRed = Color(red: 0.86, green: 0.25, blue: 0.26)
}

#Preview {
    HStack(spacing: 16) {
        CupView(isRemoved: false, size: 72)
        CupView(isRemoved: true, size: 72)
    }
    .padding()
}
