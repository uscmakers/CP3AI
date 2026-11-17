// xcode: set sdk=iOS

import Foundation
import Observation

/// Local game state: the cups on the table, the formation they were racked in,
/// and the rerack rules in effect.
@Observable
final class GameViewModel {
    private(set) var cups: [Cup]
    private(set) var formation: Formation
    private(set) var rearrangementsUsed = 0
    var rules: RerackRules

    let startingCount = FormationLibrary.standard.cupCount

    init(rules: RerackRules = .standard) {
        let formation = FormationLibrary.standard
        self.formation = formation
        self.cups = formation.makeCups()
        self.rules = rules
    }

    var remainingCount: Int { cups.filter { !$0.isRemoved }.count }
    var hasGaps: Bool { cups.contains { $0.isRemoved } }
    var isCleared: Bool { remainingCount == 0 }

    /// Formations the remaining cups can move into, excluding the one they already form.
    var availableFormations: [Formation] {
        FormationLibrary.formations(for: remainingCount).filter { hasGaps || $0 != formation }
    }

    var rearrangementsLeft: Int { max(0, rules.maxRearrangements - rearrangementsUsed) }

    var canRearrange: Bool { rearrangementsLeft > 0 && !availableFormations.isEmpty }

    var shouldSuggestRerack: Bool {
        rearrangementsLeft > 0 && rules.shouldSuggestRerack(
            remainingCups: remainingCount,
            hasGaps: hasGaps,
            hasFormations: !availableFormations.isEmpty
        )
    }

    var formationLabel: String {
        hasGaps ? "Partial \(formation.name.lowercased())" : formation.displayName
    }

    /// Marks a cup as hit, or restores it if it was already removed (to undo a mis-tap).
    func toggle(_ cup: Cup) {
        guard let index = cups.firstIndex(where: { $0.id == cup.id }) else { return }
        cups[index].isRemoved.toggle()
    }

    /// Moves the remaining cups into `newFormation`. Cups keep their identity
    /// so the view can animate each one sliding to its new spot.
    func apply(_ newFormation: Formation) {
        guard rearrangementsLeft > 0 else { return }
        let active = cups.filter { !$0.isRemoved }.sorted(by: Self.rowOrder)
        guard active.count == newFormation.cupCount else { return }

        let targets = newFormation.positions.sorted(by: Self.rowOrder)
        cups = zip(active, targets).map { Cup(id: $0.id, position: $1) }
        formation = newFormation
        rearrangementsUsed += 1
    }

    func reset() {
        formation = FormationLibrary.standard
        cups = formation.makeCups()
        rearrangementsUsed = 0
    }

    // Pair cups with targets row by row so movements stay short.
    private static func rowOrder(_ a: Cup, _ b: Cup) -> Bool { rowOrder(a.position, b.position) }

    private static func rowOrder(_ a: CupPosition, _ b: CupPosition) -> Bool {
        abs(a.y - b.y) > 0.01 ? a.y < b.y : a.x < b.x
    }
}
