from dataclasses import dataclass


@dataclass(frozen=True)
class TableDimensions:
    width: float
    length: float


@dataclass(frozen=True)
class CupDimensions:
    rim_diameter: float
    height: float


# All dimensions in millimeters
cup = CupDimensions(
    rim_diameter=92,
    height=123
)

table = TableDimensions(
    width=810,
    length=2438
)

gantry_workspace = TableDimensions(
    width=810,
    length=1219
)