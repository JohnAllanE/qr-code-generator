# Placing a QR code on the laser bed

`place_qr.py` makes a full-bed image (914.4 × 609.6 mm, 36 × 24 in) with a QR code placed on your workpiece. Set everything in `.env`, or override any value on the command line:

```
python place_qr.py
python place_qr.py --anchor top-left --offset 10,-5 --code-size 60
```

It writes two files:

- **`laser-qr-code.png`**: the file for the laser. It's 1-bit black and white, with the DPI stored in the file so it imports at true size.
- **`laser-qr-preview.png`**: a small colour picture of the bed for checking placement. It isn't for the laser.

## Coordinates

All values are in **mm**. The origin `(0, 0)` is the **bottom-left corner of the bed**, **+x is right and +y is up**, as in maths class. The script handles the flip to image pixels, which count downward.

![Whole bed with the origin at bottom-left](docs/images/bed-overview.png)

## Settings

| `.env` key | CLI flag | Meaning |
|---|---|---|
| `CANVAS_WIDTH_MM`, `CANVAS_HEIGHT_MM` | `--canvas-width`, `--canvas-height` | Bed size. Default 914.4 × 609.6. |
| `PART_WIDTH_MM`, `PART_HEIGHT_MM` | `--part-width`, `--part-height` | Outer dimensions of the workpiece. |
| `PART_X_MM`, `PART_Y_MM` | `--part-x`, `--part-y` | Where the part's **bottom-left** corner sits on the bed. |
| `CODE_SIZE_MM` | `--code-size` | Box the code is shrunk into: `W,H`, or `S` for a square. The code stays square, so its side is `min(W, H)`. **`-1` makes it as large as the part allows.** |
| `ANCHOR` | `--anchor` | `top-left`, `top-right`, `bottom-left`, `bottom-right` or `center`. |
| `OFFSET_MM` | `--offset` | Shift `dx,dy` from the anchored position. Up is +. Blank or `0,0` means no shift. |
| `QR_BORDER` | `--border` | Quiet-zone width in modules (default 4). It's counted **inside** the code size. |
| `QR_ERROR_CORRECTION` | `--ec` | `L`, `M`, `Q` or `H`. |
| `DPI` | `--dpi` | Output resolution. Default 300. |

The script stops with an error if the code would run off the bed. It warns if the code would run past the edge of the part.

## How to read the diagrams

- **Tan rectangle:** the part.
- **White square with a grey outline:** the code, quiet zone included. This is the square that `CODE_SIZE_MM` and the anchor apply to.
- **Red dot:** the anchor point on the part.
- **Blue dot and arrow:** where the offset moved that point.

In every diagram the part is 200 × 120 mm at (100, 80).

## Anchors

The anchor names the corner of the code that lines up with the **same** corner of the part. For example, `top-left` puts the code's top-left corner on the part's top-left corner. `center` puts the code's centre on the part's centre.

| `top-left` | `top-right` |
|---|---|
| ![top-left](docs/images/anchor-top-left.png) | ![top-right](docs/images/anchor-top-right.png) |
| **`bottom-left`** | **`bottom-right`** |
| ![bottom-left](docs/images/anchor-bottom-left.png) | ![bottom-right](docs/images/anchor-bottom-right.png) |

**`center`**

![center](docs/images/anchor-center.png)

## Offsets

The offset moves the code after it's anchored. Positive `dx` moves it right, and positive `dy` moves it **up**.

**`top-left`, offset `20,-15`:** 20 mm right, 15 mm down, which is a typical inset from a corner.

![top-left with offset 20,-15](docs/images/offset-top-left-right-down.png)

**`center`, offset `40,20`:** 40 mm right and 20 mm up from centre.

![center with offset 40,20](docs/images/offset-center-right-up.png)

**`bottom-right`, offset `-10,10`:** 10 mm in from both the right and bottom edges.

![bottom-right with offset -10,10](docs/images/offset-bottom-right-left-up.png)

## Code size

**`-1` (as large as possible):** the code fills the part's shorter side, 120 mm here.

![code size -1](docs/images/size-max.png)

**`80,50` (bounding box):** the code shrinks to fit the box while staying square, so it's 50 × 50 mm. It's then anchored like any other size.

![code size 80,50](docs/images/size-box.png)

**`-1` with `QR_BORDER=0`:** the dark modules run right to the edges of the box. Only use this if the part itself leaves plain, light-coloured space around the code, because scanners need that quiet margin.

![code size -1 with no quiet zone](docs/images/size-max-border-0.png)

## Regenerating these diagrams

```
python make_examples.py
```
