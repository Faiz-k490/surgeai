from typing import Dict

import cv2
import numpy as np


def detect_demo_colors(frame) -> Dict[str, bool]:
    # HSV masks are tuned for hackathon props, not clinical imagery.
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    red1 = cv2.inRange(hsv, np.array([0, 120, 70]), np.array([10, 255, 255]))
    red2 = cv2.inRange(hsv, np.array([170, 120, 70]), np.array([180, 255, 255]))
    red_mask = cv2.bitwise_or(red1, red2)

    blue_mask = cv2.inRange(hsv, np.array([95, 120, 70]), np.array([130, 255, 255]))
    green_mask = cv2.inRange(hsv, np.array([35, 80, 70]), np.array([85, 255, 255]))

    return {
        "red_present": int(cv2.countNonZero(red_mask)) > 1500,
        "blue_present": int(cv2.countNonZero(blue_mask)) > 1200,
        "green_present": int(cv2.countNonZero(green_mask)) > 1200,
    }
