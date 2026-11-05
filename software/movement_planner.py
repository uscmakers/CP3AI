
"""
Collision-aware cup motion planning.

Features:
- Five fixed parking slots per side
- Bottom-up parking with small gaps
- Parking occupancy tracking
- Collision-aware A* pathfinding
- Hardcoded triangle_10 side escapes
- Hardcoded triangle_10 middle-cup strategies
- Hardcoded triangle_6 middle-cup strategy
- Temporary blocker relocation and restoration

Coordinates are in millimeters.
Positive Y points toward the FRONT of the viewer.
"""

from dataclasses import dataclass
import heapq
import itertools
import math


@dataclass(frozen=True)
class TablePosition:
    x: float
    y: float


COLLISION_TOLERANCE = 1e-5

TRIANGLE_10_ESCAPE_DIRECTIONS = {
    4: "left",
    6: "right",
    7: "left",
    8: "right",
}

TRIANGLE_10_MIDDLE_RULES = {
    1: {
        "clearance_cups": (0,),
        "blocker": 0,
    },
    2: {
        "clearance_cups": (3,),
        "blocker": 3,
    },
}

# Triangle_10 cup 5 touches six cups, so clearing one side neighbor
# is not enough: it still cannot slide between the cups above and
# below it. Each exit clears the side neighbor and the upper
# diagonal neighbor, then cup 5 leaves diagonally upward.
# Blockers are listed in the order they are moved.
TRIANGLE_10_CUP_5_EXITS = {
    "right": {"blockers": (6, 8), "angle": math.radians(30)},
    "left": {"blockers": (4, 7), "angle": math.radians(150)},
}

# Formation positions: position 1 sits between positions 0 and 2
# against the back edge. Move either neighbor aside to free it.
TRIANGLE_6_MIDDLE_RULES = {
    1: (0, 2),
}


# ============================================================
# GEOMETRY
# ============================================================

def distance_between(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def path_cost(path):
    return sum(
        distance_between(a, b)
        for a, b in zip(path, path[1:])
    )


def distance_from_segment(p, a, b):
    vx = b.x - a.x
    vy = b.y - a.y

    length_squared = vx * vx + vy * vy

    if length_squared <= 1e-12:
        return distance_between(p, a)

    t = (
        (p.x - a.x) * vx
        + (p.y - a.y) * vy
    ) / length_squared

    t = max(0.0, min(1.0, t))

    closest = TablePosition(
        a.x + t * vx,
        a.y + t * vy
    )

    return distance_between(p, closest)


def is_position_valid(
    p,
    obstacles,
    workspace,
    cup,
    edge_clearance=0
):
    radius = cup.rim_diameter / 2 + edge_clearance

    inside = (
        radius - COLLISION_TOLERANCE
        <= p.x
        <= workspace.width - radius + COLLISION_TOLERANCE
        and
        radius - COLLISION_TOLERANCE
        <= p.y
        <= workspace.length - radius + COLLISION_TOLERANCE
    )

    if not inside:
        return False

    minimum_distance = (
        cup.rim_diameter - COLLISION_TOLERANCE
    )

    return all(
        distance_between(p, obstacle) >= minimum_distance
        for obstacle in obstacles
    )


def is_straight_path_clear(a, b, obstacles, cup):
    minimum_distance = (
        cup.rim_diameter - COLLISION_TOLERANCE
    )

    return all(
        distance_from_segment(obstacle, a, b)
        >= minimum_distance
        for obstacle in obstacles
    )


def validate_movement_path(
    path,
    obstacles,
    workspace,
    cup
):
    if not path:
        return False

    for position in path:
        if not is_position_valid(
            position, obstacles, workspace, cup
        ):
            return False

    for a, b in zip(path, path[1:]):
        if not is_straight_path_clear(
            a, b, obstacles, cup
        ):
            return False

    return True


# ============================================================
# A* PATHFINDING
# ============================================================

def find_path(
    start,
    goal,
    obstacles,
    workspace,
    cup,
    edge_clearance=0,
    step_size=15
):
    """
    Collision-aware A* with:
    - Eight-connected grid
    - Actual start and goal positions
    - Visibility connections
    - Additional nodes around obstacles

    Returns a tuple of positions or None.
    """

    if step_size <= 0:
        raise ValueError("step_size must be positive")

    if not is_position_valid(
        start, obstacles, workspace, cup, edge_clearance
    ):
        return None

    if not is_position_valid(
        goal, obstacles, workspace, cup, edge_clearance
    ):
        return None

    if distance_between(start, goal) < 1e-7:
        return (start,)

    if is_straight_path_clear(start, goal, obstacles, cup):
        return (start, goal)

    radius = cup.rim_diameter / 2 + edge_clearance

    resolution = min(
        float(step_size),
        max(3.0, cup.rim_diameter / 12)
    )

    min_x = radius
    max_x = workspace.width - radius
    min_y = radius
    max_y = workspace.length - radius

    nx = int(math.ceil((max_x - min_x) / resolution))
    ny = int(math.ceil((max_y - min_y) / resolution))

    nodes = {}
    grid_nodes = {}

    for i in range(nx + 1):
        x = min(min_x + i * resolution, max_x)

        for j in range(ny + 1):
            y = min(min_y + j * resolution, max_y)

            position = TablePosition(x, y)

            if is_position_valid(
                position,
                obstacles,
                workspace,
                cup,
                edge_clearance
            ):
                key = (i, j)
                nodes[key] = position
                grid_nodes[key] = position

    boundary_keys = []

    boundary_radius = (
        cup.rim_diameter
        + max(0.5, resolution * 0.15)
    )

    for obstacle_index, obstacle in enumerate(obstacles):
        for angle_index in range(48):
            angle = 2 * math.pi * angle_index / 48

            candidate = TablePosition(
                obstacle.x + boundary_radius * math.cos(angle),
                obstacle.y + boundary_radius * math.sin(angle)
            )

            if not is_position_valid(
                candidate,
                obstacles,
                workspace,
                cup,
                edge_clearance
            ):
                continue

            key = ("boundary", obstacle_index, angle_index)
            nodes[key] = candidate
            boundary_keys.append(key)

    # Rays out of start and goal. A cup packed against its
    # neighbors can only leave (or re-enter) along an exact
    # tangent direction, a multiple of 30 degrees in the
    # formations, which grid nodes rarely line up with.
    for special_index, special in enumerate((start, goal)):
        for angle_index in range(36):
            angle = 2 * math.pi * angle_index / 36

            for multiplier in (0.5, 1.0):
                candidate = TablePosition(
                    special.x
                    + multiplier * cup.rim_diameter * math.cos(angle),
                    special.y
                    + multiplier * cup.rim_diameter * math.sin(angle)
                )

                if not is_position_valid(
                    candidate,
                    obstacles,
                    workspace,
                    cup,
                    edge_clearance
                ):
                    continue

                if not is_straight_path_clear(
                    special, candidate, obstacles, cup
                ):
                    continue

                key = ("ray", special_index, angle_index, multiplier)
                nodes[key] = candidate
                boundary_keys.append(key)

    nodes["start"] = start
    nodes["goal"] = goal

    graph = {key: [] for key in nodes}

    def connect(a_key, b_key):
        if a_key == b_key:
            return

        a = nodes[a_key]
        b = nodes[b_key]

        if not is_straight_path_clear(a, b, obstacles, cup):
            return

        cost = distance_between(a, b)

        graph[a_key].append((b_key, cost))
        graph[b_key].append((a_key, cost))

    directions = (
        (1, 0),
        (0, 1),
        (1, 1),
        (-1, 1),
    )

    for i, j in grid_nodes:
        for di, dj in directions:
            neighbor = (i + di, j + dj)

            if neighbor in grid_nodes:
                connect((i, j), neighbor)

    # Connect boundary nodes to nearby grid nodes.
    for boundary_key in boundary_keys:
        position = nodes[boundary_key]

        nearby = []

        for grid_key, grid_position in grid_nodes.items():
            distance = distance_between(
                position, grid_position
            )

            if distance <= resolution * 2.5:
                nearby.append((distance, grid_key))

        nearby.sort()

        for _, grid_key in nearby[:12]:
            connect(boundary_key, grid_key)

    # Connect nearby boundary nodes.
    for i, key_a in enumerate(boundary_keys):
        a = nodes[key_a]

        for key_b in boundary_keys[i + 1:]:
            b = nodes[key_b]

            if distance_between(a, b) <= resolution * 4:
                connect(key_a, key_b)

    # Connect actual start and goal to visible nodes.
    for special in ("start", "goal"):
        position = nodes[special]

        for grid_key, grid_position in grid_nodes.items():
            if is_straight_path_clear(
                position, grid_position, obstacles, cup
            ):
                connect(special, grid_key)

        for boundary_key in boundary_keys:
            if is_straight_path_clear(
                position, nodes[boundary_key], obstacles, cup
            ):
                connect(special, boundary_key)

    counter = itertools.count()

    queue = [
        (
            distance_between(start, goal),
            next(counter),
            "start"
        )
    ]

    g_score = {"start": 0.0}
    parent = {}

    while queue:
        priority, _, current = heapq.heappop(queue)

        expected = (
            g_score[current]
            + distance_between(nodes[current], goal)
        )

        if priority > expected + 1e-7:
            continue

        if current == "goal":
            keys = [current]

            while keys[-1] in parent:
                keys.append(parent[keys[-1]])

            keys.reverse()

            path = tuple(nodes[key] for key in keys)

            if validate_movement_path(
                path, obstacles, workspace, cup
            ):
                return path

            return None

        for neighbor, edge_cost in graph[current]:
            candidate = g_score[current] + edge_cost

            if candidate < g_score.get(
                neighbor, math.inf
            ) - 1e-7:
                g_score[neighbor] = candidate
                parent[neighbor] = current

                heuristic = distance_between(
                    nodes[neighbor], goal
                )

                heapq.heappush(
                    queue,
                    (
                        candidate + heuristic,
                        next(counter),
                        neighbor
                    )
                )

    return None


# ============================================================
# FIXED PARKING SLOTS
# ============================================================

def fixed_parking_slots(
    workspace,
    cup,
    clearance=15,
    slots_per_side=5,
    gap_mm=5
):
    """
    Five tightly packed parking slots per side.

    L1/R1 are closest to the back.
    L5/R5 are farthest from the back.
    """

    radius = cup.rim_diameter / 2

    left_x = radius + clearance
    right_x = workspace.width - radius - clearance

    start_y = radius + clearance
    spacing = cup.rim_diameter + gap_mm

    highest_y = (
        start_y + (slots_per_side - 1) * spacing
    )

    if highest_y + radius > workspace.length:
        raise ValueError(
            "Not enough table length for parking slots."
        )

    slots = {}

    for i in range(slots_per_side):
        y = start_y + i * spacing

        slots[f"L{i + 1}"] = TablePosition(left_x, y)
        slots[f"R{i + 1}"] = TablePosition(right_x, y)

    return slots


def new_parking_occupancy(slots):
    return {
        slot_id: None
        for slot_id in slots
    }


def parking_targets(
    side,
    workspace,
    cup,
    clearance=15
):
    slots = fixed_parking_slots(
        workspace, cup, clearance
    )

    prefix = "L" if side == "left" else "R"

    for i in range(1, 6):
        yield slots[f"{prefix}{i}"]


# ============================================================
# PARKING SELECTION
# ============================================================

def choose_fixed_parking(
    source,
    obstacles,
    gantry_position,
    workspace,
    cup,
    slots,
    occupancy,
    step_size=15,
    preferred_side=None
):
    """
    Find lowest-cost reachable parking slot.

    Returns:
        (cost, slot_id, target, path)
        or None.
    """

    candidates = []

    for slot_id, target in slots.items():
        if occupancy[slot_id] is not None:
            continue

        if not is_position_valid(
            target, obstacles, workspace, cup
        ):
            continue

        path = find_path(
            source,
            target,
            obstacles,
            workspace,
            cup,
            step_size=step_size
        )

        if path is None:
            continue

        cost = (
            distance_between(gantry_position, source)
            + path_cost(path)
        )

        preference = 0

        if preferred_side is not None:
            desired = (
                "L" if preferred_side == "left" else "R"
            )

            if not slot_id.startswith(desired):
                preference = 1

        candidates.append(
            (cost, preference, slot_id, target, path)
        )

    if not candidates:
        return None

    cost, _, slot_id, target, path = min(
        candidates,
        key=lambda item: (item[0], item[1])
    )

    return cost, slot_id, target, path


def choose_parking_path(
    source,
    obstacles,
    gantry_position,
    workspace,
    cup,
    clearance=15,
    step_size=25
):
    """Legacy-compatible wrapper."""

    slots = fixed_parking_slots(
        workspace, cup, clearance
    )

    occupancy = new_parking_occupancy(slots)

    result = choose_fixed_parking(
        source,
        obstacles,
        gantry_position,
        workspace,
        cup,
        slots,
        occupancy,
        step_size
    )

    if result is None:
        return None

    cost, slot_id, target, path = result

    side = (
        "left" if slot_id.startswith("L") else "right"
    )

    return cost, side, target, path


# ============================================================
# INTERIOR DETECTION
# ============================================================

def is_surrounded_interior(source, active, cup):
    """Determine whether nearby cups surround a cup."""

    neighbors = [
        position
        for position in active
        if position != source
        and distance_between(
            source, position
        ) <= cup.rim_diameter * 1.15
    ]

    if len(neighbors) < 3:
        return False

    angles = sorted(
        math.atan2(
            position.y - source.y,
            position.x - source.x
        ) % (2 * math.pi)
        for position in neighbors
    )

    gaps = [
        angles[i + 1] - angles[i]
        for i in range(len(angles) - 1)
    ]

    gaps.append(
        angles[0] + 2 * math.pi - angles[-1]
    )

    return max(gaps) < math.pi - 1e-5


# ============================================================
# TEMPORARY BUFFER GENERATION
# ============================================================

def generate_temporary_buffers(
    blocker,
    occupied,
    workspace,
    cup,
    slots,
    step_size=15
):
    """
    Generate candidate temporary positions near a blocker.

    Avoid active cups, parked cups, and all fixed slots.
    """

    buffers = []

    radii = (
        cup.rim_diameter * 1.15,
        cup.rim_diameter * 1.5,
        cup.rim_diameter * 2.0,
        cup.rim_diameter * 2.5,
        cup.rim_diameter * 3.0,
    )

    for radius in radii:
        for k in range(48):
            angle = 2 * math.pi * k / 48

            candidate = TablePosition(
                blocker.x + radius * math.cos(angle),
                blocker.y + radius * math.sin(angle)
            )

            if not is_position_valid(
                candidate,
                occupied,
                workspace,
                cup
            ):
                continue

            if any(
                distance_between(candidate, slot)
                < cup.rim_diameter - COLLISION_TOLERANCE
                for slot in slots.values()
            ):
                continue

            buffers.append(candidate)

    buffers.sort(
        key=lambda position: distance_between(
            blocker, position
        )
    )

    return buffers


# ============================================================
# SPECIFIC BLOCKER RELOCATION
# ============================================================

def plan_specific_blocker_clearance(
    selected_id,
    blocker_id,
    active,
    parked,
    gantry_position,
    workspace,
    cup,
    slots,
    occupancy,
    step_size=15,
    stop_at_first=False
):
    """
    Three-step plan:

    1. Move specific blocker to a temporary buffer.
    2. Park selected cup.
    3. Restore blocker.

    stop_at_first returns the first working buffer instead of
    searching every buffer for the cheapest plan.

    Returns:
        (steps, cost) or None.
    """

    if selected_id not in active:
        return None

    if blocker_id not in active:
        return None

    if selected_id == blocker_id:
        return None

    source = active[selected_id]
    blocker = active[blocker_id]

    others = [
        position
        for cup_id, position in active.items()
        if cup_id not in (selected_id, blocker_id)
    ]

    others += list(parked.values())

    occupied = [source, blocker] + others

    buffers = generate_temporary_buffers(
        blocker,
        occupied,
        workspace,
        cup,
        slots,
        step_size
    )

    best = None

    for buffer in buffers:
        # Step 1: Move blocker.
        first = find_path(
            blocker,
            buffer,
            [source] + others,
            workspace,
            cup,
            step_size=step_size
        )

        if first is None:
            continue

        # Step 2: Park selected cup.
        parking = choose_fixed_parking(
            source,
            [buffer] + others,
            buffer,
            workspace,
            cup,
            slots,
            occupancy,
            step_size
        )

        if parking is None:
            continue

        _, slot_id, target, second = parking

        # Step 3: Restore blocker.
        third = find_path(
            buffer,
            blocker,
            others + [target],
            workspace,
            cup,
            step_size=step_size
        )

        if third is None:
            continue

        cost = (
            distance_between(gantry_position, blocker)
            + path_cost(first)
            + distance_between(buffer, source)
            + path_cost(second)
            + distance_between(target, buffer)
            + path_cost(third)
        )

        steps = (
            (
                f"Temporarily move cup {blocker_id}",
                blocker_id,
                blocker,
                buffer,
                first,
                None
            ),
            (
                f"Park cup {selected_id} in {slot_id}",
                selected_id,
                source,
                target,
                second,
                slot_id
            ),
            (
                f"Restore cup {blocker_id}",
                blocker_id,
                buffer,
                blocker,
                third,
                None
            ),
        )

        if best is None or cost < best[1]:
            best = (steps, cost)

        if stop_at_first:
            break

    return best


# ============================================================
# MULTIPLE BLOCKER RELOCATION
# ============================================================

def plan_multi_blocker_clearance(
    selected_id,
    blocker_ids,
    exit_angle,
    active,
    parked,
    gantry_position,
    workspace,
    cup,
    slots,
    occupancy,
    step_size=15,
    buffers_per_blocker=4
):
    """
    Plan:

    1. Move each blocker, in order, to a temporary buffer.
    2. Park selected cup.
    3. Restore blockers in reverse order.

    Buffers overlapping the selected cup's exit corridor (from
    the cup along exit_angle) are skipped. Tries up to
    buffers_per_blocker reachable buffers per blocker and
    returns the first complete plan.

    Returns:
        (steps, cost) or None.
    """

    if selected_id not in active:
        return None

    if any(
        blocker_id not in active or blocker_id == selected_id
        for blocker_id in blocker_ids
    ):
        return None

    source = active[selected_id]

    still = [
        position
        for cup_id, position in active.items()
        if cup_id != selected_id
        and cup_id not in blocker_ids
    ]

    still += list(parked.values())

    corridor_end = TablePosition(
        source.x + 4 * cup.rim_diameter * math.cos(exit_angle),
        source.y + 4 * cup.rim_diameter * math.sin(exit_angle)
    )

    def clears_corridor(position):
        return distance_from_segment(
            position, source, corridor_end
        ) >= cup.rim_diameter - COLLISION_TOLERANCE

    def restore(moved, target):
        """Paths returning moved blockers, last moved first."""

        paths = []
        placed = still + [target]
        waiting = [buffer for _, buffer in moved]

        for index in range(len(moved) - 1, -1, -1):
            blocker_id, buffer = moved[index]
            waiting.pop()

            path = find_path(
                buffer,
                active[blocker_id],
                placed + waiting,
                workspace,
                cup,
                step_size=step_size
            )

            if path is None:
                return None

            paths.append((blocker_id, buffer, path))
            placed.append(active[blocker_id])

        return paths

    def search(index, moved, moves):
        """Depth-first search over buffers for each blocker."""

        buffers = [buffer for _, buffer in moved]

        if index == len(blocker_ids):
            parking = choose_fixed_parking(
                source,
                still + buffers,
                buffers[-1],
                workspace,
                cup,
                slots,
                occupancy,
                step_size
            )

            if parking is None:
                return None

            _, slot_id, target, path = parking

            restored = restore(moved, target)

            if restored is None:
                return None

            return moves, (slot_id, target, path), restored

        blocker_id = blocker_ids[index]
        blocker = active[blocker_id]

        remaining = [
            active[other_id]
            for other_id in blocker_ids[index + 1:]
        ]

        obstacles = still + buffers + remaining + [source]

        candidates = [
            buffer
            for buffer in generate_temporary_buffers(
                blocker,
                obstacles + [blocker],
                workspace,
                cup,
                slots,
                step_size
            )
            if clears_corridor(buffer)
        ]

        tried = 0

        for buffer in candidates:
            if tried >= buffers_per_blocker:
                break

            path = find_path(
                blocker,
                buffer,
                obstacles,
                workspace,
                cup,
                step_size=step_size
            )

            if path is None:
                continue

            tried += 1

            result = search(
                index + 1,
                moved + [(blocker_id, buffer)],
                moves + [(blocker_id, blocker, buffer, path)]
            )

            if result is not None:
                return result

        return None

    result = search(0, [], [])

    if result is None:
        return None

    moves, (slot_id, target, parking_path), restored = result

    steps = []
    cost = 0.0
    position = gantry_position

    for blocker_id, start, buffer, path in moves:
        cost += distance_between(position, start) + path_cost(path)
        position = buffer

        steps.append((
            f"Temporarily move cup {blocker_id}",
            blocker_id,
            start,
            buffer,
            path,
            None
        ))

    cost += (
        distance_between(position, source)
        + path_cost(parking_path)
    )
    position = target

    steps.append((
        f"Park cup {selected_id} in {slot_id}",
        selected_id,
        source,
        target,
        parking_path,
        slot_id
    ))

    for blocker_id, buffer, path in restored:
        cost += distance_between(position, buffer) + path_cost(path)
        position = active[blocker_id]

        steps.append((
            f"Restore cup {blocker_id}",
            blocker_id,
            buffer,
            active[blocker_id],
            path,
            None
        ))

    return tuple(steps), cost


# ============================================================
# TRIANGLE-10 CUP 5 STRATEGY
# ============================================================

def choose_triangle_10_cup_5_plan(
    active,
    parked,
    gantry_position,
    workspace,
    cup,
    slots,
    occupancy,
    step_size=15
):
    """
    Hardcoded strategy for the center cup of triangle_10.

    Exit right: temporarily move cups 6 and 8.
    Exit left: temporarily move cups 4 and 7.

    Cups already removed are skipped. The side needing the fewest
    temporary moves is tried first (right on a tie), so if cup 4
    or 6 is gone, cup 5 leaves toward that side.
    """

    selected_id = 5

    if selected_id not in active:
        return None

    exits = sorted(
        TRIANGLE_10_CUP_5_EXITS.items(),
        key=lambda item: (
            sum(
                blocker_id in active
                for blocker_id in item[1]["blockers"]
            ),
            item[0] != "right"
        )
    )

    for side, rule in exits:
        blocker_ids = tuple(
            blocker_id
            for blocker_id in rule["blockers"]
            if blocker_id in active
        )

        if not blocker_ids:
            print(f"Cup 5: {side} exit already clear.")

            obstacles = [
                position
                for cup_id, position in active.items()
                if cup_id != selected_id
            ]

            obstacles += list(parked.values())

            parking = choose_fixed_parking(
                active[selected_id],
                obstacles,
                gantry_position,
                workspace,
                cup,
                slots,
                occupancy,
                step_size=step_size
            )

            if parking is None:
                continue

            cost, slot_id, target, path = parking

            steps = (
                (
                    f"Park cup {selected_id} in {slot_id}",
                    selected_id,
                    active[selected_id],
                    target,
                    path,
                    slot_id
                ),
            )

            return steps, cost

        print(
            f"Cup 5: exiting {side}, temporarily relocating "
            + " and ".join(f"cup {b}" for b in blocker_ids)
            + "."
        )

        result = plan_multi_blocker_clearance(
            selected_id,
            blocker_ids,
            rule["angle"],
            active,
            parked,
            gantry_position,
            workspace,
            cup,
            slots,
            occupancy,
            step_size
        )

        if result is not None:
            return result

    return None


# ============================================================
# TRIANGLE-10 MIDDLE-CUP STRATEGY
# ============================================================

def choose_triangle_10_middle_plan(
    selected_id,
    active,
    parked,
    gantry_position,
    workspace,
    cup,
    slots,
    occupancy,
    step_size=15
):
    """
    Hardcoded strategy for triangle_10 cups 1, 2, 5.

    Cup 5:
        See choose_triangle_10_cup_5_plan.

    Cup 1:
        If 0 is removed, attempt direct parking.
        Otherwise temporarily move cup 0.

    Cup 2:
        If 3 is removed, attempt direct parking.
        Otherwise temporarily move cup 3.
    """

    if selected_id == 5:
        return choose_triangle_10_cup_5_plan(
            active,
            parked,
            gantry_position,
            workspace,
            cup,
            slots,
            occupancy,
            step_size
        )

    if selected_id not in TRIANGLE_10_MIDDLE_RULES:
        return None

    if selected_id not in active:
        return None

    rule = TRIANGLE_10_MIDDLE_RULES[selected_id]

    source = active[selected_id]

    clearance_cups = rule["clearance_cups"]
    blocker_id = rule["blocker"]

    clearance_available = any(
        neighbor_id not in active
        for neighbor_id in clearance_cups
    )

    # --------------------------------------------------------
    # Neighbor already removed: try direct parking
    # --------------------------------------------------------

    if clearance_available:
        print(
            f"Cup {selected_id}: "
            "neighboring clearance available."
        )

        obstacles = [
            position
            for cup_id, position in active.items()
            if cup_id != selected_id
        ]

        obstacles += list(parked.values())

        parking = choose_fixed_parking(
            source,
            obstacles,
            gantry_position,
            workspace,
            cup,
            slots,
            occupancy,
            step_size=step_size
        )

        if parking is None:
            print(
                "No collision-free direct path "
                "through available clearance."
            )
            return None

        cost, slot_id, target, path = parking

        steps = (
            (
                f"Park cup {selected_id} in {slot_id}",
                selected_id,
                source,
                target,
                path,
                slot_id
            ),
        )

        return steps, cost

    # --------------------------------------------------------
    # Required neighbor still active: move it temporarily
    # --------------------------------------------------------

    if blocker_id not in active:
        return None

    print(
        f"Cup {selected_id}: temporarily "
        f"relocating cup {blocker_id}."
    )

    # Searching every buffer for the cheapest plan takes minutes
    # and freezes the viewer; buffers are tried nearest first.
    return plan_specific_blocker_clearance(
        selected_id,
        blocker_id,
        active,
        parked,
        gantry_position,
        workspace,
        cup,
        slots,
        occupancy,
        step_size,
        stop_at_first=True
    )


# ============================================================
# TRIANGLE-6 MIDDLE-CUP STRATEGY
# ============================================================

def choose_triangle_6_middle_plan(
    selected_id,
    active,
    parked,
    gantry_position,
    workspace,
    cup,
    slots,
    occupancy,
    step_size=15,
    formation_index=None
):
    """
    Hardcoded strategy for the cup in triangle_6 position 1.

    If the cup in position 0 or 2 is already removed, attempt
    direct parking. Otherwise temporarily move the position-0
    cup, or the position-2 cup if that fails, using the first
    buffer that works.

    formation_index maps active cup IDs to formation positions.
    Omit it when cup IDs are the formation positions.
    """

    if selected_id not in active:
        return None

    if formation_index is None:
        formation_index = {cup_id: cup_id for cup_id in active}

    id_at = {
        index: cup_id
        for cup_id, index in formation_index.items()
        if cup_id in active
    }

    blocker_positions = TRIANGLE_6_MIDDLE_RULES.get(
        formation_index.get(selected_id)
    )

    if blocker_positions is None:
        return None

    blocker_ids = [
        id_at.get(index) for index in blocker_positions
    ]

    if any(
        blocker_id is None
        for blocker_id in blocker_ids
    ):
        print(
            f"Cup {selected_id}: "
            "neighboring clearance available."
        )

        obstacles = [
            position
            for cup_id, position in active.items()
            if cup_id != selected_id
        ]

        obstacles += list(parked.values())

        parking = choose_fixed_parking(
            active[selected_id],
            obstacles,
            gantry_position,
            workspace,
            cup,
            slots,
            occupancy,
            step_size=step_size
        )

        if parking is not None:
            cost, slot_id, target, path = parking

            steps = (
                (
                    f"Park cup {selected_id} in {slot_id}",
                    selected_id,
                    active[selected_id],
                    target,
                    path,
                    slot_id
                ),
            )

            return steps, cost

        print(
            "No direct path through available clearance."
        )

    for blocker_id in blocker_ids:
        if blocker_id is None:
            continue

        print(
            f"Cup {selected_id}: temporarily "
            f"relocating cup {blocker_id}."
        )

        result = plan_specific_blocker_clearance(
            selected_id,
            blocker_id,
            active,
            parked,
            gantry_position,
            workspace,
            cup,
            slots,
            occupancy,
            step_size,
            stop_at_first=True
        )

        if result is not None:
            return result

    return None


# ============================================================
# GENERAL TEMPORARY RELOCATION
# ============================================================

def plan_interior_temporary_clearance(
    selected_id,
    active,
    parked,
    gantry_position,
    workspace,
    cup,
    slots,
    occupancy,
    step_size=15
):
    """
    General three-step fallback.

    Available for any cup, not only interior cups.
    """

    if selected_id not in active:
        return None

    source = active[selected_id]

    blocker_ids = [
        blocker_id
        for blocker_id, position in active.items()
        if blocker_id != selected_id
        and distance_between(
            source, position
        ) <= cup.rim_diameter * 1.5
    ]

    blocker_ids.sort(
        key=lambda blocker_id: distance_between(
            source, active[blocker_id]
        )
    )

    best = None

    for blocker_id in blocker_ids:
        result = plan_specific_blocker_clearance(
            selected_id,
            blocker_id,
            active,
            parked,
            gantry_position,
            workspace,
            cup,
            slots,
            occupancy,
            step_size
        )

        if result is None:
            continue

        if best is None or result[1] < best[1]:
            best = result

    return best


# ============================================================
# LEGACY TEMPORARY CLEARANCE
# ============================================================

def plan_temporary_clearance(
    source,
    active,
    parked,
    gantry_position,
    workspace,
    cup,
    clearance=15,
    step_size=25
):
    """Legacy-compatible wrapper."""

    active_map = {
        i: position
        for i, position in enumerate(active)
    }

    selected_id = next(
        (
            i
            for i, position in active_map.items()
            if position == source
        ),
        None
    )

    if selected_id is None:
        return None

    slots = fixed_parking_slots(
        workspace, cup, clearance
    )

    occupancy = new_parking_occupancy(slots)

    for i, position in enumerate(parked):
        for slot_id, target in slots.items():
            if distance_between(position, target) < 1e-4:
                occupancy[slot_id] = f"parked_{i}"

    result = plan_interior_temporary_clearance(
        selected_id,
        active_map,
        {
            i: position
            for i, position in enumerate(parked)
        },
        gantry_position,
        workspace,
        cup,
        slots,
        occupancy,
        step_size
    )

    if result is None:
        return None

    steps, cost = result

    legacy_steps = tuple(
        (name, start, destination, path)
        for name, _, start, destination, path, _ in steps
    )

    return legacy_steps, cost


# ============================================================
# DIRECTIONAL ESCAPE COMPATIBILITY
# ============================================================

def find_directional_escape(
    start,
    goal,
    obstacles,
    workspace,
    cup,
    preferred_side=None,
    step_size=10
):
    return find_path(
        start,
        goal,
        obstacles,
        workspace,
        cup,
        step_size=step_size
    )


# ============================================================
# TRIANGLE-10 SIDE ESCAPE
# ============================================================

def choose_triangle_10_side_path(
    selected_id,
    source,
    obstacles,
    gantry_position,
    workspace,
    cup,
    slots,
    occupancy,
    step_size=15
):
    """
    Hardcoded outward escape:

    4 -> left
    6 -> right
    7 -> left
    8 -> right

    Then use A* to reach an available parking slot.
    """

    side = TRIANGLE_10_ESCAPE_DIRECTIONS.get(
        selected_id
    )

    if side is None:
        return None

    direction = -1 if side == "left" else 1

    escape_distances = [
        cup.rim_diameter * multiplier
        for multiplier in (
            0.5,
            0.75,
            1.0,
            1.25,
            1.5,
            1.75,
            2.0,
            2.5,
            3.0,
        )
    ]

    best = None

    for escape_distance in escape_distances:
        escape_point = TablePosition(
            source.x + direction * escape_distance,
            source.y
        )

        if not is_position_valid(
            escape_point,
            obstacles,
            workspace,
            cup
        ):
            continue

        if not is_straight_path_clear(
            source,
            escape_point,
            obstacles,
            cup
        ):
            continue

        for slot_id, target in slots.items():
            if side == "left" and not slot_id.startswith("L"):
                continue

            if side == "right" and not slot_id.startswith("R"):
                continue

            if occupancy[slot_id] is not None:
                continue

            if not is_position_valid(
                target,
                obstacles,
                workspace,
                cup
            ):
                continue

            remaining_path = find_path(
                escape_point,
                target,
                obstacles,
                workspace,
                cup,
                step_size=step_size
            )

            if remaining_path is None:
                continue

            full_path = (
                (source,)
                + tuple(remaining_path)
            )

            if not validate_movement_path(
                full_path,
                obstacles,
                workspace,
                cup
            ):
                continue

            cost = (
                distance_between(gantry_position, source)
                + path_cost(full_path)
            )

            candidate = (
                cost,
                slot_id,
                target,
                full_path
            )

            if best is None or cost < best[0]:
                best = candidate

    return best


# ============================================================
# FORMATION REARRANGEMENT
# ============================================================

def assign_targets(sources, targets):
    """
    Match cups to formation positions, minimizing total distance.

    sources: {cup_id: TablePosition}
    targets: {index: TablePosition}

    Returns {cup_id: index}. Brute force; formations are small.
    """

    if len(sources) != len(targets):
        raise ValueError(
            "Cup count does not match formation size."
        )

    cup_ids = sorted(sources)

    best = min(
        itertools.permutations(sorted(targets)),
        key=lambda order: sum(
            distance_between(sources[c], targets[t])
            for c, t in zip(cup_ids, order)
        )
    )

    return dict(zip(cup_ids, best))


def plan_rearrangement(
    active,
    targets,
    parked,
    workspace,
    cup,
    step_size=15
):
    """
    Move active cups into a new formation one at a time.

    active: {cup_id: TablePosition}
    targets: {index: TablePosition} of the new formation
    parked: {cup_id: TablePosition}, treated as obstacles

    Each round moves the closest cup whose target is free and
    reachable. If every remaining cup is stuck (for example two
    cups sitting on each other's targets), one is moved to a
    temporary spot clear of all targets, then the rounds resume.

    Returns:
        (steps, assignment) or None.
        steps use the viewer format
        (name, cup_id, start, destination, path, slot_id).
        assignment maps cup_id -> formation index.
    """

    assignment = assign_targets(active, targets)

    current = dict(active)
    parked_positions = list(parked.values())

    pending = [
        cup_id for cup_id in current
        if distance_between(
            current[cup_id], targets[assignment[cup_id]]
        ) > 1e-4
    ]

    steps = []
    temporary_moves = 0

    def obstacles_for(cup_id):
        return [
            position
            for other_id, position in current.items()
            if other_id != cup_id
        ] + parked_positions

    def move(cup_id, destination, path, name):
        steps.append((
            name,
            cup_id,
            current[cup_id],
            destination,
            path,
            None
        ))

        current[cup_id] = destination

    while pending:
        pending.sort(
            key=lambda cup_id: distance_between(
                current[cup_id], targets[assignment[cup_id]]
            )
        )

        moved = False

        for cup_id in pending:
            goal = targets[assignment[cup_id]]

            path = find_path(
                current[cup_id],
                goal,
                obstacles_for(cup_id),
                workspace,
                cup,
                step_size=step_size
            )

            if path is None:
                continue

            move(
                cup_id, goal, path,
                f"Rearrange cup {cup_id}"
            )

            pending.remove(cup_id)
            moved = True
            break

        if moved:
            continue

        # Deadlock: move one pending cup out of the way.
        if temporary_moves >= len(active):
            return None

        for cup_id in pending:
            obstacles = obstacles_for(cup_id)

            buffers = [
                buffer
                for buffer in generate_temporary_buffers(
                    current[cup_id],
                    obstacles,
                    workspace,
                    cup,
                    {},
                    step_size
                )
                if all(
                    distance_between(buffer, target)
                    >= cup.rim_diameter - COLLISION_TOLERANCE
                    for target in targets.values()
                )
            ]

            for buffer in buffers:
                path = find_path(
                    current[cup_id],
                    buffer,
                    obstacles,
                    workspace,
                    cup,
                    step_size=step_size
                )

                if path is not None:
                    break
            else:
                continue

            move(
                cup_id, buffer, path,
                f"Move cup {cup_id} aside"
            )

            temporary_moves += 1
            moved = True
            break

        if not moved:
            return None

    return tuple(steps), assignment


def aligned_formation_targets(
    new_positions,
    current_positions,
    active,
    parked,
    workspace,
    cup,
    match_tolerance=1.0
):
    """
    Candidate placements for a new formation, best first.

    The new formation stays horizontally centered on the table; it
    is never shifted left or right. Each candidate shifts it toward
    the front or back so one of its positions lands on a position
    of the current formation. Placements that reuse spots where
    cups already sit need fewer moves and avoid targets that
    half-overlap cups still waiting to move.

    new_positions: {index: TablePosition}, default placement,
        horizontally centered
    current_positions: {index: TablePosition}, current formation
    active: {cup_id: TablePosition}
    parked: {cup_id: TablePosition}, must stay clear

    Returns a list of {index: TablePosition}. The default
    placement is always included.
    """

    # Rounded shift -> exact shift. Rounding only removes
    # duplicates; exact shifts keep targets on the cups.
    shifts = {(0.0, 0.0): (0.0, 0.0)}

    for anchor in current_positions.values():
        for position in new_positions.values():
            if abs(anchor.x - position.x) > match_tolerance:
                continue

            dy = anchor.y - position.y

            shifts.setdefault((0.0, round(dy, 3)), (0.0, dy))

    parked_positions = list(parked.values())
    active_positions = list(active.values())

    scored = []

    for dx, dy in shifts.values():
        targets = {
            index: TablePosition(p.x + dx, p.y + dy)
            for index, p in new_positions.items()
        }

        if not all(
            is_position_valid(
                target, parked_positions, workspace, cup
            )
            for target in targets.values()
        ):
            continue

        in_place = sum(
            any(
                distance_between(target, position)
                <= match_tolerance
                for position in active_positions
            )
            for target in targets.values()
        )

        # Most cups already in place, then closest to the back.
        scored.append((
            -in_place,
            round(dy, 3),
            targets
        ))

    scored.sort(key=lambda item: item[:2])

    return [targets for *_, targets in scored]
