from dataclasses import dataclass
import math
from config import cup

@dataclass(frozen=True)
class ArrangementPosition:
    dx: float
    dy: float

D = cup.rim_diameter
H = math.sqrt(3) / 2 * D

# Coordinates relative to the formation's center.
# Positive Y points toward the top of the viewer.

rack_layouts = {
    "triangle_10": (
        # Bottom row: 4 cups
        ArrangementPosition(-1.5 * D, 0),
        ArrangementPosition(-0.5 * D, 0),
        ArrangementPosition(0.5 * D, 0),
        ArrangementPosition(1.5 * D, 0),

        # Second row: 3 cups
        ArrangementPosition(-D, H),
        ArrangementPosition(0, H),
        ArrangementPosition(D, H),

        # Third row: 2 cups
        ArrangementPosition(-D / 2, 2 * H),
        ArrangementPosition(D / 2, 2 * H),

        # Top row: 1 cup
        ArrangementPosition(0, 3 * H),
    ),

    "triangle_6": (
        ArrangementPosition(-D, 0),
        ArrangementPosition(0, 0),
        ArrangementPosition(D, 0),
        ArrangementPosition(-D / 2, H),
        ArrangementPosition(D / 2, H),
        ArrangementPosition(0, 2 * H),
    ),

    "triangle_3": (
        ArrangementPosition(-D / 2, 0),
        ArrangementPosition(D / 2, 0),
        ArrangementPosition(0, H),
    ),

    "vertical_2": (
        ArrangementPosition(0, 0),
        ArrangementPosition(0, D),
    ),

    "backpack_kid_5": (
        ArrangementPosition(0, 0),
        ArrangementPosition(0, D),
        ArrangementPosition(0, 2 * D),
        ArrangementPosition(H, D / 2),
        ArrangementPosition(H, 1.5 * D),
    ),
}

def get_layout(layout_name):
    if layout_name not in rack_layouts:
        raise ValueError(f"Unknown layout: {layout_name}")

    return rack_layouts[layout_name]

def validate_layout(positions, cup_diameter=D):
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            a = positions[i]
            b = positions[j]

            distance = math.hypot(
                a.dx - b.dx,
                a.dy - b.dy
            )

            if distance < cup_diameter - 1e-6:
                return False

    return True

if __name__ == "__main__":
    for name, positions in rack_layouts.items():
        print(
            name,
            len(positions),
            "valid:",
            validate_layout(positions)
        )