"""
Headless cup pong game engine.

Owns the game state (active cups, parked cups, parking slots,
current formation, rearrangements left) and decides which cup
movements to make. It does not draw or move hardware: callers
plan a change, then execute it with a callback that animates the
movement (motion_viewer.py) or drives the gantry (game server).

Typical use:

    engine = GameEngine()
    plan = engine.plan_cup_removal(cup_id)
    engine.execute(plan, on_step=move_gantry)
    send_to_app(engine.snapshot())

Coordinates are in millimeters on the gantry workspace.
Positive Y points toward the FRONT of the table.
"""

from dataclasses import dataclass
import logging
from typing import NamedTuple

from config import cup as default_cup, gantry_workspace
from layouts import rack_layouts

from movement_planner import (
    TablePosition,
    distance_between,
    distance_from_segment,
    path_cost,
    fixed_parking_slots,
    new_parking_occupancy,
    choose_fixed_parking,
    choose_triangle_10_side_path,
    choose_triangle_10_middle_plan,
    choose_triangle_6_middle_plan,
    plan_interior_temporary_clearance,
    plan_rearrangement,
    aligned_formation_targets,
    is_position_valid,
)


log = logging.getLogger(__name__)


# ============================================================
# SETTINGS
# ============================================================

BACK_CLEARANCE_MM = 40
PARKING_CLEARANCE_MM = 15

STEP_MM = 15

# Placements of the new formation tried before giving up.
REARRANGE_ATTEMPTS = 3

# Default starting formation.
START_FORMATION = "triangle_6"

# Formations a game may start with.
START_FORMATIONS = ("triangle_10", "triangle_6")

# Rearrangements allowed per game.
MAX_REARRANGEMENTS = 1

# Optional rearrangement offered at each remaining-cup count.
REARRANGE_FORMATIONS = {
    6: "triangle_6",
    5: "backpack_kid_5",
    3: "triangle_3",
    2: "vertical_2",
}

TRIANGLE_10_SIDE_CUPS = {4, 6, 7, 8}
TRIANGLE_10_MIDDLE_CUPS = {1, 2, 5}
# Formation positions, not cup IDs (they differ after a rearrange).
TRIANGLE_6_MIDDLE_CUPS = {1}


# ============================================================
# TYPES
# ============================================================

class MoveStep(NamedTuple):
    """
    One cup movement. Same field order as the planner's step
    tuples, so it unpacks the same way.

    slot_id is the parking slot the cup ends in, or None when
    the cup stays on the playing area.
    """

    name: str
    cup_id: int
    start: TablePosition
    destination: TablePosition
    path: tuple
    slot_id: object = None

    def to_dict(self):
        return {
            "name": self.name,
            "cup_id": self.cup_id,
            "start": _position_dict(self.start),
            "destination": _position_dict(self.destination),
            "path": [_position_dict(p) for p in self.path],
            "slot_id": self.slot_id,
        }


@dataclass(frozen=True)
class Plan:
    """
    Movements for one game action, checked against the state
    they were planned from. Execute it with GameEngine.execute
    before anything else changes the game.
    """

    kind: str  # "remove" or "rearrange"
    steps: tuple
    cost: float
    version: int
    cup_id: object = None
    formation: object = None
    assignment: object = None
    targets: object = None

    def to_dict(self):
        return {
            "kind": self.kind,
            "cup_id": self.cup_id,
            "formation": self.formation,
            "cost_mm": round(self.cost, 2),
            "steps": [step.to_dict() for step in self.steps],
        }


class GameError(Exception):
    """An action is not allowed in the current game state."""


class PlanningError(GameError):
    """No collision-free plan was found. No cups were moved."""


# ============================================================
# FORMATION HELPERS
# ============================================================

def place_layout(name, workspace=gantry_workspace, cup=default_cup):
    """
    Position cups near the back of the table.

    The back is the bottom of the viewer.
    """

    if name not in rack_layouts:
        raise ValueError(f"{name} not defined in layouts.py")

    offsets = rack_layouts[name]

    min_x = min(p.dx for p in offsets)
    max_x = max(p.dx for p in offsets)
    min_y = min(p.dy for p in offsets)

    center_x = (min_x + max_x) / 2

    bottom_y = BACK_CLEARANCE_MM + cup.rim_diameter / 2

    positions = {
        cup_id: TablePosition(
            x=workspace.width / 2 + offset.dx - center_x,
            y=bottom_y + offset.dy - min_y,
        )
        for cup_id, offset in enumerate(offsets)
    }

    for cup_id, position in positions.items():
        obstacles = [
            other
            for other_id, other in positions.items()
            if other_id != cup_id
        ]

        if not is_position_valid(position, obstacles, workspace, cup):
            raise ValueError(
                f"Formation {name}: cup {cup_id} "
                "is outside workspace or overlaps."
            )

    return positions


def rearrange_option(layout_name, active, rearrangements_left):
    """Formation offered for the current cup count, if any."""

    if rearrangements_left <= 0:
        return None

    option = REARRANGE_FORMATIONS.get(len(active))

    if option == layout_name or option not in rack_layouts:
        return None

    return option


def validate_plan(
    steps,
    active,
    parked,
    slots,
    occupancy,
    workspace=gantry_workspace,
    cup=default_cup
):
    """
    Simulate all movements before execution.

    Validate:
    - Cup IDs
    - Starting positions
    - Path endpoints
    - Collision-free movements
    - Parking slot availability
    """

    simulated_active = dict(active)
    simulated_parked = dict(parked)
    simulated_occupancy = dict(occupancy)

    for (
        movement_name,
        cup_id,
        start,
        destination,
        path,
        slot_id
    ) in steps:

        if cup_id in simulated_active:
            actual = simulated_active.pop(cup_id)
            was_active = True

        elif cup_id in simulated_parked:
            actual = simulated_parked.pop(cup_id)
            was_active = False

        else:
            return False

        if distance_between(actual, start) > 0.01:
            return False

        if not path:
            return False

        if distance_between(path[0], start) > 0.01:
            return False

        if distance_between(path[-1], destination) > 0.01:
            return False

        obstacles = (
            list(simulated_active.values())
            + list(simulated_parked.values())
        )

        for position in path:
            if not is_position_valid(position, obstacles, workspace, cup):
                return False

        for a, b in zip(path, path[1:]):
            for obstacle in obstacles:
                if distance_from_segment(
                    obstacle, a, b
                ) < cup.rim_diameter - 1e-5:
                    return False

        if slot_id is not None:
            if slot_id not in slots:
                return False

            if simulated_occupancy.get(slot_id) is not None:
                return False

            if distance_between(slots[slot_id], destination) > 0.01:
                return False

            simulated_occupancy[slot_id] = cup_id
            simulated_parked[cup_id] = destination

        elif was_active:
            simulated_active[cup_id] = destination

        else:
            simulated_parked[cup_id] = destination

    return True


def _position_dict(position):
    return {"x_mm": round(position.x, 2), "y_mm": round(position.y, 2)}


# ============================================================
# GAME ENGINE
# ============================================================

class GameEngine:
    """
    Game state plus the rules for changing it.

    Read-only attributes for drawing or reporting:
        active        {cup_id: TablePosition} cups in play
        parked        {cup_id: TablePosition} cups in parking slots
        slots         {slot_id: TablePosition}
        occupancy     {slot_id: cup_id or None}
        layout_name   current formation
        gantry_position
        busy          True while execute() is running

    Change state only through the methods below.
    """

    def __init__(
        self,
        start_formation=START_FORMATION,
        workspace=gantry_workspace,
        cup=default_cup,
        max_rearrangements=MAX_REARRANGEMENTS
    ):
        self.workspace = workspace
        self.cup = cup
        self.max_rearrangements = max_rearrangements

        self.slots = fixed_parking_slots(
            workspace, cup, PARKING_CLEARANCE_MM
        )

        self.start_formation = start_formation
        self.busy = False
        # Increments on every state change; plans from an older
        # version are rejected.
        self.version = 0

        self.reset()

    # --------------------------------------------------------
    # Game setup
    # --------------------------------------------------------

    def reset(self, start_formation=None):
        """Rack a new game. Parked cups go back in the formation."""

        self._require_idle()

        if start_formation is not None:
            self._check_start_formation(start_formation)
            self.start_formation = start_formation

        self.layout_name = self.start_formation
        self.active = place_layout(
            self.layout_name, self.workspace, self.cup
        )

        # Active cup ID -> position index in the current formation.
        self.formation_index = {cup_id: cup_id for cup_id in self.active}

        # Formation position index -> table position, including
        # positions whose cups have been removed.
        self.formation_positions = dict(self.active)

        self.parked = {}
        self.occupancy = new_parking_occupancy(self.slots)
        self.rearrangements_left = self.max_rearrangements

        # The starting formation locks once any cup moves.
        self.game_started = False

        self.gantry_position = TablePosition(
            self.workspace.width / 2,
            self.workspace.length / 2
        )

        self._changed()

    def choose_start_formation(self, name):
        """Pick the starting formation. Only before the first move."""

        if self.game_started:
            raise GameError(
                "Game already started. Reset to choose again."
            )

        self.reset(name)

    def _check_start_formation(self, name):
        if name not in START_FORMATIONS:
            raise GameError(f"{name} is not a starting formation")

        if name not in rack_layouts:
            raise GameError(f"{name} not defined in layouts.py")

    # --------------------------------------------------------
    # Queries
    # --------------------------------------------------------

    @property
    def rearrange_option(self):
        """Formation the remaining cups can move into now, or None."""

        return rearrange_option(
            self.layout_name, self.active, self.rearrangements_left
        )

    @property
    def is_cleared(self):
        return not self.active

    def find_cup_near(self, position, tolerance=None):
        """
        Active cup whose center is closest to position, within
        tolerance mm (default: the cup's rim radius). Use this to
        match a detection in table coordinates to a cup.
        """

        if tolerance is None:
            tolerance = self.cup.rim_diameter / 2

        best_id = None
        best_distance = tolerance

        for cup_id, cup_position in self.active.items():
            distance = distance_between(position, cup_position)

            if distance <= best_distance:
                best_id = cup_id
                best_distance = distance

        return best_id

    def snapshot(self):
        """JSON-serializable view of the game for clients."""

        slot_of = {
            cup_id: slot_id
            for slot_id, cup_id in self.occupancy.items()
            if cup_id is not None
        }

        cups = [
            {
                "id": cup_id,
                "status": "active",
                "formation_index": self.formation_index.get(cup_id),
                **_position_dict(position),
            }
            for cup_id, position in sorted(self.active.items())
        ] + [
            {
                "id": cup_id,
                "status": "parked",
                "slot_id": slot_of.get(cup_id),
                **_position_dict(position),
            }
            for cup_id, position in sorted(self.parked.items())
        ]

        return {
            "version": self.version,
            "formation": self.layout_name,
            "start_formation": self.start_formation,
            "game_started": self.game_started,
            "busy": self.busy,
            "remaining": len(self.active),
            "rearrangements_left": self.rearrangements_left,
            "rearrange_option": self.rearrange_option,
            "cup_diameter_mm": self.cup.rim_diameter,
            "gantry": _position_dict(self.gantry_position),
            "cups": cups,
        }

    # --------------------------------------------------------
    # Planning
    # --------------------------------------------------------

    def plan_cup_removal(self, cup_id):
        """
        Plan parking a hit cup, moving blockers aside and back
        when needed. Raises GameError or PlanningError.
        """

        self._require_idle()

        if cup_id not in self.active:
            raise GameError(f"Cup {cup_id} is not in play")

        steps, cost = self._removal_steps(cup_id)

        steps = tuple(MoveStep(*step) for step in steps)

        if not self._validate(steps):
            raise PlanningError(
                f"Plan for cup {cup_id} failed validation. "
                "No cups moved."
            )

        log.info(
            "Cup %s: %d movements, %.2f mm",
            cup_id, len(steps), cost
        )

        return Plan(
            kind="remove",
            steps=steps,
            cost=cost,
            version=self.version,
            cup_id=cup_id,
        )

    def plan_rearrangement(self, formation=None):
        """
        Plan moving the remaining cups into the offered formation.
        formation, if given, must be the offered one.
        Raises GameError or PlanningError.
        """

        self._require_idle()

        if self.rearrangements_left <= 0:
            raise GameError("No rearrangements left")

        option = self.rearrange_option

        if option is None:
            raise GameError(
                f"No rearrangement offered for {len(self.active)} cups"
            )

        if formation is not None and formation != option:
            raise GameError(
                f"{formation} is not offered; the option is {option}"
            )

        log.info(
            "Rearranging %d cups into %s",
            len(self.active), option
        )

        candidates = aligned_formation_targets(
            place_layout(option, self.workspace, self.cup),
            self.formation_positions,
            self.active,
            self.parked,
            self.workspace,
            self.cup
        )

        for targets in candidates[:REARRANGE_ATTEMPTS]:
            result = plan_rearrangement(
                self.active,
                targets,
                self.parked,
                self.workspace,
                self.cup,
                step_size=STEP_MM
            )

            if result is None:
                continue

            steps, assignment = result
            steps = tuple(MoveStep(*step) for step in steps)

            if not self._validate(steps):
                continue

            cost = sum(path_cost(step.path) for step in steps)

            return Plan(
                kind="rearrange",
                steps=steps,
                cost=cost,
                version=self.version,
                formation=option,
                assignment=dict(assignment),
                targets=dict(targets),
            )

        raise PlanningError(
            "No valid rearrangement found. Cups not moved."
        )

    def _removal_steps(self, selected_id):
        active = self.active
        parked = self.parked
        source = active[selected_id]

        args = dict(
            workspace=self.workspace,
            cup=self.cup,
            slots=self.slots,
            occupancy=self.occupancy,
            step_size=STEP_MM,
        )

        # Step 1: hardcoded middle-cup strategies.
        if (
            self.layout_name == "triangle_10"
            and selected_id in TRIANGLE_10_MIDDLE_CUPS
        ):
            log.info(
                "Cup %s: using hardcoded middle-cup strategy",
                selected_id
            )

            result = choose_triangle_10_middle_plan(
                selected_id, active, parked,
                self.gantry_position, **args
            )

            if result is None:
                raise PlanningError(
                    "No valid middle-cup removal plan found."
                )

            return result

        if (
            self.layout_name == "triangle_6"
            and self.formation_index.get(selected_id)
            in TRIANGLE_6_MIDDLE_CUPS
        ):
            log.info(
                "Cup %s: using hardcoded middle-cup strategy",
                selected_id
            )

            result = choose_triangle_6_middle_plan(
                selected_id, active, parked,
                self.gantry_position,
                formation_index=self.formation_index,
                **args
            )

            if result is None:
                raise PlanningError(
                    "No valid middle-cup removal plan found."
                )

            return result

        # Step 2: side cups and other formations.
        obstacles = [
            position
            for cup_id, position in active.items()
            if cup_id != selected_id
        ] + list(parked.values())

        is_initial_triangle_10 = (
            self.layout_name == "triangle_10"
            and len(active) == 10
            and len(parked) == 0
        )

        direct = None

        if (
            is_initial_triangle_10
            and selected_id in TRIANGLE_10_SIDE_CUPS
        ):
            log.info(
                "Cup %s: attempting hardcoded side escape",
                selected_id
            )

            direct = choose_triangle_10_side_path(
                selected_id, source, obstacles,
                self.gantry_position, **args
            )

        # Try normal A* if no side escape was found.
        if direct is None:
            direct = choose_fixed_parking(
                source, obstacles, self.gantry_position, **args
            )

        if direct is not None:
            cost, slot_id, target, path = direct

            log.info("Direct parking path found: %s", slot_id)

            step = (
                f"Park cup in {slot_id}",
                selected_id,
                source,
                target,
                path,
                slot_id
            )

            return (step,), cost

        log.info(
            "No direct parking path. "
            "Attempting temporary relocation"
        )

        result = plan_interior_temporary_clearance(
            selected_id, active, parked,
            self.gantry_position, **args
        )

        if result is None:
            raise PlanningError(
                "No valid temporary relocation plan found."
            )

        return result

    def _validate(self, steps):
        return validate_plan(
            steps,
            self.active,
            self.parked,
            self.slots,
            self.occupancy,
            self.workspace,
            self.cup
        )

    # --------------------------------------------------------
    # Execution
    # --------------------------------------------------------

    def execute(self, plan, on_step=None):
        """
        Carry out a plan one movement at a time.

        on_step(step) is called for each MoveStep and should
        return once the cup has reached step.destination (animate
        it, or wait for the gantry). While it runs, the moving cup
        is in neither active nor parked.

        If on_step raises, the moving cup is recorded back at its
        start, the rest of the plan is dropped, and the error is
        re-raised. Cups already moved stay where they ended up.
        """

        self._require_idle()

        if plan.version != self.version:
            raise GameError(
                "Plan is out of date; the game changed after it "
                "was planned"
            )

        self.busy = True

        try:
            for step in plan.steps:
                self._run_step(step, on_step)

            if plan.kind == "rearrange":
                self.layout_name = plan.formation
                self.formation_index = dict(plan.assignment)
                self.formation_positions = dict(plan.targets)
                self.rearrangements_left -= 1

            self.game_started = True

        finally:
            self.busy = False
            self._changed()

    def _run_step(self, step, on_step):
        was_active = step.cup_id in self.active

        if was_active:
            self.active.pop(step.cup_id)
        else:
            self.parked.pop(step.cup_id)

        try:
            if on_step is not None:
                on_step(step)

        except BaseException:
            if was_active:
                self.active[step.cup_id] = step.start
            else:
                self.parked[step.cup_id] = step.start

            # Some movement may already have happened.
            self.game_started = True
            raise

        if step.slot_id is not None:
            self.parked[step.cup_id] = step.destination
            self.occupancy[step.slot_id] = step.cup_id
        else:
            self.active[step.cup_id] = step.destination

        self.gantry_position = step.destination

    # --------------------------------------------------------
    # Internals
    # --------------------------------------------------------

    def _require_idle(self):
        if self.busy:
            raise GameError("Gantry is moving; try again when it stops")

    def _changed(self):
        self.version += 1
