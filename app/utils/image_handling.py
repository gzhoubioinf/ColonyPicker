"""
Image processing utilities for colony plate analysis.
"""

import cv2
import numpy as np


def load_plate_image(image_path):
    """Load a plate image from disk. Returns a BGR NumPy array, or None on failure."""
    return cv2.imread(image_path)


def find_grid_params(img, num_rows=32, num_cols=48):
    """
    Detect grid geometry by finding cell contours and reconstructing the grid.

    Uses adaptive thresholding to isolate cell borders, then filters contours
    by expected cell size and aspect ratio. Falls back to uniform division if
    fewer than 25% of expected cells are detected.

    Returns
    -------
    grid_origin : (int, int)
        (x, y) pixel coordinates of the top-left cell corner.
    cell_size : (float, float)
        (cell_width, cell_height) in pixels.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 51, 2
    )

    contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    img_h, img_w = img.shape[:2]
    expected_cell_h = img_h / num_rows
    expected_cell_w = img_w / num_cols

    valid_cells = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if (0.5 * expected_cell_w < w < 1.5 * expected_cell_w) and \
           (0.5 * expected_cell_h < h < 1.5 * expected_cell_h) and \
           (0.7 < w / h < 1.3):
            valid_cells.append((x, y, w, h))

    if len(valid_cells) < (num_rows * num_cols * 0.25):
        return (0, 0), (img_w / num_cols, img_h / num_rows)

    grid_x = min(c[0] for c in valid_cells)
    grid_y = min(c[1] for c in valid_cells)
    grid_w = max(c[0] + c[2] for c in valid_cells) - grid_x
    grid_h = max(c[1] + c[3] for c in valid_cells) - grid_y

    return (grid_x, grid_y), (grid_w / num_cols, grid_h / num_rows)


def _locate_colony(cell_bgr):
    """
    Find the centre of the colony blob within a single cell crop.

    Uses a two-stage approach:
      1. Colour masking (colonies tend to be cream/white on pale media).
      2. Otsu threshold fallback if colour masking yields nothing useful.

    Returns (cx, cy) centre of the colony blob, or None if not found.
    """
    lo = np.array([90, 160, 30], dtype=np.uint8)
    hi = np.array([255, 255, 220], dtype=np.uint8)
    mask = cv2.inRange(cell_bgr, lo, hi)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    if contours:
        best = max(contours, key=cv2.contourArea)

    if best is None or cv2.contourArea(best) < 100:
        gray = cv2.cvtColor(cell_bgr, cv2.COLOR_BGR2GRAY)
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        raw, _ = cv2.findContours(otsu, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if raw:
            best = max(raw, key=cv2.contourArea)

    if best is None:
        return None

    x, y, w, h = cv2.boundingRect(best)
    return (x + w // 2, y + h // 2)


def extract_colony(img, row, col, grid_origin=None, cell_size=None,
                   num_rows=32, num_cols=48):
    """
    Extract and centre the colony at (row, col) from a plate image.

    Parameters
    ----------
    img : np.ndarray
        Full plate image in BGR.
    row, col : int
        0-based grid coordinates of the target colony.
    grid_origin : (int, int), optional
        Pre-computed (x, y) of the first cell.
    cell_size : (float, float), optional
        Pre-computed (width, height) of one cell.
    num_rows, num_cols : int
        Grid dimensions.

    Returns
    -------
    np.ndarray or None
        Cropped BGR image of the colony, or None if the crop is empty.
    """
    img_h, img_w = img.shape[:2]

    if grid_origin is None or cell_size is None:
        grid_origin, cell_size = find_grid_params(img, num_rows, num_cols)

    ox, oy = grid_origin
    cw, ch = cell_size

    margin = 2
    x0 = int(round(ox + col * cw)) + margin
    y0 = int(round(oy + row * ch)) + margin
    crop_w = int(round(cw)) - margin
    crop_h = int(round(ch)) - margin

    x0 = max(0, min(x0, img_w - crop_w))
    y0 = max(0, min(y0, img_h - crop_h))

    cell = img[y0: y0 + crop_h, x0: x0 + crop_w]
    if cell.size == 0:
        return None

    colony_centre = _locate_colony(cell)
    if colony_centre is None:
        return cell

    cx, cy = colony_centre
    dx = cx - crop_w // 2
    dy = cy - crop_h // 2

    new_x0 = max(0, min(x0 + dx, img_w - crop_w))
    new_y0 = max(0, min(y0 + dy, img_h - crop_h))

    return img[new_y0: new_y0 + crop_h, new_x0: new_x0 + crop_w]
