
def clamp_box(ymin: int, xmin: int, ymax: int, xmax: int) -> tuple[int, int, int, int]:
    """Ensure box coords are ordered and non-negative."""
    y1, y2 = sorted((max(0, ymin), max(0, ymax)))
    x1, x2 = sorted((max(0, xmin), max(0, xmax)))
    return y1, x1, y2, x2
