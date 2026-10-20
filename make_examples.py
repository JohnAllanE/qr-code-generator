"""Regenerate the diagrams in docs/images/ used by README.md."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from place_qr import build_matrix, dark_rects, parse_code_size, parse_offset, place_code, place_part, render_preview
from test_pattern import bleed_test_matrix

OUT_DIR = Path(__file__).resolve().parent / "docs" / "images"

CANVAS_W, CANVAS_H = 914.4, 609.6
PART_W, PART_H = 200, 120
PART_OFFSET = (100, -80)  # from the bed's top-left corner
PART = (*place_part(CANVAS_W, CANVAS_H, PART_W, PART_H, "top-left", PART_OFFSET), PART_W, PART_H)
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

# ((x px, y px), merge X runs)
BLEED_PANELS = (((0, 0), False), ((2, 0), False), ((2, 0), True), ((2, 2), True))
MODULE_PX = 18  # module size the bleed diagrams are drawn at (1.524 mm at 300 DPI)


def bleed_diagram(matrix, n=10, cell=30, pad=20):
    """Close-up of the code's top-left n x n modules for each bleed panel, side by side."""
    sub = [row[:n] for row in matrix[:n]]
    font = ImageFont.load_default(size=18)
    panel = n * cell
    img = Image.new("RGB", (len(BLEED_PANELS) * (panel + pad) + pad, panel + 2 * pad + 30), "white")
    draw = ImageDraw.Draw(img)
    for i, (bleed_px, merge) in enumerate(BLEED_PANELS):
        left, top = pad + i * (panel + pad), pad + 30
        label = f"--bleed-px {bleed_px[0]},{bleed_px[1]}" + (" --merge-x" if merge else " --no-merge-x")
        draw.text((left, pad - 4), label, fill="black", font=font)
        for k in range(n + 1):  # module cell grid
            draw.line((left + k * cell, top, left + k * cell, top + panel), fill=(210, 210, 210))
            draw.line((left, top + k * cell, left + panel, top + k * cell), fill=(210, 210, 210))
        # Square of side n "units" (1 unit per module), y-up, mapped into this panel.
        for rx, ry, w, h in dark_rects(sub, 0, 0, n, [v / MODULE_PX for v in bleed_px], merge):
            x0, y0 = left + rx * cell, top + (n - ry - h) * cell
            draw.rectangle((round(x0), round(y0), round(x0 + w * cell) - 1, round(y0 + h * cell) - 1), fill="black")
    return img


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
                   px_per_mm=1, title="Bed 914.4 x 609.6 mm, origin (0,0) bottom-left; part: anchor=top-left, offset=100,-80"
                   ).save(OUT_DIR / "bed-overview.png")
    bleed_diagram(matrix_no_border).save(OUT_DIR / "bleed-shrink.png")
    test = bleed_test_matrix()
    bleed_diagram(test, n=len(test), cell=10).save(OUT_DIR / "bleed-test-pattern.png")
    print(f"Wrote diagrams to {OUT_DIR}")


if __name__ == "__main__":
    main()
