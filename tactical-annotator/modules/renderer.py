import cv2
import numpy as np
from typing import List, Tuple

def draw_glowing_ring(frame: np.ndarray, center: Tuple[int, int], color: Tuple[int, int, int], radius: int = 25) -> np.ndarray:
    """
    Draw a glowing ring around a point.
    """
    glow_layer = np.zeros_like(frame, dtype=np.uint8)
    # Draw three concentric circles
    cv2.circle(glow_layer, center, radius + 10, color, 2)
    cv2.circle(glow_layer, center, radius + 5, color, 2)
    cv2.circle(glow_layer, center, radius, color, 2)
    # Apply Gaussian blur
    blurred = cv2.GaussianBlur(glow_layer, (21, 21), 0)
    # Add the glow to the frame
    return cv2.addWeighted(frame, 1.0, blurred, 0.85, 0)

def draw_connecting_line(frame: np.ndarray, p1: Tuple[int, int], p2: Tuple[int, int], color: Tuple[int, int, int], thickness: int = 2) -> np.ndarray:
    """
    Draw a semi-transparent line between two points.
    """
    overlay = frame.copy()
    cv2.line(overlay, p1, p2, color, thickness)
    return cv2.addWeighted(overlay, 0.75, frame, 0.25, 0)

def draw_hatched_zone(frame: np.ndarray, vertices: List[Tuple[int, int]], color: Tuple[int, int, int]) -> np.ndarray:
    """
    Draw a hatched (striped) triangle.
    """
    # Layer 1: filled triangle at low opacity
    overlay = frame.copy()
    pts = np.array(vertices, dtype=np.int32)
    cv2.fillPoly(overlay, [pts], color)
    frame = cv2.addWeighted(overlay, 0.15, frame, 0.85, 0)

    # Layer 2: hatching clipped to triangle
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [pts], 255)
    x, y, w, h = cv2.boundingRect(pts)
    hatch_layer = np.zeros_like(frame)
    # Draw diagonal lines at 45 degrees, spacing 8px
    # Iterate from -(w+h) to (w+h) to cover corners
    for i in range(-(w + h), w + h + 1, 8):
        # Line from (x + i, y) to (x + i + h, y + h)
        pt1 = (int(x + i), int(y))
        pt2 = (int(x + i + h), int(y + h))
        cv2.line(hatch_layer, pt1, pt2, color, 1)
    # Clip hatch_layer to mask
    hatch_layer[mask == 0] = 0
    # Add hatching layer
    return cv2.addWeighted(frame, 1.0, hatch_layer, 0.4, 0)

def draw_dashed_arrow(frame: np.ndarray, start: Tuple[int, int], end: Tuple[int, int], color: Tuple[int, int, int],
                     dash_len: int = 12, gap_len: int = 8) -> np.ndarray:
    """
    Draw a dashed arrow from start to end.
    """
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    dist = np.sqrt(dx*dx + dy*dy)
    if dist == 0:
        return frame
    ux = dx / dist
    uy = dy / dist

    # Draw dashed line
    for i in range(0, int(dist), dash_len + gap_len):
        # Start of dash
        x_start = int(x1 + ux * i)
        y_start = int(y1 + uy * i)
        # End of dash (ensure we don't exceed the segment)
        x_end = int(x1 + ux * min(i + dash_len, dist))
        y_end = int(y1 + uy * min(i + dash_len, dist))
        cv2.line(frame, (x_start, y_start), (x_end, y_end), color, 2)

    # Draw arrowhead at the end
    # Calculate points for the arrowhead polygon
    # We'll use cv2.arrowedLine for simplicity, but we need to draw it dashed?
    # Instead, we can draw a small filled triangle at the end.
    # For simplicity, we'll draw a solid arrowhead (as per spec: cv2.arrowedLine with tipLength=0.5)
    # But note: the spec says to draw arrowhead using cv2.arrowedLine after the dashed line.
    # We'll draw a short solid arrow at the end.
    # However, the spec says: draw arrowhead: cv2.arrowedLine(frame, (end[0] - int(ux*15), end[1] - int(uy*15)), end, color, 2, tipLength=0.5)
    # Let's do that.
    arrow_tip_length = 15
    arrow_start = (int(x2 - ux * arrow_tip_length), int(y2 - uy * arrow_tip_length))
    cv2.arrowedLine(frame, arrow_start, (int(x2), int(y2)), color, 2, tipLength=0.5)
    return frame

def draw_player_label(frame: np.ndarray, text: str, position: Tuple[int, int], color: Tuple[int, int, int]) -> np.ndarray:
    """
    Draw text with a black outline and colored fill.
    """
    # Black outline
    cv2.putText(frame, text, position, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
    # Colored text
    cv2.putText(frame, text, position, cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
    return frame