import SwiftUI

/// Selectable card showing a small preview of a formation.
struct FormationCard: View {
    let formation: Formation
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 10) {
                FormationView(formation: formation)
                    .frame(height: 84)

                VStack(spacing: 2) {
                    Text(formation.name)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.primary)
                    Text(formation.detail)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .padding(14)
            .frame(maxWidth: .infinity)
            .card(
                cornerRadius: 18,
                borderColor: isSelected ? .accentColor : .primary.opacity(0.07),
                borderWidth: isSelected ? 2 : 1
            )
            .overlay(alignment: .topTrailing) {
                if isSelected {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.body)
                        .foregroundStyle(Color.accentColor)
                        .padding(10)
                }
            }
        }
        .buttonStyle(.plain)
        .accessibilityLabel(formation.displayName)
        .accessibilityAddTraits(isSelected ? .isSelected : [])
    }
}

#Preview {
    HStack {
        FormationCard(formation: FormationLibrary.triangle6, isSelected: true) {}
        FormationCard(formation: FormationLibrary.backpack5, isSelected: false) {}
    }
    .padding()
    .background(Color(.systemGroupedBackground))
}
