"""
A small test pattern for dialling in --bleed-px, used in place of a QR code.

It's a square matrix of modules (rows of bools, True = dark), like build_matrix()
returns, so it goes through the same placement, bleed compensation and output code. Each
feature sits in its own 10 x 10 cell, with 4-module white gutters between cells, wider
than any gap inside a feature so the features don't run into each other:

    checkerboard 1x1    dots 1x1, 1 gap     vertical stripes 1 wide
    checkerboard 2x2    dots 2x2, 2 gap     vertical stripes 2 wide
    horiz. stripes 1    horiz. stripes 2    finder (as in a QR code)

The middle row repeats the top row at twice the scale. Stripes are the easiest to
measure: vertical ones give black and white widths across (X), horizontal ones top to
bottom (Y). Checkerboards show corner-to-corner bleed, and isolated dots show how a
lone module shrinks or swells. The finder is in the bottom-right, so it also marks
which way up the burn is.
"""

CELL = 10
GUTTER = 4
GRID = 3
SIZE = GRID * CELL + (GRID - 1) * GUTTER  # 38 modules


def checkerboard(block, size):
    return [[(r // block + c // block) % 2 == 0 for c in range(size)] for r in range(size)]


def dots(block, gap, count):
    """count x count dots of block x block modules, with `gap` white modules between."""
    pitch = block + gap
    size = count * pitch - gap
    return [[r % pitch < block and c % pitch < block for c in range(size)] for r in range(size)]


def vertical_stripes(width, count, height):
    pitch = 2 * width
    return [[c % pitch < width for c in range(count * pitch - width)] for _ in range(height)]


def horizontal_stripes(width, count, length):
    return [list(row) for row in zip(*vertical_stripes(width, count, length))]


def finder():
    """The 7 x 7 position marker from the corners of a QR code."""
    def dark(r, c):
        ring = max(abs(r - 3), abs(c - 3))
        return ring != 2
    return [[dark(r, c) for c in range(7)] for r in range(7)]


FEATURES = [
    [checkerboard(1, 9), dots(1, 1, 5), vertical_stripes(1, 5, 10)],
    [checkerboard(2, 10), dots(2, 2, 3), vertical_stripes(2, 3, 10)],
    [horizontal_stripes(1, 5, 10), horizontal_stripes(2, 3, 10), finder()],
]


def bleed_test_matrix():
    """The SIZE x SIZE test pattern; each feature is centred in its cell."""
    matrix = [[False] * SIZE for _ in range(SIZE)]
    for gr, row in enumerate(FEATURES):
        for gc, feature in enumerate(row):
            top = gr * (CELL + GUTTER) + (CELL - len(feature)) // 2
            left = gc * (CELL + GUTTER) + (CELL - len(feature[0])) // 2
            for r, cells in enumerate(feature):
                matrix[top + r][left:left + len(cells)] = cells
    return matrix
