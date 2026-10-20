"""
Lay out the bleed test pattern once per bleed setting, in a row, as one full-bed laser file.

The settings are the four from the README's test pattern diagram, left to right. The row
is centred vertically on --center-y, so a small piece of material can sit under it and be
moved between runs at different powers and speeds. Defaults give 18 px modules at 300 DPI
(1.524 mm), the same as a 50 mm QR code; see "Whole-pixel module sizes" in README.md.
Bleed values are in px at --dpi.

    python make_bleed_sheet.py
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

from make_examples import BLEED_PANELS
from place_qr import MM_PER_INCH, dark_rects, draw_qr, mm_to_px, px_to_mm, write_rects_pdf
from test_pattern import SIZE, bleed_test_matrix


def main():
    project_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--canvas-width", type=float, default=914.4)
    parser.add_argument("--canvas-height", type=float, default=609.6)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--module", type=float, default=1.524, help="module size, mm")
    parser.add_argument("--left", type=float, default=0, help="left edge of the first pattern, mm from the bed's left")
    parser.add_argument("--center-y", type=float, default=12 * MM_PER_INCH,
                        help="height of the row's centre line, mm from the bed's bottom")
    parser.add_argument("--gap", type=int, default=10, help="white modules between patterns")
    parser.add_argument("--out-dir", default="output")
    parser.add_argument("--out", default="bleed-sheet.png")
    parser.add_argument("--pdf", default="bleed-sheet.pdf")
    args = parser.parse_args()

    out_dir = project_dir / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    matrix = bleed_test_matrix()
    side = SIZE * args.module
    y = args.center_y - side / 2
    tiles = [(args.left + i * (SIZE + args.gap) * args.module, bleed_px, [px_to_mm(v, args.dpi) for v in bleed_px], merge)
             for i, (bleed_px, merge) in enumerate(BLEED_PANELS)]
    right = tiles[-1][0] + side
    if args.left < 0 or y < 0 or right > args.canvas_width or y + side > args.canvas_height:
        raise SystemExit("Error: the row runs off the bed.")

    write_rects_pdf([r for x, _, bleed, merge in tiles for r in dark_rects(matrix, x, y, side, bleed, merge)],
                    args.canvas_width, args.canvas_height, out_dir / args.pdf)

    img = Image.new("1", (round(mm_to_px(args.canvas_width, args.dpi)), round(mm_to_px(args.canvas_height, args.dpi))), 1)

    def to_px(bx, by):
        return mm_to_px(bx, args.dpi), mm_to_px(args.canvas_height - by, args.dpi)

    for x, _, bleed, merge in tiles:
        draw_qr(ImageDraw.Draw(img), matrix, x, y, side, to_px, fill=0, bleed_mm=bleed, merge_x=merge)
    img.save(out_dir / args.out, dpi=(args.dpi, args.dpi))

    print(f"Saved {out_dir / args.pdf} and {out_dir / args.out}")
    print(f"Module {args.module:g} mm ({mm_to_px(args.module, args.dpi):.1f} px), patterns {side:.3f} mm square")
    print(f"Row: x {args.left:.3f} to {right:.3f} mm, y {y:.3f} to {y + side:.3f} mm "
          f"(centre {args.center_y:.3f} mm from the bottom, {args.canvas_height - args.center_y:.3f} mm from the top)")
    for i, (x, bleed_px, _, merge) in enumerate(tiles, start=1):
        print(f"  {i}. x {x:7.3f} mm: --bleed-px {bleed_px[0]:g},{bleed_px[1]:g} {'--merge-x' if merge else '--no-merge-x'}")


if __name__ == "__main__":
    main()
