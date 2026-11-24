"""
Cup Pong Motion Viewer

Draws the game and animates cup movements. The game state and
movement planning live in game_engine.GameEngine; this file is
one client of it, driven by the mouse and keyboard.

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

import logging
import math

import cv2
import numpy as np

from config import cup, gantry_workspace

from movement_planner import (
    TablePosition,
    distance_between,
)

from game_engine import (
    GameEngine,
    GameError,
)


# ============================================================
# SETTINGS
# ============================================================

WINDOW_NAME = "Cup Pong Motion Viewer"

SCALE = 0.60

FRAME_DELAY_MS = 25

REARRANGE_KEYS = {ord("f"), ord("F")}

# Keys choosing the starting formation before the first move.
START_FORMATION_KEYS = {
    ord("1"): "triangle_10",
    ord("2"): "triangle_6",
}


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
# EXECUTION
# ============================================================

def animate_step(engine, step):
    """Animate one movement. The engine updates state afterwards."""

    print(f"Executing: {step.name} (cup {step.cup_id})")

    for moving_position in interpolate(step.path):
        frame = render(
            engine.active,
            engine.parked,
            engine.slots,
            engine.occupancy,
            moving=(step.cup_id, moving_position),
            path=step.path,
            title=step.name
        )

        cv2.imshow(WINDOW_NAME, frame)
        cv2.waitKey(FRAME_DELAY_MS)


def run_plan(engine, plan):
    engine.execute(
        plan,
        on_step=lambda step: animate_step(engine, step)
    )


def print_occupancy(engine):
    print(
        "Occupied slots:",
        {
            slot_id: cup_id
            for slot_id, cup_id in engine.occupancy.items()
            if cup_id is not None
        }
    )


# ============================================================
# MAIN
# ============================================================

def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    engine = GameEngine()

    canvas_height = int(gantry_workspace.length * SCALE)

    state = {"clicked_id": None}

    def on_mouse(event, mouse_x, mouse_y, flags, parameters):
        if event != cv2.EVENT_LBUTTONDOWN:
            return

        for cup_id, position in engine.active.items():
            px, py = pixel(position, canvas_height)

            distance = math.hypot(mouse_x - px, mouse_y - py)

            if distance <= cup.rim_diameter / 2 * SCALE:
                parameters["clicked_id"] = cup_id
                break

    cv2.namedWindow(WINDOW_NAME)
    cv2.setMouseCallback(WINDOW_NAME, on_mouse, state)

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
        option = engine.rearrange_option

        title = engine.layout_name

        if not engine.game_started:
            title += " | Start: 1=tri10 2=tri6"
        elif option is not None:
            title += f" | F: {option}"
        elif engine.rearrangements_left <= 0:
            title += " | No rearrangements left"

        cv2.imshow(
            WINDOW_NAME,
            render(
                engine.active,
                engine.parked,
                engine.slots,
                engine.occupancy,
                title=title
            )
        )

        key = cv2.waitKeyEx(30)

        if key in (27, ord("q"), ord("Q")):
            break

        # ----------------------------------------------------
        # Choose starting formation
        # ----------------------------------------------------

        if key in START_FORMATION_KEYS:
            state["clicked_id"] = None

            try:
                engine.choose_start_formation(
                    START_FORMATION_KEYS[key]
                )
            except GameError as error:
                print(error)
                continue

            print("Starting formation:", engine.layout_name)
            continue

        # ----------------------------------------------------
        # Optional rearrangement
        # ----------------------------------------------------

        if key in REARRANGE_KEYS:
            state["clicked_id"] = None

            if engine.rearrangements_left <= 0:
                print("No rearrangements left.")
                continue

            if option is None:
                continue

            print()
            print("------------------------------------")

            try:
                plan = engine.plan_rearrangement()
            except GameError as error:
                print(error)
                continue

            run_plan(engine, plan)

            print(f"Formation: {engine.layout_name}")
            print(
                f"Rearrangements left: {engine.rearrangements_left}"
            )
            print("------------------------------------")
            continue

        # ----------------------------------------------------
        # Reset formation
        # ----------------------------------------------------

        if key in (ord("r"), ord("R")):
            engine.reset()
            state["clicked_id"] = None

            print("Reset:", engine.layout_name)
            continue

        # ----------------------------------------------------
        # Handle cup selection
        # ----------------------------------------------------

        selected_id = state["clicked_id"]
        state["clicked_id"] = None

        if selected_id is None or selected_id not in engine.active:
            continue

        print()
        print("------------------------------------")
        print(f"Formation: {engine.layout_name}")
        print(f"Selected cup ID: {selected_id}")

        try:
            plan = engine.plan_cup_removal(selected_id)
        except GameError as error:
            print(error)
            continue

        print(f"Total movements: {len(plan.steps)}")
        print(f"Estimated gantry travel: {plan.cost:.2f} mm")

        run_plan(engine, plan)

        print()
        print("Movement completed.")
        print(f"Remaining active cups: {len(engine.active)}")
        print(f"Parked cups: {len(engine.parked)}")
        print_occupancy(engine)

        option = engine.rearrange_option

        if option is not None:
            print(
                f"{len(engine.active)} cups left: press F to "
                f"rearrange into {option}, or keep playing."
            )

        print("------------------------------------")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
