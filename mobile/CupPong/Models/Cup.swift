import Foundation

struct Cup: Identifiable, Hashable {
    let id: Int
    var position: CupPosition
    var isRemoved = false
}

extension Formation {
    /// Fresh cups placed at this formation's positions.
    func makeCups() -> [Cup] {
        positions.enumerated().map { Cup(id: $0.offset, position: $0.element) }
    }
}
