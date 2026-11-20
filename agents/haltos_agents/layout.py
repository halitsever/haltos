"""Grid geometry, kept free of Qt so it is tested everywhere."""

Rect = tuple[int, int, int, int]


def grouped(groups: list[str], cols: int) -> list[Rect]:
    """(col, row, 1, 1) per tile, filled row by row, each group starting on a fresh row."""
    rects: list[Rect] = []
    col, row = 0, -1
    for i, group in enumerate(groups):
        if i == 0 or group != groups[i - 1] or col == cols:
            col, row = 0, row + 1
        rects.append((col, row, 1, 1))
        col += 1
    return rects


def sections(groups: list[str], cols: int) -> list[tuple[str, int, int]]:
    """(group, count, first row) per group, in order."""
    rects = grouped(groups, cols)
    found: list[tuple[str, int, int]] = []
    for group, rect in zip(groups, rects):
        if found and found[-1][0] == group:
            found[-1] = (group, found[-1][1] + 1, found[-1][2])
        else:
            found.append((group, 1, rect[1]))
    return found


def neighbour(rects: list[Rect], here: int, direction: str) -> int:
    """The tile above or below `here`, nearest edge first and then nearest centre; `here` at the edge."""
    col, row, w, h = rects[here]
    centre = col + w / 2

    def offset(r: Rect) -> float:
        return abs(r[0] + r[2] / 2 - centre)

    if direction == "down":
        found = [(r[1], offset(r), i) for i, r in enumerate(rects) if r[1] >= row + h]
    else:
        found = [(-(r[1] + r[3]), offset(r), i) for i, r in enumerate(rects) if r[1] + r[3] <= row]
    return min(found)[2] if found else here
