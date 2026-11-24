import Foundation

/// A cup position measured in cup rim diameters.
/// Positive y points toward the top of the screen, matching `software/layouts.py`.
struct CupPosition: Hashable {
    var x: Double
    var y: Double
}

/// A named arrangement of cups. Coordinates are relative; views center them automatically.
struct Formation: Identifiable, Hashable {
    /// Matches the layout keys in `software/layouts.py` so the gantry planner can share them.
    let id: String
    let name: String
    let detail: String
    let positions: [CupPosition]

    var cupCount: Int { positions.count }
    var displayName: String { "\(name) (\(detail))" }
}

/// Central catalog of every formation the app knows about.
/// To add a layout, define it here and include it in `all`.
enum FormationLibrary {
    /// Row spacing for tightly packed cups (√3 / 2 diameters).
    private static let h = 3.0.squareRoot() / 2

    static let triangle10 = Formation(
        id: "triangle_10",
        name: "Triangle",
        detail: "4-3-2-1",
        positions: [
            .init(x: -1.5, y: 0), .init(x: -0.5, y: 0), .init(x: 0.5, y: 0), .init(x: 1.5, y: 0),
            .init(x: -1, y: h), .init(x: 0, y: h), .init(x: 1, y: h),
            .init(x: -0.5, y: 2 * h), .init(x: 0.5, y: 2 * h),
            .init(x: 0, y: 3 * h),
        ]
    )

    static let triangle6 = Formation(
        id: "triangle_6",
        name: "Triangle",
        detail: "3-2-1",
        positions: [
            .init(x: -1, y: 0), .init(x: 0, y: 0), .init(x: 1, y: 0),
            .init(x: -0.5, y: h), .init(x: 0.5, y: h),
            .init(x: 0, y: 2 * h),
        ]
    )

    static let backpack5 = Formation(
        id: "backpack_kid_5",
        name: "Backpack",
        detail: "3 + 2",
        positions: [
            .init(x: 0, y: 0), .init(x: 0, y: 1), .init(x: 0, y: 2),
            .init(x: h, y: 0.5), .init(x: h, y: 1.5),
        ]
    )

    static let triangle3 = Formation(
        id: "triangle_3",
        name: "Triangle",
        detail: "2-1",
        positions: [
            .init(x: -0.5, y: 0), .init(x: 0.5, y: 0),
            .init(x: 0, y: h),
        ]
    )

    static let vertical2 = Formation(
        id: "vertical_2",
        name: "Vertical",
        detail: "1-1",
        positions: [.init(x: 0, y: 0), .init(x: 0, y: 1)]
    )

    static let standard = triangle10

    /// Mirrors `rack_layouts` in `software/layouts.py`; keep the two in sync.
    static let all: [Formation] = [triangle10, triangle6, backpack5, triangle3, vertical2]

    static func formations(for cupCount: Int) -> [Formation] {
        all.filter { $0.cupCount == cupCount }
    }

    /// The formation with this ID. An ID the app doesn't know yet (added to
    /// `software/layouts.py` only) gets a placeholder named after the ID.
    static func formation(id: String) -> Formation {
        all.first { $0.id == id }
            ?? Formation(id: id, name: id.replacingOccurrences(of: "_", with: " ").capitalized, detail: "", positions: [])
    }
}
