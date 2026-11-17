import SwiftUI

/// Subtle, tappable suggestion that a rerack is available.
struct RerackBanner: View {
    let remainingCups: Int
    let formations: [Formation]
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Image(systemName: "sparkles")
                    .font(.body.weight(.medium))
                    .foregroundStyle(Color.accentColor)
                    .frame(width: 32, height: 32)
                    .background(Circle().fill(Color.accentColor.opacity(0.12)))

                VStack(alignment: .leading, spacing: 2) {
                    Text("Rerack available")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.primary)
                    Text(message)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Spacer(minLength: 0)

                Image(systemName: "chevron.right")
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(.tertiary)
            }
            .padding(14)
            .card(cornerRadius: 16)
        }
        .buttonStyle(.plain)
    }

    private var message: String {
        let names = formations.map(\.displayName).formatted(.list(type: .or))
        return "\(remainingCups) \(remainingCups == 1 ? "cup fits" : "cups fit") a \(names)."
    }
}

#Preview {
    RerackBanner(remainingCups: 6, formations: [FormationLibrary.triangle6]) {}
        .padding()
        .background(Color(.systemGroupedBackground))
}
