"""Spotlight grid geometry, kept free of Qt so it is tested everywhere."""

Rect = tuple[int, int, int, int]


def pack(n: int, sel: int, cols: int, big_rows: int) -> list[Rect]:
    """(col, row, w, h) per tile in order; each tile takes the first free block, row by row."""
    taken: set[tuple[int, int]] = set()
    rects = []
    for i in range(n):
        w, h = (min(2, cols), max(2, big_rows)) if i == sel else (1, 1)
        row = 0
        while True:
            col = next((c for c in range(cols - w + 1)
                        if not any((c + x, row + y) in taken for x in range(w) for y in range(h))), None)
            if col is not None:
                break
            row += 1
        taken.update((col + x, row + y) for x in range(w) for y in range(h))
        rects.append((col, row, w, h))
    return rects


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
