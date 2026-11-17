import SwiftUI

/// Sheet for choosing, previewing, and confirming a new formation.
struct RearrangeView: View {
    let cupCount: Int
    let formations: [Formation]
    let rearrangementsLeft: Int
    let onConfirm: (Formation) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var selection: Formation?

    init(cupCount: Int, formations: [Formation], rearrangementsLeft: Int, onConfirm: @escaping (Formation) -> Void) {
        self.cupCount = cupCount
        self.formations = formations
        self.rearrangementsLeft = rearrangementsLeft
        self.onConfirm = onConfirm
        _selection = State(initialValue: formations.first)
    }

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 16) {
                sectionTitle("Preview")

                Group {
                    if let selection {
                        FormationView(formation: selection)
                            .animation(.spring(duration: 0.4), value: selection)
                    } else {
                        ContentUnavailableView("No formations", systemImage: "circle.dashed")
                    }
                }
                .padding(20)
                .frame(maxWidth: .infinity)
                .frame(height: 260)
                .card()

                sectionTitle("\(cupCount)-cup formations")

                ScrollView {
                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 140), spacing: 12)], spacing: 12) {
                        ForEach(formations) { formation in
                            FormationCard(formation: formation, isSelected: formation == selection) {
                                selection = formation
                            }
                        }
                    }
                    .padding(2)
                }
                .scrollBounceBehavior(.basedOnSize)

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
                    guard let selection else { return }
                    onConfirm(selection)
                    dismiss()
                } label: {
                    Text(selection.map { "Rearrange to \($0.name)" } ?? "Rearrange")
                        .font(.body.weight(.semibold))
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .buttonBorderShape(.roundedRectangle(radius: 14))
                .disabled(selection == nil)
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
            .sensoryFeedback(.selection, trigger: selection)
        }
        .presentationDragIndicator(.visible)
    }

    private func sectionTitle(_ text: String) -> some View {
        Text(text)
            .font(.subheadline.weight(.medium))
            .foregroundStyle(.secondary)
            .padding(.top, 8)
    }
}

#Preview {
    RearrangeView(cupCount: 6, formations: FormationLibrary.formations(for: 6), rearrangementsLeft: 1) { _ in }
}
