#moving the cups to get from one cup configuration to the next
#when a cup is removed, we put it on the right hand side of the table, starting at the corner and moving up each cup

from config import cup, table, gantry_workspace
from config import TableDimensions, CupDimensions

import math
import heapq
import itertools

from dataclasses import dataclass

@dataclass(frozen=True)
class TablePosition:
    x: float
    y: float

def distance_between(cup1: TablePosition, cup2: TablePosition):
    x_diff = cup2.x - cup1.x
    y_diff = cup2.y - cup1.y

    return math.hypot(x_diff, y_diff)


def distance_from_segment(position, segment_start, segment_end):
    segment_x = segment_end.x - segment_start.x
    segment_y = segment_end.y - segment_start.y
    segment_length_squared = segment_x**2 + segment_y**2

    if segment_length_squared == 0:
        return distance_between(position, segment_start)

    start_to_position_x = position.x - segment_start.x
    start_to_position_y = position.y - segment_start.y
    projection = (start_to_position_x * segment_x + start_to_position_y * segment_y) / segment_length_squared
    projection = max(0.0, min(1.0, projection))

    closest_position = TablePosition(x=segment_start.x + projection * segment_x, y=segment_start.y + projection * segment_y)

    return distance_between(position, closest_position)


def is_straight_path_clear(start, goal, obstacles, cup):
    for obstacle in obstacles:
        if (distance_from_segment(obstacle, start, goal) + 1e-6 < cup.rim_diameter):
            return False

    return True

#true (x,y) coordinate of where to put the cup we just removed (side parking)
def get_removed_cup_target(removed_count, table, cup, edge_clearance):
    cup_radius = cup.rim_diameter / 2
    removed_stack_x = table.width - cup_radius - edge_clearance
    removed_cup_target_y = edge_clearance + cup_radius + (removed_count * cup.rim_diameter)
    return TablePosition(x=removed_stack_x, y=removed_cup_target_y)

#checks whether a position is avaiable along the path from cup --> parking when removed
def is_position_valid(position, obstacles, workspace, cup, edge_clearance):
    #position = candidate location along the path of the removed cup --> parking
    #obstacles = all the center positions for the othe rcups

    #cup collision check
    minimum_distance_squared = (cup.rim_diameter - 1e-6) ** 2

    for obstacle_position in obstacles:
        x_difference = position.x - obstacle_position.x
        y_difference = position.y - obstacle_position.y
        distance_squared = x_difference**2 + y_difference**2

        if distance_squared < minimum_distance_squared:
            return False

    #table clearance check

    cup_radius = cup.rim_diameter / 2

    x_min = edge_clearance + cup_radius
    x_max = workspace.width - cup_radius - edge_clearance

    y_min = edge_clearance + cup_radius
    y_max = workspace.length - cup_radius - edge_clearance # will probbaly need to add more buffer space if we have two gantries but for now should be fine

    if not (position.x >= x_min and position.x <= x_max and position.y >= y_min and position.y <= y_max):
        return False

    return True

# return tuple of (TablePosition, cost) pairs for neighboring nodes
def get_neighbor_nodes(node, step_size):
    #node = current position
    #step_size = how fine of a grid search we want for A* algorithm (smaller = more fine)

    neighbors = []

    for i in range (-1, 2):
        dx = i * step_size
        for j in range (-1, 2):

            dy = j * step_size

            if (i == 0 and j == 0):
                continue # generates the node itselfso skip

            neighbor_node = TablePosition(
                x=node.x + dx,
                y=node.y + dy
            )

            if i == 0 or j == 0:
                step_cost = step_size
            else:
                step_cost = step_size * math.sqrt(2)

            node_cost_pair = (neighbor_node, step_cost)
            neighbors.append(node_cost_pair)

    return tuple(neighbors)


#prune neighbors to only include positions that are unobstructed
def get_valid_neighbors(node, step_size, obstacles, workspace, cup, edge_clearance):

    valid_neighbors = []

    neighbors = get_neighbor_nodes(node, step_size)

    for neighbor_cost_pair in neighbors:
        if is_position_valid(position=neighbor_cost_pair[0], obstacles=obstacles, workspace=workspace, cup=cup, edge_clearance=edge_clearance):
            valid_neighbors.append(neighbor_cost_pair)

    return tuple(valid_neighbors)

# heuristic is straight-line distance
def heuristic(node, goal):
    return distance_between(node, goal)

# A* algo to find path
def find_path(start, goal, obstacles, workspace, cup, edge_clearance, step_size):

    if not is_position_valid(position=goal, obstacles=obstacles, workspace=workspace, cup=cup, edge_clearance=edge_clearance):
        return None

    if is_straight_path_clear(start, goal, obstacles, cup):
        return (start, goal)

    path = []

    node_ID = 0

    open_list = []
    closed_list = set()

    g = 0.0
    f = g + heuristic(start, goal)

    heapq.heappush(open_list, (f, -g, node_ID, start))

    g_scores = {start: 0.0}
    predecessor = {start: None}

    while(len(open_list) > 0):
        f, neg_g, _, current = (heapq.heappop(open_list))
        g = -neg_g

        if current in closed_list:
            continue

        if current == goal:
            path_traceback_iterator = current

            while(path_traceback_iterator != None):
                path.append(path_traceback_iterator)
                path_traceback_iterator = predecessor[path_traceback_iterator]

            path.reverse()
            return tuple(path)

        neighbors = get_valid_neighbors(node=current, step_size=step_size, obstacles=obstacles, workspace=workspace, cup=cup, edge_clearance=edge_clearance)

        #handle the case that no exact path is found given the step size, if we're close enough to the goal node just add it to the neighbor list
        distance_to_goal = distance_between(current, goal)
        maximum_neighbor_distance = step_size * math.sqrt(2)

        if (distance_to_goal <= maximum_neighbor_distance and is_position_valid(position=goal, obstacles=obstacles, workspace=workspace, cup=cup, edge_clearance=edge_clearance)):
            neighbors = neighbors + ((goal, distance_to_goal),)

        closed_list.add(current)

        for neighbor_node, move_cost in neighbors:

            if neighbor_node in closed_list:
                continue

            neighbor_g = g_scores[current] + move_cost

            if neighbor_g < g_scores.get(neighbor_node, math.inf):
                predecessor[neighbor_node] = current
                g_scores[neighbor_node] = neighbor_g

                neighbor_h = heuristic(neighbor_node, goal)
                neighbor_f = neighbor_g + neighbor_h

                node_ID += 1

                heapq.heappush(open_list, (neighbor_f, -neighbor_g, node_ID, neighbor_node))

    return None


def path_cost(path):

    if path is None:
        return math.inf

    cost = 0.0

    if len(path) < 2: return 0.0

    for i in range (0, len(path) - 1):
        start = path[i]
        end = path [i + 1]
        segment_cost = distance_between(start, end)
        cost += segment_cost

    return cost

def evaluate_replacement_candidate(scored_position, candidate_position, cup_positions, parking_target, workspace, cup, edge_clearance, step_size):

    candidate_obstacles = tuple(position for position in cup_positions if position != candidate_position)

    candidate_to_parking_path = find_path(start=candidate_position, goal=parking_target, obstacles=candidate_obstacles, workspace=workspace, cup=cup, edge_clearance=edge_clearance, step_size=step_size)

    if candidate_to_parking_path is None:
        return None

    new_obstacles = [position for position in cup_positions if (position != candidate_position and position != scored_position)]
    new_obstacles.append(parking_target)
    new_obstacles = tuple(new_obstacles)

    scored_to_candidate_path = find_path(start=scored_position, goal=candidate_position, obstacles=new_obstacles, workspace=workspace, cup=cup, edge_clearance=edge_clearance, step_size=step_size)
    if scored_to_candidate_path is None:
        return None


    total_cost = path_cost(candidate_to_parking_path) + path_cost(scored_to_candidate_path)

    return (candidate_to_parking_path, scored_to_candidate_path, total_cost)


def plan_cup_removal(scored_position, cup_positions, parking_target, workspace, cup, edge_clearance, step_size):
    #try moving the scored cup to parking directly first

    scored_obstacles = tuple(position for position in cup_positions if position != scored_position)

    scored_to_parking_path = find_path(start=scored_position, goal=parking_target, obstacles=scored_obstacles, workspace=workspace, cup=cup, edge_clearance=edge_clearance, step_size=step_size)

    if scored_to_parking_path is not None:
        cost = path_cost(scored_to_parking_path)
        return ((scored_to_parking_path,), cost)

    #scored cup to parking location directly isn't possible, so we need a two-step procedure
    #should examine every other cup
    #should choose the one with the lowest total cost across both of the movement steps

    minimum_cost = math.inf
    optimal_paths = None

    for candidate_position in cup_positions:

        if candidate_position == scored_position: # we know this isn't valid from the first check
            continue

        candidate_evaluation_result = evaluate_replacement_candidate(scored_position=scored_position, candidate_position=candidate_position, cup_positions=cup_positions, parking_target=parking_target, workspace=workspace, cup=cup, edge_clearance=edge_clearance, step_size=step_size)

        # no two-path sequence possible for this replacement cup
        if candidate_evaluation_result is None:
            continue

        candidate_to_parking_path, scored_to_candidate_path, total_cost = (candidate_evaluation_result)

        if (total_cost < minimum_cost):
            optimal_paths = (candidate_to_parking_path, scored_to_candidate_path)
            minimum_cost = total_cost

    if optimal_paths is None: #cooked
        return None

    return (optimal_paths, minimum_cost)


#return a tuple (next_state, movement_path, movement_cost) for eveyr single cup movement from state
def get_state_transitions(state, destinations, parking_target, workspace, cup, edge_clearance, step_size):

    transitions = []

    available_destinations = destinations - state

    for source in state:

        if source == parking_target: #don't want to move parked cup back to the rack so skip it
            continue

        current_obstacles = state - {source}
        source_can_leave = bool(
            get_valid_neighbors(
                node=source,
                step_size=step_size,
                obstacles=current_obstacles,
                workspace=workspace,
                cup=cup,
                edge_clearance=edge_clearance
            )
        )

        for destination in available_destinations:

            if not is_position_valid(
                position=destination,
                obstacles=current_obstacles,
                workspace=workspace,
                cup=cup,
                edge_clearance=edge_clearance
            ):
                continue

            if is_straight_path_clear(
                start=source,
                goal=destination,
                obstacles=current_obstacles,
                cup=cup
            ):
                source_to_destination = (source, destination)
            elif not source_can_leave:
                continue
            else:
                source_to_destination = find_path(start=source, goal=destination, obstacles=current_obstacles, workspace=workspace, cup=cup, edge_clearance=edge_clearance, step_size=step_size)

            if source_to_destination is None: #no path to move this cup to this empty spot
                continue

            next_state = (state - {source}) | {destination}
            source_to_destination_cost = path_cost(source_to_destination)

            transition = (next_state, source_to_destination, source_to_destination_cost)
            transitions.append(transition)

    return tuple(transitions)


def find_rearrangement_plan(start_state, goal_state, destinations, parking_target, workspace, cup, edge_clearance, step_size, gantry_start=None, heuristic_weight=1.0):

    if heuristic_weight <= 0:
        raise ValueError("heuristic_weight must be greater than zero")

    movement_paths = []

    open_list = []
    best_cost = {} # dictionary map every (cup state, gantry position)
    predecessor = {} # search node --> (previous search node, path_used) pair
    transition_cache = {} # cup state --> possible cup movements
    state_ID = 0

    start_search_node = (start_state, gantry_start)

    best_cost[start_search_node] = 0
    predecessor[start_search_node] = None

    priority = heuristic_weight * (state_heuristic(start_state, goal_state) + gantry_heuristic(state=start_state, goal_state=goal_state, gantry_position=gantry_start, parking_target=parking_target))

    heapq.heappush(open_list, (priority, 0.0, state_ID, start_search_node))

    while (open_list):
        _, current_cost, _, current_search_node = heapq.heappop(open_list)

        current_state, current_gantry_position = current_search_node

        if current_cost > best_cost[current_search_node]:
            continue

        if current_state == goal_state:
            traceback_iterator = current_search_node

            while predecessor[traceback_iterator] is not None:

                previous_state, movement_path = predecessor[traceback_iterator]
                movement_paths.append(movement_path)
                traceback_iterator = previous_state

            movement_paths.reverse()

            return (tuple(movement_paths), current_cost)

        transitions = transition_cache.get(current_state)

        if transitions is None:
            transitions = get_state_transitions(state=current_state, destinations=destinations, parking_target=parking_target, workspace=workspace, cup=cup, edge_clearance=edge_clearance, step_size=step_size)
            transition_cache[current_state] = transitions

        for next_state, source_to_destination, source_to_destination_cost in transitions:
            next_source = source_to_destination[0]
            next_gantry_position = source_to_destination[-1]

            if current_gantry_position is None:
                gantry_reposition_cost = 0.0
            else:
                gantry_reposition_cost = distance_between(current_gantry_position, next_source)

            transition_cost = (gantry_reposition_cost + source_to_destination_cost)
            candidate_cost = current_cost + transition_cost
            next_search_node = (next_state, next_gantry_position)

            remaining_cost = (state_heuristic(next_state, goal_state) + gantry_heuristic(state=next_state, goal_state=goal_state, gantry_position=next_gantry_position, parking_target=parking_target))
            candidate_priority = candidate_cost + heuristic_weight * remaining_cost

            if candidate_cost < best_cost.get(next_search_node, math.inf):

                best_cost[next_search_node] = candidate_cost
                predecessor[next_search_node] = (current_search_node, source_to_destination)
                state_ID += 1

                heapq.heappush(open_list, (candidate_priority, candidate_cost, state_ID, next_search_node))


    return None


def gantry_heuristic(state, goal_state, gantry_position, parking_target):
    if state == goal_state or gantry_position is None:
        return 0.0

    movable_cups = tuple(position for position in state if position != parking_target)

    if not movable_cups:
        return 0.0

    return min(distance_between(gantry_position, position) for position in movable_cups)


def state_heuristic(state, goal_state):
    extra_positions = tuple(state - goal_state)
    missing_positions = tuple(goal_state - state)

    if len(extra_positions) == 0:
        return 0.0


    min_assignment_cost = math.inf

    permutations = itertools.permutations(missing_positions)

    for permutation in permutations:
        assignment_cost = 0
        for i in range (0, len(extra_positions)):
            cost = distance_between(extra_positions[i], permutation[i])
            assignment_cost += cost

        if assignment_cost < min_assignment_cost:
            min_assignment_cost = assignment_cost

    return min_assignment_cost


# generate the points in destinations that we can use to temporarily store cups while we shuffle the others around
def generate_buffers(rack_positions, parking_target, workspace, cup, edge_clearance, count, buffer_clearance):

    if count == 0:
        return ()

    cup_radius = cup.rim_diameter / 2

    x_min = edge_clearance + cup_radius
    x_max = workspace.width - edge_clearance - cup_radius

    y_min = edge_clearance + cup_radius
    y_max = workspace.length - edge_clearance - cup_radius


    dumb_candidates = []

    sample_spacing = cup_radius

    y = y_min

    while(y <= y_max):

        x = x_min

        while(x <= x_max):

            buffer = TablePosition(x=x, y=y)
            dumb_candidates.append(buffer)

            x += sample_spacing

        y += sample_spacing


    required_separation = cup.rim_diameter + buffer_clearance
    safe_candidates = []

    for candidate in dumb_candidates:

        good_candidate = True

        for rack_position in rack_positions:
            if distance_between(candidate, rack_position) < required_separation:
                good_candidate = False
                break

        if distance_between(candidate, parking_target) < required_separation:
                good_candidate = False

        if good_candidate:
            safe_candidates.append(candidate)


    rack_x_sum = 0
    rack_y_sum = 0

    for rack_position in rack_positions:
        rack_x_sum += rack_position.x
        rack_y_sum += rack_position.y

    cups_in_rack = len(rack_positions)

    rack_center_x = rack_x_sum / cups_in_rack
    rack_center_y = rack_y_sum / cups_in_rack

    rack_center = TablePosition(rack_center_x, rack_center_y)

    def distance_to_rack_center(candidate):
        return distance_between(candidate, rack_center)

    safe_candidates.sort(key=distance_to_rack_center)

    selected_buffers = []

    for candidate in safe_candidates:

        candidate_is_compatible = True

        for selected_buffer in selected_buffers:
            distance = distance_between(candidate,selected_buffer)

            if distance < required_separation:
                candidate_is_compatible = False
                break

        if candidate_is_compatible:
            selected_buffers.append(candidate)

        if len(selected_buffers) == count:
            return tuple(selected_buffers)
