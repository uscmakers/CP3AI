import cv2
import numpy as np
from config import cup
from layouts import rack_layouts



def main():
    height = 700
    width = 700

    canvas = np.full((height, width, 3), 255, dtype=np.uint8)

    center = (width // 2, height //2)
    radius = int(cup.rim_diameter / 2)

    layout = rack_layouts["kidney_5"]

    anchor_x = width // 2
    anchor_y = height // 2

    for slot_id, position in enumerate(layout):
        pixel_x = int(center[0] + position.dx)
        pixel_y = int(center[1] - position.dy) #increase downward for some reason wth

        cv2.circle(canvas, (pixel_x, pixel_y), radius, (0, 0, 255), 2)
        cv2.putText(canvas, str(slot_id), (pixel_x - 8, pixel_y + 7), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

    cv2.imshow("layout viewer", canvas)
    cv2.waitKey(0)
    cv2.destroyAllWindows()



if __name__ == "__main__":
    main()
