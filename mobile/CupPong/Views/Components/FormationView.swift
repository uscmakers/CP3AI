import SwiftUI

/// Draws a set of cups centered in the available space.
struct FormationView: View {
    let cups: [Cup]
    /// Width/height of the drawing area in cup diameters. A fixed span keeps cups
    /// the same size across formations instead of zooming in on small ones.
    var span: Double = 4.4
    var onTap: ((Cup) -> Void)?

    init(cups: [Cup], span: Double = 4.4, onTap: ((Cup) -> Void)? = nil) {
        self.cups = cups
        self.span = span
        self.onTap = onTap
    }

    init(formation: Formation, span: Double = 4.4) {
        self.init(cups: formation.makeCups(), span: span)
    }

    var body: some View {
        GeometryReader { geo in
            let unit = min(geo.size.width, geo.size.height) / span
            let center = boundsCenter

            ZStack {
                ForEach(cups) { cup in
                    CupView(isRemoved: cup.isRemoved, size: unit * 0.92)
                        .position(
                            x: geo.size.width / 2 + (cup.position.x - center.x) * unit,
                            y: geo.size.height / 2 - (cup.position.y - center.y) * unit
                        )
                        .onTapGesture { onTap?(cup) }
                        .allowsHitTesting(onTap != nil)
                        .accessibilityElement()
                        .accessibilityLabel(cup.isRemoved ? "Removed cup" : "Cup")
                        .accessibilityHint(onTap == nil ? "" : (cup.isRemoved ? "Restores the cup" : "Marks the cup as hit"))
                        .accessibilityAddTraits(onTap == nil ? [] : .isButton)
                }
            }
        }
    }

    /// Center of the bounding box of every cup, including removed ones,
    /// so the layout doesn't shift as cups are hit.
    private var boundsCenter: CupPosition {
        guard !cups.isEmpty else { return CupPosition(x: 0, y: 0) }
        let xs = cups.map(\.position.x)
        let ys = cups.map(\.position.y)
        return CupPosition(x: (xs.min()! + xs.max()!) / 2, y: (ys.min()! + ys.max()!) / 2)
    }
}

#Preview {
    FormationView(formation: FormationLibrary.triangle10)
        .padding()
}
