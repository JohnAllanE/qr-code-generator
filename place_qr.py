"""
Render a QR code onto a full laser-bed canvas, placed relative to a workpiece.

Settings come from .env (see the comments there); any of them can be overridden
on the command line, e.g.:

    python place_qr.py --anchor top-left --offset 10,-5 --code-size 60

All coordinates are in mm with the origin at the BOTTOM-LEFT of the bed, +x right and
+y up. The conversion to image pixels (origin top-left, +y down) happens internally.
The PNG is saved with its DPI embedded so the laser software imports it at true size.
Output files go in output/ (OUTPUT_DIR). See README.md for examples and pictures.
"""

import argparse
import math
import os
from pathlib import Path

import qrcode
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from qrcode.constants import ERROR_CORRECT_H, ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q

MM_PER_INCH = 25.4

ERROR_CORRECTION = {
    "L": ERROR_CORRECT_L,
    "M": ERROR_CORRECT_M,
    "Q": ERROR_CORRECT_Q,
    "H": ERROR_CORRECT_H,
}

ANCHORS = ("top-left", "top-right", "bottom-left", "bottom-right", "center")

# Where each anchor sits on a rectangle, as fractions of (width, height) from its bottom-left.
ANCHOR_FRACTIONS = {
    "top-left": (0, 1),
    "top-right": (1, 1),
    "bottom-left": (0, 0),
    "bottom-right": (1, 0),
    "center": (0.5, 0.5),
}


def mm_to_px(mm, dpi):
    return mm / MM_PER_INCH * dpi


def parse_pair(text, name):
    """Parse "a,b" or "a" (-> a,a) into a float pair."""
    parts = [p.strip() for p in str(text).split(",")]
    try:
        if len(parts) == 1:
            return float(parts[0]), float(parts[0])
        if len(parts) == 2:
            return float(parts[0]), float(parts[1])
    except ValueError:
        pass
    raise ValueError(f"{name} must be a number or 'a,b', got {text!r}")


def parse_offset(text):
    if text is None or str(text).strip().lower() in ("", "none"):
        return 0.0, 0.0
    return parse_pair(text, "offset")


def parse_code_size(text):
    """Return the (W, H) bounding box, or None for "as large as possible"."""
    if str(text).strip() == "-1":
        return None
    return parse_pair(text, "code size")


def build_matrix(data, error_correction, border):
    """Return the QR module matrix (list of rows of bools), including the quiet zone."""
    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECTION[error_correction], border=border)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.get_matrix()


def align(outer_x, outer_y, outer_w, outer_h, w, h, anchor, offset):
    """
    Bottom-left corner (y-up) of a w x h rectangle whose `anchor` point lands on the
    same `anchor` point of the outer rectangle, then shifted by `offset`.
    """
    fx, fy = ANCHOR_FRACTIONS[anchor]
    x = outer_x + fx * (outer_w - w) + offset[0]
    y = outer_y + fy * (outer_h - h) + offset[1]
    return x, y


def place_part(canvas_w, canvas_h, part_w, part_h, part_anchor, part_offset):
    """Bottom-left corner of the part on the bed, in bed mm (y-up)."""
    return align(0, 0, canvas_w, canvas_h, part_w, part_h, part_anchor, part_offset)


def place_code(part_x, part_y, part_w, part_h, code_box, anchor, offset):
    """
    Work out where the code goes, in bed mm (y-up).

    Returns (x, y, side): the bottom-left corner and side length of the code's square,
    quiet zone included. The code's `anchor` point lands on the part's `anchor` point,
    then everything is shifted by `offset`.
    """
    box_w, box_h = (part_w, part_h) if code_box is None else code_box
    side = min(box_w, box_h)
    if side <= 0:
        raise ValueError("Code size must be positive (or -1 for as large as possible).")

    x, y = align(part_x, part_y, part_w, part_h, side, side, anchor, offset)
    return x, y, side


def dark_rects(matrix, x, y, side, shrink_pct=(0.0, 0.0), merge_x=False):
    """
    Yield (x0, y0, w, h) in bed mm (y-up, bottom-left corner) for the dark modules of
    `matrix` placed in the square (x, y, side).

    `shrink_pct` = (x %, y %) shrinks every module about its own centre, separately in
    each direction, to compensate for the laser burning wider than drawn (dark "bleeding"
    into the white gaps). Raster lasers mostly bleed along X, their fast travel direction.

    `merge_x` joins each row's run of adjacent dark modules into one rectangle, so the
    X shrink only applies at the run's two ends, where black meets white.
    """
    module = side / len(matrix)
    inset_x = module * shrink_pct[0] / 200
    inset_y = module * shrink_pct[1] / 200
    h = module - 2 * inset_y
    top = y + side
    for row, cells in enumerate(matrix):
        ry = top - (row + 1) * module + inset_y
        col = 0
        while col < len(cells):
            if not cells[col]:
                col += 1
                continue
            start = col
            col += 1
            while merge_x and col < len(cells) and cells[col]:
                col += 1
            yield x + start * module + inset_x, ry, (col - start) * module - 2 * inset_x, h


def draw_qr(draw, matrix, x, y, side, to_px, fill, shrink_pct=(0.0, 0.0), merge_x=False):
    """
    Draw the dark modules of `matrix` into the square (x, y, side) given in bed mm.

    `to_px` maps a bed point (mm, y-up) to image pixels (y-down). Each edge is rounded
    on its own so the overall code size stays exact; modules differ by <= 1 px.
    """
    for rx, ry, w, h in dark_rects(matrix, x, y, side, shrink_pct, merge_x):
        px0, py0 = to_px(rx, ry + h)
        px1, py1 = to_px(rx + w, ry)
        draw.rectangle((round(px0), round(py0), round(px1) - 1, round(py1) - 1), fill=fill)


def render_canvas(matrix, x, y, side, canvas_w, canvas_h, dpi, shrink_pct=(0.0, 0.0), merge_x=False):
    """The laser file: white bed, black modules. Mode "1" keeps a 300 DPI bed small."""
    img = Image.new("1", (round(mm_to_px(canvas_w, dpi)), round(mm_to_px(canvas_h, dpi))), 1)

    def to_px(bx, by):
        return mm_to_px(bx, dpi), mm_to_px(canvas_h - by, dpi)

    draw_qr(ImageDraw.Draw(img), matrix, x, y, side, to_px, fill=0, shrink_pct=shrink_pct, merge_x=merge_x)
    return img


def write_pdf(matrix, x, y, side, canvas_w, canvas_h, path, shrink_pct=(0.0, 0.0), merge_x=False):
    """
    The laser file as a vector PDF whose page is exactly the bed size.

    PDF units are points (1/72 in) with the origin at the bottom-left and +y up, the same
    convention as the bed, so no flip is needed. Each dark module (or row run, with
    `merge_x`) is its own filled rectangle.
    """
    pt = 72 / MM_PER_INCH
    rects = [f"{rx * pt:.4f} {ry * pt:.4f} {w * pt:.4f} {h * pt:.4f} re"
             for rx, ry, w, h in dark_rects(matrix, x, y, side, shrink_pct, merge_x)]
    content = ("0 g\n" + "\n".join(rects) + "\nf\n").encode()

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {canvas_w * pt:.4f} {canvas_h * pt:.4f}] "
        f"/Contents 4 0 R /Resources << >> >>".encode(),
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"endstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    Path(path).write_bytes(out)


def _arrow(draw, start, end, color, width=3, head=12):
    draw.line((start, end), fill=color, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    left = (end[0] - head * math.cos(angle - 0.45), end[1] - head * math.sin(angle - 0.45))
    right = (end[0] - head * math.cos(angle + 0.45), end[1] - head * math.sin(angle + 0.45))
    draw.polygon((end, left, right), fill=color)


def _dot(draw, center, color, r=7):
    draw.ellipse((center[0] - r, center[1] - r, center[0] + r, center[1] + r), fill=color, outline="white", width=2)


def render_preview(matrix, x, y, side, part, anchor, offset, canvas_w, canvas_h,
                   region=None, px_per_mm=4.0, title=None):
    """
    A colour picture for checking placement (not for the laser).

    Shows the bed, the part (tan), the code with its quiet zone outlined, the part's
    anchor point (red) and, if there is an offset, an arrow to where it moved (blue).
    `region` = (x0, y0, x1, y1) in bed mm crops the view; default is the whole bed.
    """
    part_x, part_y, part_w, part_h = part
    x0, y0, x1, y1 = region or (0, 0, canvas_w, canvas_h)
    img = Image.new("RGB", (round((x1 - x0) * px_per_mm), round((y1 - y0) * px_per_mm)), (200, 200, 200))
    draw = ImageDraw.Draw(img)

    def to_px(bx, by):
        return (bx - x0) * px_per_mm, (y1 - by) * px_per_mm

    def rect(bx0, by0, bx1, by1, **kwargs):
        (a, b), (c, d) = to_px(bx0, by1), to_px(bx1, by0)
        draw.rectangle((round(a), round(b), round(c), round(d)), **kwargs)

    rect(0, 0, canvas_w, canvas_h, fill=(232, 232, 232), outline=(120, 120, 120), width=2)
    rect(part_x, part_y, part_x + part_w, part_y + part_h, fill=(236, 212, 168), outline=(140, 100, 50), width=3)
    rect(x, y, x + side, y + side, fill="white", outline=(150, 150, 150), width=1)
    draw_qr(draw, matrix, x, y, side, to_px, fill="black")

    fx, fy = ANCHOR_FRACTIONS[anchor]
    anchor_pt = to_px(part_x + fx * part_w, part_y + fy * part_h)
    if offset != (0, 0):
        moved_pt = to_px(part_x + fx * part_w + offset[0], part_y + fy * part_h + offset[1])
        _arrow(draw, anchor_pt, moved_pt, (30, 90, 220))
        _dot(draw, moved_pt, (30, 90, 220))
    _dot(draw, anchor_pt, (220, 40, 40))

    # Axis gizmo in the bottom-left corner: +x right, +y up.
    font = ImageFont.load_default(size=max(12, img.height // 30))
    gx, gy, length = 20, img.height - 20, max(40, img.height // 10)
    _arrow(draw, (gx, gy), (gx + length, gy), (60, 60, 60))
    _arrow(draw, (gx, gy), (gx, gy - length), (60, 60, 60))
    draw.text((gx + length + 6, gy), "+x", fill=(60, 60, 60), font=font, anchor="lm")
    draw.text((gx, gy - length - 6), "+y", fill=(60, 60, 60), font=font, anchor="mb")

    if title:
        draw.text((12, 10), title, fill=(20, 20, 20), font=font)
    return img


def main():
    project_dir = Path(__file__).resolve().parent
    load_dotenv(project_dir / ".env", override=True)
    env = os.getenv

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default=env("TARGET_URL"))
    parser.add_argument("--canvas-width", type=float, default=float(env("CANVAS_WIDTH_MM", 914.4)))
    parser.add_argument("--canvas-height", type=float, default=float(env("CANVAS_HEIGHT_MM", 609.6)))
    parser.add_argument("--dpi", type=int, default=int(env("DPI", 300)))
    parser.add_argument("--part-width", type=float, default=float(env("PART_WIDTH_MM", 200)))
    parser.add_argument("--part-height", type=float, default=float(env("PART_HEIGHT_MM", 120)))
    parser.add_argument("--part-anchor", choices=ANCHORS, default=env("PART_ANCHOR", "top-left"),
                        help="bed corner the part is aligned to")
    parser.add_argument("--part-offset", default=env("PART_OFFSET_MM", "0,0"), help='"dx,dy" from that corner, up is +')
    parser.add_argument("--code-size", default=env("CODE_SIZE_MM", "-1"), help='"W,H", "S" or -1')
    parser.add_argument("--anchor", choices=ANCHORS, default=env("ANCHOR", "center"))
    parser.add_argument("--offset", default=env("OFFSET_MM", "0,0"), help='"dx,dy", up is +')
    parser.add_argument("--border", type=int, default=int(env("QR_BORDER", 4)), help="quiet zone, modules")
    parser.add_argument("--bleed-shrink", default=env("BLEED_SHRINK_PERCENT", "0"),
                        help='"x,y" %% of the module to shrink each dark module by, about its centre; '
                             'one number = both')
    parser.add_argument("--merge-x", action=argparse.BooleanOptionalAction,
                        default=env("MERGE_X_RUNS", "true").strip().lower() in ("1", "true", "yes", "on"),
                        help="join each row's adjacent dark modules into one rectangle (X shrink at run ends only)")
    parser.add_argument("--ec", choices=ERROR_CORRECTION, default=env("QR_ERROR_CORRECTION", "M"))
    parser.add_argument("--out-dir", default=env("OUTPUT_DIR", "output"),
                        help="folder for the files below when given as relative paths")
    parser.add_argument("--out", default=env("OUTPUT_PATH", "laser-qr-code.png"))
    parser.add_argument("--pdf", default=env("PDF_PATH", "laser-qr-code.pdf"), help="vector PDF; blank = none")
    parser.add_argument("--preview", default=env("PREVIEW_PATH", ""), help="blank = no preview")
    args = parser.parse_args()

    if not args.url:
        parser.error("No URL: set TARGET_URL in .env or pass --url")
    try:
        bleed = parse_pair(args.bleed_shrink, "bleed shrink")
        code_box = parse_code_size(args.code_size)
        offset = parse_offset(args.offset)
        part_offset = parse_offset(args.part_offset)
    except ValueError as e:
        parser.error(str(e))
    if not all(0 <= v < 100 for v in bleed):
        parser.error("--bleed-shrink values must be from 0 up to (not including) 100")

    # Relative output paths go inside the output folder (itself relative to this script).
    out_dir = project_dir / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    args.out = out_dir / args.out
    args.pdf = out_dir / args.pdf if args.pdf else None
    args.preview = out_dir / args.preview if args.preview else None

    matrix = build_matrix(args.url, args.ec, args.border)
    part_x, part_y = place_part(args.canvas_width, args.canvas_height, args.part_width, args.part_height,
                                args.part_anchor, part_offset)
    if (part_x < 0 or part_y < 0
            or part_x + args.part_width > args.canvas_width or part_y + args.part_height > args.canvas_height):
        print("Warning: the part extends past the edge of the bed.")
    x, y, side = place_code(part_x, part_y, args.part_width, args.part_height, code_box, args.anchor, offset)

    if x < 0 or y < 0 or x + side > args.canvas_width or y + side > args.canvas_height:
        raise SystemExit(f"Error: code square ({x:.1f}, {y:.1f}) to ({x + side:.1f}, {y + side:.1f}) mm "
                         f"runs off the {args.canvas_width} x {args.canvas_height} mm canvas.")
    eps = 1e-6
    if (x < part_x - eps or y < part_y - eps
            or x + side > part_x + args.part_width + eps or y + side > part_y + args.part_height + eps):
        print("Warning: the code (with quiet zone) extends past the edge of the part.")

    img = render_canvas(matrix, x, y, side, args.canvas_width, args.canvas_height, args.dpi, bleed, args.merge_x)
    img.save(args.out, dpi=(args.dpi, args.dpi))

    module_mm = side / len(matrix)
    b = args.border * module_mm
    print(f"Saved {args.out}: {img.width} x {img.height} px @ {args.dpi} DPI "
          f"({args.canvas_width} x {args.canvas_height} mm)")
    print(f"Code square (incl. quiet zone): bottom-left ({x:.2f}, {y:.2f}) mm, {side:.2f} mm")
    print(f"Dark modules: bottom-left ({x + b:.2f}, {y + b:.2f}) mm, {side - 2 * b:.2f} mm, "
          f"module = {module_mm:.2f} mm ({mm_to_px(module_mm, args.dpi):.1f} px)")
    if any(bleed):
        w_mm, h_mm = (module_mm * (1 - v / 100) for v in bleed)
        if args.merge_x:
            print(f"Bleed shrink X {bleed[0]:g}%, Y {bleed[1]:g}%, X runs merged: each run of dark modules is "
                  f"{module_mm - w_mm:.3f} mm narrower than drawn and {h_mm:.3f} mm tall, "
                  f"gaps {module_mm - h_mm:.3f} mm between rows")
        else:
            print(f"Bleed shrink X {bleed[0]:g}%, Y {bleed[1]:g}%: dark modules {w_mm:.3f} wide x {h_mm:.3f} mm tall, "
                  f"gaps {module_mm - w_mm:.3f} mm between left/right neighbours, "
                  f"{module_mm - h_mm:.3f} mm between top/bottom")
    if mm_to_px(module_mm, args.dpi) < 3:
        print("Warning: modules are under 3 px; increase --dpi or the code size.")

    if args.pdf:
        write_pdf(matrix, x, y, side, args.canvas_width, args.canvas_height, args.pdf, bleed, args.merge_x)
        print(f"Saved {args.pdf}: vector, page {args.canvas_width} x {args.canvas_height} mm "
              f"(print at Actual size / 100%)")

    if args.preview:
        part = (part_x, part_y, args.part_width, args.part_height)
        preview = render_preview(matrix, x, y, side, part, args.anchor, offset,
                                 args.canvas_width, args.canvas_height, px_per_mm=2)
        preview.save(args.preview)
        print(f"Saved preview {args.preview}")


if __name__ == "__main__":
    main()
