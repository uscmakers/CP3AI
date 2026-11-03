
"""
Cup Pong Motion Viewer

Features:
- Five fixed parking slots on each side
- Bottom-up parking slot arrangement
- Parking occupancy tracking
- Collision-aware A* pathfinding
- Hardcoded triangle_10 side escapes
- Hardcoded triangle_10 middle-cup strategies
- Hardcoded triangle_6 middle-cup strategy
- Temporary blocker relocation and restoration
- Permanent cup IDs
- Animated cup movements

Game flow:
    Choose triangle_10 or triangle_6 before the first move; the
    choice locks once any cup moves. When 6, 5, 3, or 2 cups
    remain, the remaining cups can optionally be rearranged into
    triangle_6, backpack_kid_5, triangle_3, or vertical_2. Only
    one rearrangement is allowed per game. Parked cups stay in
    their slots.

Controls:
    1 / 2           - Start with triangle_10 / triangle_6
                      (before the first move only)
    Click cup       - Park selected cup
    F               - Rearrange into the offered formation
                      (once per game)
    R               - Reset to the chosen starting formation
    Q / ESC         - Quit
"""

import math

import cv2
import numpy as np

from config import cup, gantry_workspace
from layouts import rack_layouts

from movement_planner import (
    TablePosition,
    distance_between,
    distance_from_segment,
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


# ============================================================
# SETTINGS
# ============================================================

WINDOW_NAME = "Cup Pong Motion Viewer"

SCALE = 0.60

BACK_CLEARANCE_MM = 40
PARKING_CLEARANCE_MM = 15

STEP_MM = 15
FRAME_DELAY_MS = 25

REARRANGE_KEYS = {ord("f"), ord("F")}

# Placements of the new formation tried before giving up.
REARRANGE_ATTEMPTS = 3

# Default starting formation.
START_FORMATION = "triangle_6"

# Keys choosing the starting formation before the first move.
START_FORMATION_KEYS = {
    ord("1"): "triangle_10",
    ord("2"): "triangle_6",
}

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
# FORMATION POSITIONING
# ============================================================

def place_layout(name):
    """
    Position cups near the back of the table.

    The back is the bottom of the viewer.
    """

    offsets = rack_layouts[name]

    min_x = min(p.dx for p in offsets)
    max_x = max(p.dx for p in offsets)
    min_y = min(p.dy for p in offsets)

    center_x = (min_x + max_x) / 2

    bottom_y = (
        BACK_CLEARANCE_MM
        + cup.rim_diameter / 2
    )

    positions = {}

    for cup_id, offset in enumerate(offsets):
        positions[cup_id] = TablePosition(
            x=(
                gantry_workspace.width / 2
                + offset.dx
                - center_x
            ),
            y=(
                bottom_y
                + offset.dy
                - min_y
            )
        )

    for cup_id, position in positions.items():
        obstacles = [
            other
            for other_id, other in positions.items()
            if other_id != cup_id
        ]

        if not is_position_valid(
            position,
            obstacles,
            gantry_workspace,
            cup
        ):
            raise ValueError(
                f"Formation {name}: cup {cup_id} "
                "is outside workspace or overlaps."
            )

    return positions


# ============================================================
# COORDINATE CONVERSION
# ============================================================

def pixel(position, canvas_height):
    return (
        int(round(position.x * SCALE)),
        canvas_height - 1 - int(round(position.y * SCALE))
    )


# ============================================================
# DRAWING
# ============================================================

def draw_circle(
    image,
    position,
    radius,
    color,
    label,
    text_color=(255, 255, 255)
):
    center = pixel(position, image.shape[0])

    cv2.circle(
        image,
        center,
        radius,
        color,
        -1
    )

    cv2.circle(
        image,
        center,
        radius,
        (255, 255, 255),
        2
    )

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.48
    thickness = 2

    text = str(label)

    (text_width, text_height), _ = cv2.getTextSize(
        text,
        font,
        font_scale,
        thickness
    )

    cv2.putText(
        image,
        text,
        (
            center[0] - text_width // 2,
            center[1] + text_height // 2
        ),
        font,
        font_scale,
        text_color,
        thickness
    )


def render(
    active,
    parked,
    slots,
    occupancy,
    moving=None,
    path=None,
    title=""
):
    width = int(gantry_workspace.width * SCALE)
    height = int(gantry_workspace.length * SCALE)

    image = np.full(
        (height, width, 3),
        (110, 160, 100),
        dtype=np.uint8
    )

    cv2.rectangle(
        image,
        (1, 1),
        (width - 2, height - 2),
        (255, 255, 255),
        2
    )

    radius = max(
        2,
        round(cup.rim_diameter / 2 * SCALE)
    )

    # Draw empty parking slots.
    for slot_id, position in slots.items():
        if occupancy[slot_id] is None:
            draw_circle(
                image,
                position,
                radius,
                (125, 165, 125),
                slot_id
            )

    # Draw movement path.
    if path is not None:
        for start, end in zip(path, path[1:]):
            cv2.line(
                image,
                pixel(start, height),
                pixel(end, height),
                (255, 220, 50),
                2
            )

    # Draw active cups.
    for cup_id, position in active.items():
        draw_circle(
            image,
            position,
            radius,
            (35, 45, 220),
            cup_id
        )

    # Draw parked cups.
    for cup_id, position in parked.items():
        draw_circle(
            image,
            position,
            radius,
            (125, 125, 125),
            cup_id
        )

    # Draw moving cup.
    if moving is not None:
        moving_id, moving_position = moving

        draw_circle(
            image,
            moving_position,
            radius,
            (0, 220, 255),
            moving_id,
            (0, 0, 0)
        )

    cv2.putText(
        image,
        "FRONT",
        (8, 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2
    )

    cv2.putText(
        image,
        "BACK",
        (8, height - 12),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        2
    )

    if title:
        cv2.putText(
            image,
            title[:45],
            (8, 45),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1
        )

    return image


# ============================================================
# ANIMATION
# ============================================================

def interpolate(path, distance_step=7):
    for start, end in zip(path, path[1:]):
        distance = distance_between(start, end)

        steps = max(
            1,
            int(math.ceil(distance / distance_step))
        )

        for i in range(steps):
            t = i / steps

            yield TablePosition(
                start.x + (end.x - start.x) * t,
                start.y + (end.y - start.y) * t
            )

    yield path[-1]


# ============================================================
# PLAN VALIDATION
# ============================================================

def validate_plan(
    steps,
    active,
    parked,
    slots,
    occupancy
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

        if distance_between(
            path[-1], destination
        ) > 0.01:
            return False

        obstacles = (
            list(simulated_active.values())
            + list(simulated_parked.values())
        )

        for position in path:
            if not is_position_valid(
                position,
                obstacles,
                gantry_workspace,
                cup
            ):
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

            if simulated_occupancy.get(
                slot_id
            ) is not None:
                return False

            if distance_between(
                slots[slot_id],
                destination
            ) > 0.01:
                return False

            simulated_occupancy[slot_id] = cup_id
            simulated_parked[cup_id] = destination

        elif was_active:
            simulated_active[cup_id] = destination

        else:
            simulated_parked[cup_id] = destination

    return True


# ============================================================
# EXECUTION
# ============================================================

def rearrange_option(
    layout_name,
    active,
    rearrangements_left
):
    """Formation offered for the current cup count, if any."""

    if rearrangements_left <= 0:
        return None

    option = REARRANGE_FORMATIONS.get(len(active))

    if option == layout_name or option not in rack_layouts:
        return None

    return option


def execute_steps(
    steps,
    active,
    parked,
    slots,
    occupancy
):
    """
    Animate movements and update state in place.

    Returns the final gantry position.
    """

    gantry_position = None

    for (
        movement_name,
        moving_id,
        start,
        destination,
        path,
        slot_id
    ) in steps:
        print(
            f"Executing: {movement_name} "
            f"(cup {moving_id})"
        )

        if moving_id in active:
            active.pop(moving_id)
        else:
            parked.pop(moving_id)

        for moving_position in interpolate(path):
            frame = render(
                active,
                parked,
                slots,
                occupancy,
                moving=(
                    moving_id,
                    moving_position
                ),
                path=path,
                title=movement_name
            )

            cv2.imshow(
                WINDOW_NAME,
                frame
            )

            cv2.waitKey(FRAME_DELAY_MS)

        if slot_id is not None:
            parked[moving_id] = destination
            occupancy[slot_id] = moving_id
        else:
            active[moving_id] = destination

        gantry_position = destination

    return gantry_position


# ============================================================
# MAIN
# ============================================================

def main():
    if START_FORMATION not in rack_layouts:
        raise ValueError(
            f"{START_FORMATION} not defined in layouts.py"
        )

    slots = fixed_parking_slots(
        gantry_workspace,
        cup,
        PARKING_CLEARANCE_MM
    )

    occupancy = new_parking_occupancy(slots)

    start_formation = START_FORMATION

    layout_name = start_formation

    active = place_layout(layout_name)

    # Active cup ID -> position index in the current formation.
    formation_index = {
        cup_id: cup_id for cup_id in active
    }

    # Formation position index -> table position, including
    # positions whose cups have been removed.
    formation_positions = dict(active)

    # Starting formation locks once any cup moves.
    game_started = False

    parked = {}

    rearrangements_left = MAX_REARRANGEMENTS

    gantry_position = TablePosition(
        gantry_workspace.width / 2,
        gantry_workspace.length / 2
    )

    canvas_height = int(
        gantry_workspace.length * SCALE
    )

    state = {
        "clicked_id": None,
        "active": active
    }

    def on_mouse(
        event,
        mouse_x,
        mouse_y,
        flags,
        parameters
    ):
        if event != cv2.EVENT_LBUTTONDOWN:
            return

        for cup_id, position in parameters[
            "active"
        ].items():
            px, py = pixel(position, canvas_height)

            distance = math.hypot(
                mouse_x - px,
                mouse_y - py
            )

            if distance <= (
                cup.rim_diameter / 2 * SCALE
            ):
                parameters["clicked_id"] = cup_id
                break

    cv2.namedWindow(WINDOW_NAME)

    cv2.setMouseCallback(
        WINDOW_NAME,
        on_mouse,
        state
    )

    print()
    print("====================================")
    print(" CUP PONG MOTION VIEWER")
    print("====================================")
    print("1/2: Start with triangle_10/triangle_6")
    print("Click: Park cup")
    print("F: Rearrange when offered")
    print("R: Reset")
    print("Q: Quit")
    print()

    while True:
        state["active"] = active

        option = rearrange_option(
            layout_name,
            active,
            rearrangements_left
        )

        title = layout_name

        if not game_started:
            title += " | Start: 1=tri10 2=tri6"
        elif option is not None:
            title += f" | F: {option}"
        elif rearrangements_left <= 0:
            title += " | No rearrangements left"

        cv2.imshow(
            WINDOW_NAME,
            render(
                active,
                parked,
                slots,
                occupancy,
                title=title
            )
        )

        key = cv2.waitKeyEx(30)

        if key in (
            27,
            ord("q"),
            ord("Q")
        ):
            break

        # ----------------------------------------------------
        # Choose starting formation
        # ----------------------------------------------------

        if key in START_FORMATION_KEYS:
            state["clicked_id"] = None

            if game_started:
                print(
                    "Game already started. "
                    "Press R to reset and choose again."
                )
                continue

            choice = START_FORMATION_KEYS[key]

            if choice not in rack_layouts:
                print(f"{choice} not defined in layouts.py")
                continue

            start_formation = choice
            layout_name = start_formation

            active = place_layout(layout_name)

            formation_index = {
                cup_id: cup_id for cup_id in active
            }

            formation_positions = dict(active)

            print("Starting formation:", layout_name)

            continue

        # ----------------------------------------------------
        # Optional rearrangement
        # ----------------------------------------------------

        if key in REARRANGE_KEYS:
            state["clicked_id"] = None

            if rearrangements_left <= 0:
                print("No rearrangements left.")
                continue

            if option is None:
                continue

            print()
            print("------------------------------------")
            print(
                f"Rearranging {len(active)} cups "
                f"into {option}..."
            )

            candidates = aligned_formation_targets(
                place_layout(option),
                formation_positions,
                active,
                parked,
                gantry_workspace,
                cup
            )

            result = None

            for targets in candidates[:REARRANGE_ATTEMPTS]:
                result = plan_rearrangement(
                    active,
                    targets,
                    parked,
                    gantry_workspace,
                    cup,
                    step_size=STEP_MM
                )

                if result is not None and validate_plan(
                    result[0],
                    active,
                    parked,
                    slots,
                    occupancy
                ):
                    break

                result = None

            if result is None:
                print(
                    "No valid rearrangement found. "
                    "Cups not moved."
                )
                continue

            steps, assignment = result

            final_position = execute_steps(
                steps,
                active,
                parked,
                slots,
                occupancy
            )

            if final_position is not None:
                gantry_position = final_position

            layout_name = option
            formation_index = assignment
            formation_positions = targets
            rearrangements_left -= 1
            game_started = True

            print(f"Formation: {layout_name}")
            print("No rearrangements left.")
            print("------------------------------------")

            continue

        # ----------------------------------------------------
        # Reset formation
        # ----------------------------------------------------

        if key in (ord("r"), ord("R")):
            layout_name = start_formation

            active = place_layout(layout_name)

            formation_index = {
                cup_id: cup_id for cup_id in active
            }

            formation_positions = dict(active)

            game_started = False

            parked = {}
            occupancy = new_parking_occupancy(slots)

            rearrangements_left = MAX_REARRANGEMENTS

            gantry_position = TablePosition(
                gantry_workspace.width / 2,
                gantry_workspace.length / 2
            )

            state["clicked_id"] = None

            print("Reset:", layout_name)

            continue

        # ----------------------------------------------------
        # Handle cup selection
        # ----------------------------------------------------

        selected_id = state["clicked_id"]
        state["clicked_id"] = None

        if (
            selected_id is None
            or selected_id not in active
        ):
            continue

        source = active[selected_id]

        obstacles = [
            position
            for cup_id, position in active.items()
            if cup_id != selected_id
        ]

        obstacles += list(parked.values())

        print()
        print("------------------------------------")
        print(f"Formation: {layout_name}")
        print(f"Selected cup ID: {selected_id}")

        steps = None
        cost = None

        # ----------------------------------------------------
        # Step 1: Hardcoded middle-cup strategy
        # ----------------------------------------------------

        if (
            layout_name == "triangle_10"
            and selected_id in TRIANGLE_10_MIDDLE_CUPS
        ):
            print(
                f"Cup {selected_id}: using "
                "hardcoded middle-cup strategy..."
            )

            result = choose_triangle_10_middle_plan(
                selected_id,
                active,
                parked,
                gantry_position,
                gantry_workspace,
                cup,
                slots,
                occupancy,
                step_size=STEP_MM
            )

            if result is None:
                print(
                    "No valid middle-cup removal plan found."
                )
                continue

            steps, cost = result

        elif (
            layout_name == "triangle_6"
            and formation_index.get(selected_id)
            in TRIANGLE_6_MIDDLE_CUPS
        ):
            print(
                f"Cup {selected_id}: using "
                "hardcoded middle-cup strategy..."
            )

            result = choose_triangle_6_middle_plan(
                selected_id,
                active,
                parked,
                gantry_position,
                gantry_workspace,
                cup,
                slots,
                occupancy,
                step_size=STEP_MM,
                formation_index=formation_index
            )

            if result is None:
                print(
                    "No valid middle-cup removal plan found."
                )
                continue

            steps, cost = result

        # ----------------------------------------------------
        # Step 2: Side cups and other formations
        # ----------------------------------------------------

        else:
            is_initial_triangle_10 = (
                layout_name == "triangle_10"
                and len(active) == 10
                and len(parked) == 0
            )

            direct = None

            if (
                is_initial_triangle_10
                and selected_id in TRIANGLE_10_SIDE_CUPS
            ):
                print(
                    f"Cup {selected_id}: "
                    "attempting hardcoded side escape..."
                )

                direct = choose_triangle_10_side_path(
                    selected_id,
                    source,
                    obstacles,
                    gantry_position,
                    gantry_workspace,
                    cup,
                    slots,
                    occupancy,
                    step_size=STEP_MM
                )

            # Try normal A* if no side escape found.
            if direct is None:
                direct = choose_fixed_parking(
                    source,
                    obstacles,
                    gantry_position,
                    gantry_workspace,
                    cup,
                    slots,
                    occupancy,
                    step_size=STEP_MM
                )

            if direct is not None:
                cost, slot_id, target, path = direct

                steps = (
                    (
                        f"Park cup in {slot_id}",
                        selected_id,
                        source,
                        target,
                        path,
                        slot_id
                    ),
                )

                print(
                    f"Direct parking path found: {slot_id}"
                )

            else:
                print(
                    "No direct parking path. "
                    "Attempting temporary relocation..."
                )

                result = plan_interior_temporary_clearance(
                    selected_id,
                    active,
                    parked,
                    gantry_position,
                    gantry_workspace,
                    cup,
                    slots,
                    occupancy,
                    step_size=STEP_MM
                )

                if result is None:
                    print(
                        "No valid temporary relocation plan found."
                    )
                    continue

                steps, cost = result

        # ----------------------------------------------------
        # Step 3: Validate complete plan
        # ----------------------------------------------------

        if not validate_plan(
            steps,
            active,
            parked,
            slots,
            occupancy
        ):
            print(
                "Plan validation failed. "
                "No cups moved."
            )
            continue

        print(
            f"Total movements: {len(steps)}"
        )

        print(
            f"Estimated gantry travel: {cost:.2f} mm"
        )

        # ----------------------------------------------------
        # Step 4: Execute movements
        # ----------------------------------------------------

        gantry_position = execute_steps(
            steps,
            active,
            parked,
            slots,
            occupancy
        )

        game_started = True

        print()
        print("Movement completed.")
        print(
            f"Remaining active cups: {len(active)}"
        )
        print(f"Parked cups: {len(parked)}")
        print(
            "Occupied slots:",
            {
                slot_id: cup_id
                for slot_id, cup_id in occupancy.items()
                if cup_id is not None
            }
        )

        option = rearrange_option(
            layout_name,
            active,
            rearrangements_left
        )

        if option is not None:
            print(
                f"{len(active)} cups left: press F to "
                f"rearrange into {option}, or keep playing."
            )

        print("------------------------------------")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
