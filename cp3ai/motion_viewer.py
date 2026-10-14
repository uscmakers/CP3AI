# had chat make this

import cv2
import numpy as np

from config import cup, gantry_workspace
from layouts import rack_layouts

from movement_planner import (
    TablePosition,
    distance_between,
    find_path,
    find_rearrangement_plan,
    generate_buffers,
    get_removed_cup_target,
    path_cost,
)


WINDOW_NAME = "Rack Layout Browser"
PIXELS_PER_MM = 0.5
EDGE_CLEARANCE = 0
BUFFER_COUNT = 2
BUFFER_CLEARANCE = 20
PLANNER_STEP_SIZE = 40
# 1.0 proves the shortest plan; values above 1.0 favor viewer responsiveness.
HIGH_LEVEL_HEURISTIC_WEIGHT = 2.25

# OpenCV reports different arrow-key values across operating systems/backends.
LEFT_ARROW_KEYS = {81, 63234, 65361, 2424832}
RIGHT_ARROW_KEYS = {83, 63235, 65363, 2555904}


def table_to_pixel(position, canvas_height, pixels_per_mm):
    pixel_x = int(position.x * pixels_per_mm)

    pixel_y = (
        canvas_height
        - 1
        - int(position.y * pixels_per_mm)
    )

    return (pixel_x, pixel_y)


def draw_frame(
    path,
    moving_position,
    obstacles,
    workspace,
    cup,
    pixels_per_mm
):
    canvas_width = int(
        workspace.width * pixels_per_mm
    )

    canvas_height = int(
        workspace.length * pixels_per_mm
    )

    # Light-green table
    canvas = np.full(
        (canvas_height, canvas_width, 3),
        (120, 190, 130),
        dtype=np.uint8
    )

    # White table boundary
    cv2.rectangle(
        canvas,
        (0, 0),
        (canvas_width - 1, canvas_height - 1),
        (255, 255, 255),
        3
    )

    cup_radius = int(
        cup.rim_diameter
        / 2
        * pixels_per_mm
    )

    # Draw planned path
    for i in range(len(path) - 1):
        start_pixel = table_to_pixel(
            path[i],
            canvas_height,
            pixels_per_mm
        )

        end_pixel = table_to_pixel(
            path[i + 1],
            canvas_height,
            pixels_per_mm
        )

        cv2.line(
            canvas,
            start_pixel,
            end_pixel,
            (255, 100, 0),
            2
        )

    # Draw stationary cups
    for obstacle in obstacles:
        obstacle_pixel = table_to_pixel(
            obstacle,
            canvas_height,
            pixels_per_mm
        )

        cv2.circle(
            canvas,
            obstacle_pixel,
            cup_radius,
            (0, 0, 220),
            -1
        )

        cv2.circle(
            canvas,
            obstacle_pixel,
            cup_radius,
            (255, 255, 255),
            2
        )

    # Draw target
    target_pixel = table_to_pixel(
        path[-1],
        canvas_height,
        pixels_per_mm
    )

    cv2.circle(
        canvas,
        target_pixel,
        cup_radius + 5,
        (0, 120, 0),
        3
    )

    # Draw moving cup
    moving_pixel = table_to_pixel(
        moving_position,
        canvas_height,
        pixels_per_mm
    )

    cv2.circle(
        canvas,
        moving_pixel,
        cup_radius,
        (0, 0, 220),
        -1
    )

    cv2.circle(
        canvas,
        moving_pixel,
        cup_radius,
        (255, 255, 255),
        2
    )

    cv2.circle(
        canvas,
        moving_pixel,
        cup_radius + 5,
        (0, 255, 255),
        2
    )

    return canvas


def draw_layout(
    cup_positions,
    workspace,
    cup,
    pixels_per_mm=PIXELS_PER_MM,
    selected_index=None
):
    canvas_width = int(workspace.width * pixels_per_mm)
    canvas_height = int(workspace.length * pixels_per_mm)

    canvas = np.full(
        (canvas_height, canvas_width, 3),
        (120, 190, 130),
        dtype=np.uint8
    )

    cv2.rectangle(
        canvas,
        (0, 0),
        (canvas_width - 1, canvas_height - 1),
        (255, 255, 255),
        3
    )

    cup_radius = int(cup.rim_diameter / 2 * pixels_per_mm)

    for index, position in enumerate(cup_positions):
        pixel_position = table_to_pixel(
            position,
            canvas_height,
            pixels_per_mm
        )

        cv2.circle(
            canvas,
            pixel_position,
            cup_radius,
            (0, 0, 220),
            -1
        )

        cv2.circle(
            canvas,
            pixel_position,
            cup_radius,
            (255, 255, 255),
            2
        )

        if index == selected_index:
            cv2.circle(
                canvas,
                pixel_position,
                cup_radius + 5,
                (0, 255, 255),
                2
            )

    return canvas


def animate_path(
    path,
    obstacles,
    workspace,
    cup,
    pixels_per_mm=0.5
):
    for position in path:
        frame = draw_frame(
            path=path,
            moving_position=position,
            obstacles=obstacles,
            workspace=workspace,
            cup=cup,
            pixels_per_mm=pixels_per_mm
        )

        cv2.imshow("Cup Motion", frame)

        key = cv2.waitKey(40)

        if key == 27 or key == ord("q"):
            break

    cv2.waitKey(0)
    cv2.destroyAllWindows()




def animate_plan(
    paths,
    initial_cup_positions,
    workspace,
    cup,
    pixels_per_mm=0.5
):
    current_positions = list(initial_cup_positions)

    for path in paths:
        moving_start = path[0]

        obstacles = tuple(
            position
            for position in current_positions
            if position != moving_start
        )

        for moving_position in path:
            frame = draw_frame(
                path=path,
                moving_position=moving_position,
                obstacles=obstacles,
                workspace=workspace,
                cup=cup,
                pixels_per_mm=pixels_per_mm
            )

            cv2.imshow(WINDOW_NAME, frame)

            key = cv2.waitKey(40) & 0xFF

            if key == 27 or key == ord("q"):
                return False

        # Update the simulated physical state.
        current_positions.remove(moving_start)
        current_positions.append(path[-1])

    cv2.waitKey(700)
    return True


def place_layout(layout_name, anchor):
    offsets = rack_layouts[layout_name]

    minimum_dx = min(offset.dx for offset in offsets)
    maximum_dx = max(offset.dx for offset in offsets)
    minimum_dy = min(offset.dy for offset in offsets)
    maximum_dy = max(offset.dy for offset in offsets)

    layout_center_dx = (minimum_dx + maximum_dx) / 2
    layout_center_dy = (minimum_dy + maximum_dy) / 2

    return tuple(
        TablePosition(
            x=anchor.x + offset.dx - layout_center_dx,
            y=anchor.y + offset.dy - layout_center_dy
        )
        for offset in offsets
    )


def plan_selected_cup(
    cup_positions,
    scored_index,
    removed_count,
    gantry_start=None
):
    scored_position = cup_positions[scored_index]

    if gantry_start is None:
        gantry_start = TablePosition(
            x=gantry_workspace.width / 2,
            y=gantry_workspace.length / 2
        )

    parking_target = get_removed_cup_target(
        removed_count=removed_count,
        table=gantry_workspace,
        cup=cup,
        edge_clearance=EDGE_CLEARANCE
    )

    # Most exposed cups can go directly to parking. This is much faster than
    # running the high-level rearrangement search for every click.
    direct_obstacles = tuple(
        position
        for index, position in enumerate(cup_positions)
        if index != scored_index
    )
    direct_path = find_path(
        start=scored_position,
        goal=parking_target,
        obstacles=direct_obstacles,
        workspace=gantry_workspace,
        cup=cup,
        edge_clearance=EDGE_CLEARANCE,
        step_size=PLANNER_STEP_SIZE
    )

    if direct_path is not None:
        gantry_reposition_cost = distance_between(
            gantry_start,
            scored_position
        )
        total_cost = gantry_reposition_cost + path_cost(direct_path)
        return ((direct_path,), total_cost, parking_target)

    temporary_positions = frozenset(
        generate_buffers(
            rack_positions=cup_positions,
            parking_target=parking_target,
            workspace=gantry_workspace,
            cup=cup,
            edge_clearance=EDGE_CLEARANCE,
            count=BUFFER_COUNT,
            buffer_clearance=BUFFER_CLEARANCE
        )
    )

    start_state = frozenset(cup_positions)
    goal_state = (
        start_state
        - {scored_position}
        | {parking_target}
    )
    destinations = (
        start_state
        | temporary_positions
        | {parking_target}
    )

    print("Generated buffers:", tuple(temporary_positions))

    result = find_rearrangement_plan(
        start_state=start_state,
        goal_state=goal_state,
        destinations=destinations,
        parking_target=parking_target,
        workspace=gantry_workspace,
        cup=cup,
        edge_clearance=EDGE_CLEARANCE,
        step_size=PLANNER_STEP_SIZE,
        gantry_start=gantry_start,
        heuristic_weight=HIGH_LEVEL_HEURISTIC_WEIGHT
    )

    if result is None:
        return None

    paths, total_cost = result
    return (paths, total_cost, parking_target)


def main():
    anchor = TablePosition(
        x=gantry_workspace.width / 2,
        y=800
    )

    layout_names = tuple(rack_layouts.keys())
    current_layout_index = 0

    active_positions = list(
        place_layout(layout_names[current_layout_index], anchor)
    )
    parked_positions = []
    gantry_position = anchor

    canvas_height = int(gantry_workspace.length * PIXELS_PER_MM)
    clickable_cup_radius = int(cup.rim_diameter / 2 * PIXELS_PER_MM)

    browser_state = {
        "cup_positions": (),
        "clicked_index": None,
        "accept_clicks": True,
    }

    def handle_mouse(event, pixel_x, pixel_y, flags, parameters):
        if event != cv2.EVENT_LBUTTONDOWN:
            return

        if not parameters["accept_clicks"]:
            return

        for index, position in enumerate(parameters["cup_positions"]):
            cup_pixel_x, cup_pixel_y = table_to_pixel(
                position,
                canvas_height,
                PIXELS_PER_MM
            )

            pixel_distance = np.hypot(
                pixel_x - cup_pixel_x,
                pixel_y - cup_pixel_y
            )

            if pixel_distance <= clickable_cup_radius:
                parameters["clicked_index"] = index
                return

    cv2.namedWindow(WINDOW_NAME)
    cv2.setMouseCallback(WINDOW_NAME, handle_mouse, browser_state)

    print(
        "Controls: left/right arrows cycle layouts, click a cup to remove it, "
        "R resets, Q quits."
    )
    print(
        "Planner heuristic weight:",
        HIGH_LEVEL_HEURISTIC_WEIGHT,
        "(use 1.0 for exact shortest-path mode)"
    )
    print("Layout:", layout_names[current_layout_index])

    running = True

    while running:
        layout_name = layout_names[current_layout_index]
        clickable_positions = tuple(active_positions)
        all_cup_positions = tuple(active_positions + parked_positions)
        browser_state["cup_positions"] = clickable_positions

        frame = draw_layout(
            cup_positions=all_cup_positions,
            workspace=gantry_workspace,
            cup=cup
        )
        cv2.imshow(WINDOW_NAME, frame)

        key = cv2.waitKeyEx(30)

        if key == 27 or key == ord("q"):
            break

        if key in LEFT_ARROW_KEYS or key == ord("a"):
            current_layout_index = (
                current_layout_index - 1
            ) % len(layout_names)
            active_positions = list(
                place_layout(layout_names[current_layout_index], anchor)
            )
            parked_positions = []
            gantry_position = anchor
            browser_state["clicked_index"] = None
            print("Layout:", layout_names[current_layout_index])
            continue

        if key in RIGHT_ARROW_KEYS or key == ord("d"):
            current_layout_index = (
                current_layout_index + 1
            ) % len(layout_names)
            active_positions = list(
                place_layout(layout_names[current_layout_index], anchor)
            )
            parked_positions = []
            gantry_position = anchor
            browser_state["clicked_index"] = None
            print("Layout:", layout_names[current_layout_index])
            continue

        if key == ord("r") or key == ord("R"):
            active_positions = list(place_layout(layout_name, anchor))
            parked_positions = []
            gantry_position = anchor
            browser_state["clicked_index"] = None
            print("Reset layout:", layout_name)
            continue

        clicked_index = browser_state["clicked_index"]

        if clicked_index is None:
            continue

        if clicked_index >= len(active_positions):
            browser_state["clicked_index"] = None
            continue

        browser_state["clicked_index"] = None
        browser_state["accept_clicks"] = False

        selected_frame = draw_layout(
            cup_positions=all_cup_positions,
            workspace=gantry_workspace,
            cup=cup,
            selected_index=clicked_index
        )
        cv2.imshow(WINDOW_NAME, selected_frame)
        cv2.waitKey(1)

        print(
            f"Planning {layout_name} cup {clicked_index} removal..."
        )

        try:
            result = plan_selected_cup(
                cup_positions=all_cup_positions,
                scored_index=clicked_index,
                removed_count=len(parked_positions),
                gantry_start=gantry_position
            )
        except ValueError as error:
            print("Planning setup failed:", error)
            result = None

        if result is None:
            print(
                f"No rearrangement plan found for "
                f"{layout_name} cup {clicked_index}."
            )
        else:
            paths, total_cost, parking_target = result
            print(f"Cup movements: {len(paths)}")
            print(f"Total distance: {total_cost:.2f} mm")

            running = animate_plan(
                paths=paths,
                initial_cup_positions=all_cup_positions,
                workspace=gantry_workspace,
                cup=cup
            )

            if running:
                active_positions.pop(clicked_index)
                parked_positions.append(parking_target)

                if paths:
                    gantry_position = paths[-1][-1]

                print(
                    f"Remaining cups: {len(active_positions)}; "
                    f"parked cups: {len(parked_positions)}"
                )

        browser_state["accept_clicks"] = True

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
