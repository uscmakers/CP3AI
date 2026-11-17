import Foundation

/// House rules for when the app suggests a rerack. Suggestions are advisory only;
/// the player always decides whether to rearrange.
struct RerackRules {
    /// Remaining-cup counts at which a rerack is suggested.
    /// Matches `REARRANGE_FORMATIONS` in `software/motion_viewer.py`.
    var suggestedCounts: Set<Int> = [6, 5, 3, 2]

    /// Rearrangements allowed per game. Matches `MAX_REARRANGEMENTS` in `software/motion_viewer.py`.
    var maxRearrangements = 1

    static let standard = RerackRules()

    /// Suggest a rerack only when the formation has gaps and a clean layout exists for the count.
    func shouldSuggestRerack(remainingCups: Int, hasGaps: Bool, hasFormations: Bool) -> Bool {
        hasGaps && hasFormations && suggestedCounts.contains(remainingCups)
    }
}
