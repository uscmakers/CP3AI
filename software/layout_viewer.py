"""Interactive cup formation viewer with back-aligned racks and two-sided parking.

Click an active cup to simulate a made shot. This viewer demonstrates parking;
it does not yet run the A* movement planner or drive hardware.
"""
import math
import cv2
import numpy as np
from config import cup, gantry_workspace
from layouts import rack_layouts, validate_layout

WINDOW = 'Cup Pong - Back Rack and Side Parking'
SCALE = 0.55
MARGIN = 45
BACK_CLEARANCE_MM = 40  # gap between the back edge and the outer cup rim
SIDE_CLEARANCE_MM = 0    # parked cup rims touch the side boundary


def place_at_back(layout_name):
    offsets = rack_layouts[layout_name]
    top = max(p.dy for p in offsets)
    mid_x = (min(p.dx for p in offsets) + max(p.dx for p in offsets)) / 2
    backmost_center_y = gantry_workspace.length - cup.rim_diameter / 2 - BACK_CLEARANCE_MM
    return [(gantry_workspace.width / 2 + p.dx - mid_x,
             backmost_center_y + p.dy - top) for p in offsets]


def parking_spots(side):
    radius = cup.rim_diameter / 2
    x = radius + SIDE_CLEARANCE_MM if side == 'left' else gantry_workspace.width - radius - SIDE_CLEARANCE_MM
    return [(x, radius + SIDE_CLEARANCE_MM + i * cup.rim_diameter)
            for i in range(int((gantry_workspace.length - 2 * (radius + SIDE_CLEARANCE_MM)) // cup.rim_diameter) + 1)]


def pick_parking_target(source, occupied, active):
    """Choose nearest free valid parking spot on EITHER side.

    This is a simple distance heuristic, not a collision-free A* path.
    """
    candidates = []
    for side in ('left', 'right'):
        for spot in parking_spots(side):
            if all(math.dist(spot, other) >= cup.rim_diameter - 1e-6
                   for other in occupied + active if other != source):
                candidates.append((math.dist(source, spot), side, spot))
    if not candidates:
        return None
    _, side, target = min(candidates)
    return side, target


def to_pixel(position, canvas_height):
    x, y = position
    return (round(MARGIN + x * SCALE), round(canvas_height - MARGIN - y * SCALE))


def draw(name, active, parked):
    width = round(gantry_workspace.width * SCALE + 2 * MARGIN)
    height = round(gantry_workspace.length * SCALE + 2 * MARGIN)
    canvas = np.full((height, width, 3), (245, 245, 245), dtype=np.uint8)
    cv2.rectangle(canvas, to_pixel((0, gantry_workspace.length), height),
                  to_pixel((gantry_workspace.width, 0), height), (110, 165, 105), -1)
    cv2.rectangle(canvas, to_pixel((0, gantry_workspace.length), height),
                  to_pixel((gantry_workspace.width, 0), height), (255, 255, 255), 2)
    cv2.putText(canvas, 'BACK', (width // 2 - 30, 25), cv2.FONT_HERSHEY_SIMPLEX, .65, (25, 25, 25), 2)
    cv2.putText(canvas, name.replace('_', ' ').title(), (8, height - 18),
                cv2.FONT_HERSHEY_SIMPLEX, .5, (30, 30, 30), 1)
    cv2.putText(canvas, 'Click cup: park | A/D: layout | R: reset | Q: quit',
                (8, height - 2), cv2.FONT_HERSHEY_SIMPLEX, .36, (40, 40, 40), 1)
    radius = round(cup.rim_diameter / 2 * SCALE)
    for index, pos in enumerate(active):
        center = to_pixel(pos, height)
        cv2.circle(canvas, center, radius, (60, 75, 210), -1)
        cv2.circle(canvas, center, radius, (255, 255, 255), 2)
        cv2.putText(canvas, str(index + 1), (center[0] - 7, center[1] + 6),
                    cv2.FONT_HERSHEY_SIMPLEX, .5, (255, 255, 255), 2)
    for side, pos in parked:
        center = to_pixel(pos, height)
        cv2.circle(canvas, center, radius, (135, 135, 135), -1)
        cv2.circle(canvas, center, radius, (255, 255, 255), 2)
    return canvas


def main():
    names = list(rack_layouts)
    for name in names:
        assert validate_layout(rack_layouts[name]), f'Overlapping cups in {name}'
    index = 0
    active = place_at_back(names[index])
    parked = []
    state = {'clicked': None, 'active': active}
    height = round(gantry_workspace.length * SCALE + 2 * MARGIN)

    def mouse(event, x, y, flags, userdata):
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        for i, pos in enumerate(state['active']):
            px, py = to_pixel(pos, height)
            if math.hypot(px - x, py - y) <= cup.rim_diameter / 2 * SCALE:
                state['clicked'] = i
                break

    cv2.namedWindow(WINDOW)
    cv2.setMouseCallback(WINDOW, mouse)
    print('Click a live cup to park it on the nearer AVAILABLE side. A/D cycle, R resets, Q quits.')
    while True:
        cv2.imshow(WINDOW, draw(names[index], active, parked))
        key = cv2.waitKeyEx(30)
        if key in (27, ord('q'), ord('Q')):
            break
        if key in (ord('d'), ord('D'), 83, 63235, 65363, 2555904):
            index = (index + 1) % len(names)
        elif key in (ord('a'), ord('A'), 81, 63234, 65361, 2424832):
            index = (index - 1) % len(names)
        elif key in (ord('r'), ord('R')):
            pass
        else:
            if state['clicked'] is not None:
                source = active[state['clicked']]
                result = pick_parking_target(source, [p for _, p in parked], active)
                if result:
                    side, target = result
                    print(f'Cup at {source} -> {side} parking {target}')
                    active.pop(state['clicked'])
                    parked.append((side, target))
                else:
                    print('No free parking position found.')
                state['clicked'] = None
            continue
        active = place_at_back(names[index])
        parked = []
        state['active'] = active
        state['clicked'] = None
        print('Formation:', names[index])
    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
