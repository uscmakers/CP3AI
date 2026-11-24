import SwiftUI

/// Sheet showing the rearranged formation and a button to confirm it.
struct RearrangeView: View {
    let formation: Formation
    let rearrangementsLeft: Int
    let onConfirm: (Formation) -> Void

    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                VStack(spacing: 12) {
                    FormationView(formation: formation)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)

                    VStack(spacing: 2) {
                        Text(formation.name)
                            .font(.headline)
                        Text(formation.detail)
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                }
                .padding(20)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .card()
                .padding(.top, 8)

                Label(
                    rearrangementsLeft == 1
                        ? "This uses your only rearrangement for the game."
                        : "\(rearrangementsLeft - 1) rearrangements will remain after this.",
                    systemImage: "info.circle"
                )
                .font(.footnote)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity)

                Button {
                    onConfirm(formation)
                    dismiss()
                } label: {
                    Text("Confirm")
                        .font(.body.weight(.semibold))
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .buttonBorderShape(.roundedRectangle(radius: 14))
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 8)
            .background(Color(.systemGroupedBackground))
            .navigationTitle("Rearrange")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
        .presentationDragIndicator(.visible)
    }
}

#Preview {
    RearrangeView(formation: FormationLibrary.triangle6, rearrangementsLeft: 1) { _ in }
}
