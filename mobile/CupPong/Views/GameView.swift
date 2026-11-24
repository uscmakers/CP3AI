import SwiftUI

/// Main screen: the current rack, remaining count, rerack suggestion, and actions.
struct GameView: View {
    @State private var game = GameViewModel()
    @State private var isRearranging = false
    @State private var isConnecting = false
    @State private var cupToConfirm: Cup?
    @State private var isConfirmingReset = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                header

                FormationView(cups: game.cups) { cup in
                    if game.isTableMode {
                        // Hits normally come from the camera; a tap here moves the gantry, so confirm it.
                        if game.canAct, !cup.isRemoved { cupToConfirm = cup }
                    } else {
                        withAnimation(.easeOut(duration: 0.2)) { game.toggle(cup) }
                    }
                }
                .padding(20)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .card()
                .overlay { tableOverlay }

                if game.shouldSuggestRerack {
                    RerackBanner(remainingCups: game.remainingCount, formations: game.availableFormations) {
                        isRearranging = true
                    }
                    .disabled(!game.canRearrange)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                }

                rearrangeButton
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 8)
            .animation(.easeInOut(duration: 0.25), value: game.shouldSuggestRerack)
            .animation(.spring(duration: 0.6, bounce: 0.15), value: game.cups)
            .background(Color(.systemGroupedBackground))
            .navigationTitle("Cup Pong")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItemGroup(placement: .topBarLeading) {
                    Button {
                        if game.isTableMode {
                            isConfirmingReset = true
                        } else {
                            withAnimation(.spring(duration: 0.4)) { game.reset() }
                        }
                    } label: {
                        Label("Reset", systemImage: "arrow.counterclockwise")
                    }
                    .disabled(!game.canAct)
                }
                ToolbarItemGroup(placement: .topBarTrailing) {
                    Button {
                        isConnecting = true
                    } label: {
                        Label("Table", systemImage: game.isTableMode ? "dot.radiowaves.left.and.right" : "antenna.radiowaves.left.and.right.slash")
                    }
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
            .sheet(isPresented: $isConnecting) {
                TableConnectView(table: game.table)
            }
            .confirmationDialog(
                "Mark this cup as hit?",
                isPresented: Binding(get: { cupToConfirm != nil }, set: { if !$0 { cupToConfirm = nil } }),
                titleVisibility: .visible,
                presenting: cupToConfirm
            ) { cup in
                Button("Park Cup") { game.toggle(cup) }
            } message: { _ in
                Text("Use this if the camera missed a hit. The gantry moves the cup off the table.")
            }
            .confirmationDialog(
                "Start a new rack?",
                isPresented: $isConfirmingReset,
                titleVisibility: .visible
            ) {
                Button("New Rack") { game.reset() }
            } message: {
                Text("Put every cup back in the starting formation first. The table will treat them as racked.")
            }
            .alert(
                "Table",
                isPresented: Binding(get: { game.table.serverError != nil }, set: { if !$0 { game.table.serverError = nil } })
            ) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(game.table.serverError ?? "")
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

            VStack(alignment: .trailing, spacing: 6) {
                if game.isTableMode {
                    Button {
                        isConnecting = true
                    } label: {
                        TableStatusLabel(status: game.table.status)
                            .font(.caption.weight(.medium))
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }
                    .buttonStyle(.plain)
                }

                Text(game.formationLabel)
                    .font(.footnote.weight(.medium))
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(Capsule().fill(Color.primary.opacity(0.05)))
            }
        }
        .padding(.top, 8)
        .accessibilityElement(children: .combine)
    }

    @ViewBuilder
    private var tableOverlay: some View {
        if game.isWaitingForTable {
            VStack(spacing: 10) {
                ProgressView()
                Text("Connecting to the table…")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            .transition(.opacity)
        } else if game.isBusy {
            VStack {
                Spacer()
                Label("Moving cups…", systemImage: "gearshape.2")
                    .font(.footnote.weight(.medium))
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(Capsule().fill(.regularMaterial))
                    .padding(.bottom, 12)
            }
            .transition(.opacity)
        } else if game.isCleared {
            clearedOverlay
        }
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
        if game.isCleared || game.isWaitingForTable { return nil }
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
