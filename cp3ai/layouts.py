# layouts.py all about cup coordinates and positions


r"""
      (0, table.length / 2)                                                              (table.width, table.length / 2)
        ----------------------------------------------------------------------------------
        |                                                                                |
        |                                                                                |
        |                                                                                |
        |                                       .------.                                 |
        |                                      /        \                                |
        |                                     |    9     |                               |
        |                                      \        /                                |
        |                                       '------'                                 |
        |                                 .------.    .------.                           |
        |                                /        \  /        \                          |
        |                               |    7     ||    8     |                         |
        |                                \        /  \        /                          |
        |                                 '------'    '------'                           |
        |                           .------.    .------.    .------.                     |
        |                          /        \  /        \  /        \                    |
        |                         |    4     ||    5     ||    6     |                   |
        |                          \        /  \        /  \        /                    |
        |                           '------'    '------'    '------'                     |
        |                     .------.    .------.    .------.    .------.               |
        |                    /        \  /        \  /        \  /        \              |
        |                   |    0     ||    1     ||    2     ||    3     |             |
        |                    \        /  \        /  \        /  \        /              |
        |                     '------'    '------'    '------'    '------'               |
        |                                                                                |
        |                                                                                |
        |                                                                                |
        |                                                                                |
        ----------------------------------------------------------------------------------
      (0, 0)                                                                            (table.width, 0)

"""

"""
I think the gantry's restpoint or home base should be at cup 5 so it can move and grab another cup as quickly as
possible if a shot is made. ArrangementPosition coordinates will be with respect to cup 5 (lef/down negative, right/up poisitve)
"""

from dataclasses import dataclass
from config import TableDimensions, CupDimensions, cup
import math

@dataclass(frozen=True)
class ArrangementPosition:
    dx: float
    dy: float

def hex_positionify(horizontal, diagonal, cup_diameter):  # right = +horizontal, left = -horizonatal, upright = +diagonal, downleft = -diagonal
    dx = (cup_diameter * horizontal) + (cup_diameter * diagonal) / 2
    dy = (cup_diameter / 2 * diagonal) * math.sqrt(3)

    result = ArrangementPosition(dx=dx, dy=dy)
    return result

def make_hex_layout(hex_coordinates, cup_diameter):

    hex_layout = []

    for coordinates in hex_coordinates:
        horizontal = coordinates[0]
        diagonal = coordinates[1]
        hex_position = hex_positionify(horizontal=horizontal, diagonal=diagonal, cup_diameter=cup_diameter)
        hex_layout.append(hex_position)
    return tuple(hex_layout)


def make_cartesian_layout(cartesian_coordinates, cup_diameter):
    """Convert coordinates measured in cup diameters into layout offsets."""

    cartesian_layout = []

    for x_units, y_units in cartesian_coordinates:
        cartesian_layout.append(
            ArrangementPosition(
                dx=x_units * cup_diameter,
                dy=y_units * cup_diameter
            )
        )

    return tuple(cartesian_layout)



hex_layouts = {
    "triangle_10": (
        (-1, -1), #cup0
        (0, -1),  #cup1
        (1, -1),  #cup2
        (2, -1),  #cup3
        (-1, 0),  #cup4
        (0 , 0),  #cup5
        (1, 0),   #cup6
        (-1, 1),  #cup7
        (0, 1),   #cup8
        (-1, 2),  #cup9
    ),

    "honeycomb": (
        (0, -1),  #cup1
        (1, -1),  #cup2
        (-1, 0),  #cup4
        (0 , 0),  #cup5
        (1, 0),   #cup6
        (-1, 1),  #cup7
        (0, 1),   #cup8
    ),

    "five": (
        (0, -1),  #cup1
        (1, -1),  #cup2
        (0 , 0),  #cup5
        (-1, 1),  #cup7
        (0, 1),   #cup8
    ),

    "triangle_6": (
        (-0.5, -1),
        (0.5, -1),
        (1.5, -1),
        (-0.5, 0),
        (0.5, 0),
        (-0.5, 1)
    ),

    "trapezoid_5": (
        (-1, 0), #cup0
        (0, 0),  #cup1
        (1, 0),  #cup2
        (-1, 1), #cup3
        (0, 1),  #cup4
    ),

    "kidney_5": (
        (0, 0),   #cup0
        (1, 0),   #cup1
        (-1, 1),  #cup2
        (0, 1),   #cup3
        (-1, 2),  #cup4
    ),

    "diamond_4": (
        (1, -1), #cup0
        (0, 0),  #cup1
        (1, 0),  #cup2
        (0, 1),  #cup3
    ),

    "rhombus_4": (
        (0, 0), #cup0
        (1, 0), #cup1
        (0, 1), #cup2
        (1, 1), #cup3
    ),

    "triangle_3": (
        (0, 0), #cup0
        (1, 0), #cup1
        (0, 1), #cup2
    ),

    "cliffhanger_10": (
        (-2, 0), #cup0
        (-1, 0), #cup1
        (0, 0),  #cup2
        (-2, 1), #cup3
        (-2, 2), #cup4
        (1, 0),  #cup5
        (2, 0),  #cup6
        (3, 0),  #cup7
        (2, 1),  #cup8
        (1, 2),  #cup9
    ),

        "cut_eye_9": (
        (-1, -1), #cup0
        (0, -1),  #cup1
        (1, -1),  #cup2
        (2, -1),  #cup3
        (-1, 0),  #cup4
        (0, 0),   #cup5
        (1, 0),   #cup6
        (-1, 1),  #cup7
        (0, 1),   #cup8
    ),

    "wall_7": (
        (-1, -1), #cup0
        (0, -1),  #cup1
        (1, -1),  #cup2
        (2, -1),  #cup3
        (-1, 0),  #cup4
        (0, 0),   #cup5
        (1, 0),   #cup6
    ),
}

tri_pack_height = math.sqrt(3) / 2 #vertical distance when you have a triangle packing

cartesian_layouts = {
    "marching_8": (
        (-0.5, -1.5), #cup0
        (0.5, -1.5),  #cup1
        (-0.5, -0.5), #cup2
        (0.5, -0.5),  #cup3
        (-0.5, 0.5),  #cup4
        (0.5, 0.5),   #cup5
        (-0.5, 1.5),  #cup6
        (0.5, 1.5),   #cup7
    ),

    "triangle_plus_one_7": (
        (-1, 0),                       #cup0
        (0, 0),                        #cup1
        (1, 0),                        #cup2
        (-0.5, tri_pack_height),   #cup3
        (0.5, tri_pack_height),    #cup4
        (0, 2 * tri_pack_height),  #cup5
        (0, 2 * tri_pack_height + 1), #cup6
    ),

    "marching_6": (
        (-0.5, -1), #cup0
        (0.5, -1),  #cup1
        (-0.5, 0),  #cup2
        (0.5, 0),   #cup3
        (-0.5, 1),  #cup4
        (0.5, 1),   #cup5
    ),

    "zipper_6": (
        (-tri_pack_height / 2, -1),   #cup0
        (-tri_pack_height / 2, 0),    #cup1
        (-tri_pack_height / 2, 1),    #cup2
        (tri_pack_height / 2, -0.5),  #cup3
        (tri_pack_height / 2, 0.5),   #cup4
        (tri_pack_height / 2, 1.5),   #cup5
    ),

    "house_5": (
        (-0.5, 0),                       #cup0
        (0.5, 0),                        #cup1
        (-0.5, 1),                       #cup2
        (0.5, 1),                        #cup3
        (0, 1 + tri_pack_height),    #cup4
    ),

    "five_5": (
        (-0.5, -tri_pack_height), #cup0
        (0.5, -tri_pack_height),  #cup1
        (0, 0),                   #cup2
        (-0.5, tri_pack_height),  #cup3
        (0.5, tri_pack_height),   #cup4
    ),

    "staff_5": (
        (0, -2), #cup0
        (0, -1), #cup1
        (0, 0),  #cup2
        (0, 1),  #cup3
        (0, 2),  #cup4
    ),

    "two_one_one_one_5": (
        (-0.5, 0),                      #cup0
        (0.5, 0),                       #cup1
        (0, tri_pack_height),       #cup2
        (0, tri_pack_height + 1),   #cup3
        (0, tri_pack_height + 2),   #cup4
    ),

    "crosshair_5": (
        (0, 0),  #cup0
        (-1, 0), #cup1
        (1, 0),  #cup2
        (0, -1), #cup3
        (0, 1),  #cup4
    ),

    "square_4": (
        (-0.5, -0.5), #cup0
        (0.5, -0.5),  #cup1
        (-0.5, 0.5),  #cup2
        (0.5, 0.5),   #cup3
    ),

    "two_one_one_4": (
        (-0.5, 0),                #cup0
        (0.5, 0),                 #cup1
        (0, tri_pack_height),     #cup2
        (0, tri_pack_height + 1), #cup3
    ),

    "traffic_light_3": (
        (0, -1), #cup0
        (0, 0),  #cup1
        (0, 1),  #cup2
    ),

    "thin_red_line_3": (
        (-1, 0), #cup0
        (0, 0),  #cup1
        (1, 0),  #cup2
    ),

    "vertical_2": (
        (0, -0.5), #cup0
        (0, 0.5),  #cup1
    ),

    "flatline_2": (
        (-0.5, 0), #cup0
        (0.5, 0),  #cup1
    ),

    "last_cup_1": (
        (0, 0), #cup0
    ),
}

rack_layouts: dict[str,tuple[ArrangementPosition, ...]] = {}

for layout_name, coordinates in hex_layouts.items():
    rack_layout = make_hex_layout(hex_coordinates=coordinates, cup_diameter=cup.rim_diameter)
    rack_layouts[layout_name] = rack_layout

for layout_name, coordinates in cartesian_layouts.items():
    rack_layout = make_cartesian_layout(cartesian_coordinates=coordinates, cup_diameter=cup.rim_diameter)
    rack_layouts[layout_name] = rack_layout

#make sure a layout makes sense
def validate_layout(positions, cup_diameter):

    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):

            x_displacement = positions[i].dx - positions[j].dx
            y_displacement = positions[i].dy - positions[j].dy
            distance = math.sqrt(x_displacement**2 + y_displacement**2)

            if (distance + 1e-6 < cup_diameter):
                return False

    return True

def get_layout(layout_name):
    #input = string like "triangle_6"
    #output = tuple of ArrangementPosition objects
    #invalid name raises ValueError

    if layout_name in rack_layouts:
        return rack_layouts[layout_name]

    raise ValueError(f"Undefined Layout :( no layout with name {layout_name}")



def main():
    for layout_name, coordinates in hex_layouts.items():
        rack_layout = make_hex_layout(hex_coordinates=coordinates, cup_diameter=cup.rim_diameter)
        rack_layouts[layout_name] = rack_layout


    layout = get_layout("triangle_6")
    print(len(layout))
    print(validate_layout(layout, cup.rim_diameter))

if __name__ == "__main__":
    main()
