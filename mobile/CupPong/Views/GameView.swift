import SwiftUI

/// Main screen: the current rack, remaining count, rerack suggestion, and actions.
struct GameView: View {
    @State private var game = GameViewModel()
    @State private var isRearranging = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                header

                FormationView(cups: game.cups) { cup in
                    withAnimation(.easeOut(duration: 0.2)) { game.toggle(cup) }
                }
                .padding(20)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .card()
                .overlay { if game.isCleared { clearedOverlay } }

                if game.shouldSuggestRerack {
                    RerackBanner(remainingCups: game.remainingCount, formations: game.availableFormations) {
                        isRearranging = true
                    }
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                }

                rearrangeButton
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 8)
            .animation(.easeInOut(duration: 0.25), value: game.shouldSuggestRerack)
            .background(Color(.systemGroupedBackground))
            .navigationTitle("Cup Pong")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        withAnimation(.spring(duration: 0.4)) { game.reset() }
                    } label: {
                        Label("Reset", systemImage: "arrow.counterclockwise")
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    ProfileButton()
                }
            }
            .sheet(isPresented: $isRearranging) {
                if let formation = game.availableFormations.first {
                    RearrangeView(
                        formation: formation,
                        rearrangementsLeft: game.rearrangementsLeft
                    ) { formation in
                        withAnimation(.spring(duration: 0.6, bounce: 0.15)) { game.apply(formation) }
                    }
                }
            }
            .sensoryFeedback(.selection, trigger: game.remainingCount)
        }
    }

    private var header: some View {
        HStack(alignment: .lastTextBaseline) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Remaining")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                HStack(alignment: .firstTextBaseline, spacing: 4) {
                    Text("\(game.remainingCount)")
                        .font(.system(size: 48, weight: .semibold, design: .rounded))
                        .contentTransition(.numericText())
                        .animation(.snappy, value: game.remainingCount)
                    Text("of \(game.startingCount)")
                        .font(.title3)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()

            Text(game.formationLabel)
                .font(.footnote.weight(.medium))
                .foregroundStyle(.secondary)
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(Capsule().fill(Color.primary.opacity(0.05)))
        }
        .padding(.top, 8)
        .accessibilityElement(children: .combine)
    }

    private var rearrangeButton: some View {
        VStack(spacing: 6) {
            Button {
                isRearranging = true
            } label: {
                Label("Rearrange", systemImage: "arrow.triangle.2.circlepath")
                    .font(.body.weight(.semibold))
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .buttonBorderShape(.roundedRectangle(radius: 14))
            .disabled(!game.canRearrange)

            if let caption = rearrangeCaption {
                Text(caption)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private var rearrangeCaption: String? {
        if game.isCleared { return nil }
        if game.rearrangementsLeft == 0 { return "Rearrangement used this game" }
        if game.availableFormations.isEmpty && game.hasGaps { return "No formations for \(game.remainingCount) cups" }
        return game.rearrangementsLeft == 1
            ? "1 rearrangement per game"
            : "\(game.rearrangementsLeft) rearrangements left"
    }

    private var clearedOverlay: some View {
        VStack(spacing: 8) {
            Image(systemName: "checkmark.circle")
                .font(.largeTitle)
                .foregroundStyle(Color.accentColor)
            Text("All cups cleared")
                .font(.headline)
            Text("Tap reset to start a new rack.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .transition(.opacity)
    }
}

#Preview {
    GameView()
        .environment(AuthViewModel())
}
