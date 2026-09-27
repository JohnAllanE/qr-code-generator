"""Regenerate the diagrams in docs/images/ used by PLACEMENT.md."""

from pathlib import Path

from place_qr import build_matrix, parse_code_size, parse_offset, place_code, render_preview

OUT_DIR = Path(__file__).resolve().parent / "docs" / "images"

CANVAS_W, CANVAS_H = 914.4, 609.6
PART = (100, 80, 200, 120)  # x, y, width, height
MARGIN = 25  # mm of bed shown around the part in close-up diagrams

# (file name, anchor, code size, offset)
EXAMPLES = [
    ("anchor-top-left", "top-left", "50", "0,0"),
    ("anchor-top-right", "top-right", "50", "0,0"),
    ("anchor-bottom-left", "bottom-left", "50", "0,0"),
    ("anchor-bottom-right", "bottom-right", "50", "0,0"),
    ("anchor-center", "center", "50", "0,0"),
    ("offset-top-left-right-down", "top-left", "50", "20,-15"),
    ("offset-center-right-up", "center", "50", "40,20"),
    ("offset-bottom-right-left-up", "bottom-right", "50", "-10,10"),
    ("size-max", "center", "-1", "0,0"),
    ("size-box", "top-left", "80,50", "0,0"),
    ("size-max-border-0", "center", "-1", "0,0"),
]


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    part_x, part_y, part_w, part_h = PART
    region = (part_x - MARGIN, part_y - MARGIN, part_x + part_w + MARGIN, part_y + part_h + MARGIN)
    matrix = build_matrix("https://example.com", "M", border=4)
    matrix_no_border = build_matrix("https://example.com", "M", border=0)

    for name, anchor, code_size, offset_text in EXAMPLES:
        offset = parse_offset(offset_text)
        x, y, side = place_code(*PART, parse_code_size(code_size), anchor, offset)
        m = matrix_no_border if name.endswith("border-0") else matrix
        title = f"anchor={anchor}  code size={code_size}  offset={offset_text}"
        render_preview(m, x, y, side, PART, anchor, offset, CANVAS_W, CANVAS_H,
                       region=region, px_per_mm=3, title=title).save(OUT_DIR / f"{name}.png")

    # Whole-bed overview showing where the part sits relative to the origin.
    x, y, side = place_code(*PART, parse_code_size("50"), "center", (0, 0))
    render_preview(matrix, x, y, side, PART, "center", (0, 0), CANVAS_W, CANVAS_H,
                   px_per_mm=1, title="Bed 914.4 x 609.6 mm, origin (0,0) bottom-left; part at (100, 80)"
                   ).save(OUT_DIR / "bed-overview.png")
    print(f"Wrote diagrams to {OUT_DIR}")


if __name__ == "__main__":
    main()
