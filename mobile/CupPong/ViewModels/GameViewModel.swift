// xcode: set sdk=iOS

import Foundation
import Observation

/// Game state for the main screen.
///
/// Local mode (no table): the app keeps the cups itself and the player taps to
/// mark hits. Table mode: the table server owns the game; this shows the last
/// state it sent and forwards the player's actions to it as commands.
@MainActor
@Observable
final class GameViewModel {
    let table = TableConnection()
    var rules: RerackRules

    private var localCups: [Cup]
    private var localFormation: Formation
    private var localRearrangementsUsed = 0

    init(rules: RerackRules = .standard) {
        let formation = FormationLibrary.standard
        self.localFormation = formation
        self.localCups = formation.makeCups()
        self.rules = rules
    }

    // MARK: - Mode

    /// True when playing with the table, even while (re)connecting.
    var isTableMode: Bool { table.isActive }

    /// The server's state, in table mode once it has arrived.
    private var remote: TableSnapshot? { isTableMode ? table.snapshot : nil }

    /// Waiting for the first state from the table.
    var isWaitingForTable: Bool { isTableMode && table.snapshot == nil }

    /// The gantry is moving cups; actions are disabled until it stops.
    var isBusy: Bool { remote?.busy == true }

    /// Whether the player can act right now.
    var canAct: Bool {
        guard isTableMode else { return true }
        return table.status == .connected && remote != nil && !isBusy
    }

    // MARK: - State

    var cups: [Cup] {
        guard isTableMode else { return localCups }
        return remote.map(Self.cups(from:)) ?? []
    }

    var formation: Formation {
        guard isTableMode else { return localFormation }
        return remote.map { FormationLibrary.formation(id: $0.formation) } ?? localFormation
    }

    var startingCount: Int {
        guard let remote else { return FormationLibrary.standard.cupCount }
        return FormationLibrary.formation(id: remote.startFormation).cupCount
    }

    var remainingCount: Int { cups.filter { !$0.isRemoved }.count }
    var hasGaps: Bool { cups.contains { $0.isRemoved } }
    var isCleared: Bool { !cups.isEmpty && remainingCount == 0 }

    /// Formations the remaining cups can move into, excluding the one they already form.
    var availableFormations: [Formation] {
        if isTableMode {
            // The server decides which formation is offered.
            guard let option = remote?.rearrangeOption else { return [] }
            return [FormationLibrary.formation(id: option)]
        }
        return FormationLibrary.formations(for: remainingCount).filter { hasGaps || $0 != localFormation }
    }

    var rearrangementsLeft: Int {
        if isTableMode { return remote?.rearrangementsLeft ?? 0 }
        return max(0, rules.maxRearrangements - localRearrangementsUsed)
    }

    var canRearrange: Bool { canAct && rearrangementsLeft > 0 && !availableFormations.isEmpty }

    var shouldSuggestRerack: Bool {
        if isTableMode { return remote?.rearrangeOption != nil }
        return rearrangementsLeft > 0 && rules.shouldSuggestRerack(
            remainingCups: remainingCount,
            hasGaps: hasGaps,
            hasFormations: !availableFormations.isEmpty
        )
    }

    var formationLabel: String {
        hasGaps ? "Partial \(formation.name.lowercased())" : formation.displayName
    }

    // MARK: - Actions

    /// Local mode: marks a cup as hit, or restores it if it was already removed (to undo a mis-tap).
    /// Table mode: asks the table to park the cup. Parked cups can't be put back from the app.
    func toggle(_ cup: Cup) {
        if isTableMode {
            guard canAct, !cup.isRemoved else { return }
            table.send(.cupHit(cupID: cup.id))
            return
        }
        guard let index = localCups.firstIndex(where: { $0.id == cup.id }) else { return }
        localCups[index].isRemoved.toggle()
    }

    /// Moves the remaining cups into `newFormation`. Cups keep their identity
    /// so the view can animate each one sliding to its new spot.
    func apply(_ newFormation: Formation) {
        if isTableMode {
            guard canAct else { return }
            table.send(.rearrange(formationID: newFormation.id))
            return
        }

        guard rearrangementsLeft > 0 else { return }
        let active = localCups.filter { !$0.isRemoved }.sorted(by: Self.rowOrder)
        guard active.count == newFormation.cupCount else { return }

        let targets = newFormation.positions.sorted(by: Self.rowOrder)
        localCups = zip(active, targets).map { Cup(id: $0.id, position: $1) }
        localFormation = newFormation
        localRearrangementsUsed += 1
    }

    /// Local mode: re-racks the cups. Table mode: tells the table the cups were re-racked.
    func reset() {
        if isTableMode {
            guard canAct else { return }
            table.send(.reset)
            return
        }
        localFormation = FormationLibrary.standard
        localCups = localFormation.makeCups()
        localRearrangementsUsed = 0
    }

    // MARK: - Table state → cups

    /// Converts the server's millimeter positions into the cup-diameter units the views use.
    /// With `spots`, hit cups keep their place as outlines; without it only active cups show.
    static func cups(from snapshot: TableSnapshot) -> [Cup] {
        let diameter = snapshot.cupDiameterMm > 0 ? snapshot.cupDiameterMm : 92
        func position(_ x: Double, _ y: Double) -> CupPosition {
            CupPosition(x: x / diameter, y: y / diameter)
        }

        let active = snapshot.cups.filter(\.isActive)
        let activeIDs = Set(active.map(\.id))

        guard let spots = snapshot.spots, !spots.isEmpty else {
            return active.map { Cup(id: $0.id, position: position($0.xMm, $0.yMm)) }
        }

        var cups = spots.map { spot in
            Cup(
                // Spots with no cup get negative IDs so they never clash with real cups.
                id: spot.cupId ?? -(spot.index + 1),
                position: position(spot.xMm, spot.yMm),
                isRemoved: !(spot.cupId.map(activeIDs.contains) ?? false)
            )
        }

        // An active cup that isn't sitting in its spot (for example one moved
        // aside mid-plan) is drawn where it actually is.
        for cup in active {
            let here = position(cup.xMm, cup.yMm)
            let inSpot = cups.contains {
                $0.id == cup.id && abs($0.position.x - here.x) < 0.05 && abs($0.position.y - here.y) < 0.05
            }
            if !inSpot {
                cups.removeAll { $0.id == cup.id }
                cups.append(Cup(id: cup.id, position: here))
            }
        }
        return cups
    }

    // Pair cups with targets row by row so movements stay short.
    private static func rowOrder(_ a: Cup, _ b: Cup) -> Bool { rowOrder(a.position, b.position) }

    private static func rowOrder(_ a: CupPosition, _ b: CupPosition) -> Bool {
        abs(a.y - b.y) > 0.01 ? a.y < b.y : a.x < b.x
    }
}
