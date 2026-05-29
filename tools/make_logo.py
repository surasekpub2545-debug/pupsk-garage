"""
Generate the PUP-SK GARAGE logo in multiple variants.
Run:  python tools/make_logo.py
Outputs to assets/logo/
"""
import os, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, '..', 'assets', 'logo')
os.makedirs(OUT, exist_ok=True)


# ── Brand palette (blue-cyan racing) ─────────────────────────────────
BG_DARK   = (7, 8, 14)
BG_PANEL  = (17, 19, 28)
CYAN      = (0, 212, 255)     # #00d4ff — primary "ฟ้า"
BLUE      = (0, 128, 255)     # #0080ff — secondary "น้ำเงิน"
BLUE_DK   = (0, 70, 160)      # for shadows
WHITE     = (255, 255, 255)
GREY      = (140, 150, 175)
GRID      = (40, 50, 70)
# Aliases so the variants below stay readable
GREEN     = CYAN              # main accent name kept generic
GREEN_DK  = BLUE


def _load_font(size, bold=True):
    """Try Tahoma Bold first, fall back to default."""
    candidates = []
    if bold:
        candidates += [r'C:\Windows\Fonts\tahomabd.ttf',
                       r'C:\Windows\Fonts\segoeuib.ttf']
    candidates += [r'C:\Windows\Fonts\tahoma.ttf',
                   r'C:\Windows\Fonts\segoeui.ttf']
    for p in candidates:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except Exception: pass
    return ImageFont.load_default()


def _hexagon(draw, cx, cy, r, fill=None, outline=None, width=1):
    pts = []
    for i in range(6):
        ang = math.radians(60 * i - 30)
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    draw.polygon(pts, fill=fill, outline=outline, width=width)


def _checker_strip(draw, x0, y0, x1, y1, cell=8):
    """Draw a small checker-pattern strip (racing flag)."""
    cols = int((x1 - x0) / cell) + 1
    rows = int((y1 - y0) / cell) + 1
    for ri in range(rows):
        for ci in range(cols):
            cx = x0 + ci * cell
            cy = y0 + ri * cell
            if (ri + ci) % 2 == 0:
                draw.rectangle((cx, cy, min(cx + cell, x1), min(cy + cell, y1)),
                                fill=WHITE)


# ── Variant 1: Hexagonal badge ────────────────────────────────────────
def variant_badge(size=512):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    r_out = int(size * 0.46)
    r_in  = int(size * 0.40)

    # Outer hex carbon shell
    _hexagon(d, cx, cy, r_out, fill=BG_DARK, outline=GREEN, width=6)
    # Inner hex panel
    _hexagon(d, cx, cy, r_in, fill=BG_PANEL, outline=GRID, width=2)

    # Top racing-flag strip (small checker)
    strip_h = int(size * 0.06)
    sx0 = cx - int(r_in * 0.6); sx1 = cx + int(r_in * 0.6)
    sy0 = cy - int(r_in * 0.7); sy1 = sy0 + strip_h
    _checker_strip(d, sx0, sy0, sx1, sy1, cell=int(size * 0.022))

    # Big monogram "PSK"
    f_mono = _load_font(int(size * 0.32), bold=True)
    text = 'PSK'
    bbox = d.textbbox((0, 0), text, font=f_mono)
    tw = bbox[2] - bbox[0]; th = bbox[3] - bbox[1]
    tx = cx - tw / 2 - bbox[0]
    ty = cy - th / 2 - bbox[1] - int(size * 0.03)
    # Drop shadow
    d.text((tx + 4, ty + 4), text, fill=(0, 0, 0, 180), font=f_mono)
    d.text((tx, ty), text, fill=GREEN, font=f_mono)

    # Bottom label "PUP-SK GARAGE"
    f_label = _load_font(int(size * 0.06), bold=True)
    label = 'PUP-SK  GARAGE'
    bbox = d.textbbox((0, 0), label, font=f_label)
    lw = bbox[2] - bbox[0]
    d.text((cx - lw / 2 - bbox[0],
            cy + int(r_in * 0.55) - bbox[1]),
           label, fill=WHITE, font=f_label)

    img.save(os.path.join(OUT, 'logo_badge.png'))
    print('Saved: logo_badge.png')


# ── Variant 2: Horizontal wordmark ────────────────────────────────────
def variant_wordmark(w=1200, h=320):
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Background — solid dark rounded rectangle
    pad = 30
    d.rounded_rectangle((pad, pad, w - pad, h - pad),
                        radius=18, fill=BG_DARK, outline=GREEN, width=4)

    # Left accent block (vertical stripe)
    block_w = int(w * 0.06)
    d.rectangle((pad + 18, pad + 22, pad + 18 + block_w, h - pad - 22),
                fill=GREEN)

    # Main wordmark
    f_main = _load_font(int(h * 0.42), bold=True)
    main = 'PUP-SK'
    text_x = pad + 18 + block_w + 32
    bbox = d.textbbox((0, 0), main, font=f_main)
    text_y = (h - (bbox[3] - bbox[1])) // 2 - bbox[1] - 18
    d.text((text_x, text_y), main, fill=WHITE, font=f_main)
    main_w = bbox[2] - bbox[0]

    # Sub-label "GARAGE" — wider spaced
    f_sub = _load_font(int(h * 0.13), bold=True)
    sub = 'G A R A G E'
    bbox = d.textbbox((0, 0), sub, font=f_sub)
    sub_x = text_x + 6
    sub_y = text_y + int(h * 0.40) + 8
    d.text((sub_x, sub_y), sub, fill=GREEN, font=f_sub)

    # Right-side: monogram badge
    badge_cx = w - pad - int(h * 0.46)
    badge_cy = h // 2
    badge_r  = int(h * 0.36)
    _hexagon(d, badge_cx, badge_cy, badge_r,
             fill=BG_PANEL, outline=GREEN, width=4)
    f_mono = _load_font(int(badge_r * 0.95), bold=True)
    mono = 'P'
    bbox = d.textbbox((0, 0), mono, font=f_mono)
    mx = badge_cx - (bbox[2] - bbox[0]) / 2 - bbox[0]
    my = badge_cy - (bbox[3] - bbox[1]) / 2 - bbox[1]
    d.text((mx, my), mono, fill=GREEN, font=f_mono)

    img.save(os.path.join(OUT, 'logo_wordmark.png'))
    print('Saved: logo_wordmark.png')


# ── Variant 3: Compact app icon (square, for taskbar/launcher) ───────
def variant_icon(size=512):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Rounded-square carbon plate
    pad = int(size * 0.04)
    d.rounded_rectangle((pad, pad, size - pad, size - pad),
                        radius=int(size * 0.18),
                        fill=BG_DARK, outline=GREEN, width=8)

    # Inner accent corner triangles (racing chevron feel)
    chev_pts = [
        (pad + 30, pad + 30),
        (pad + 110, pad + 30),
        (pad + 30, pad + 110),
    ]
    d.polygon(chev_pts, fill=GREEN)

    # Monogram "PSK" centered, slightly raised
    f = _load_font(int(size * 0.42), bold=True)
    text = 'PSK'
    bbox = d.textbbox((0, 0), text, font=f)
    tw = bbox[2] - bbox[0]; th = bbox[3] - bbox[1]
    tx = (size - tw) / 2 - bbox[0]
    ty = (size - th) / 2 - bbox[1] - int(size * 0.04)
    d.text((tx + 5, ty + 5), text, fill=(0, 0, 0, 200), font=f)
    d.text((tx, ty), text, fill=WHITE, font=f)

    # Bottom thin strip "GARAGE"
    f2 = _load_font(int(size * 0.08), bold=True)
    sub = 'GARAGE'
    bbox = d.textbbox((0, 0), sub, font=f2)
    sx = (size - (bbox[2] - bbox[0])) / 2 - bbox[0]
    sy = size - pad - int(size * 0.12) - bbox[1]
    d.text((sx, sy), sub, fill=GREEN, font=f2)

    img.save(os.path.join(OUT, 'logo_icon.png'))
    print('Saved: logo_icon.png')


# ── Variant 4: Splash banner (wide, for app launch screen) ───────────
def variant_splash(w=1920, h=1080):
    img = Image.new('RGBA', (w, h), BG_DARK)
    d = ImageDraw.Draw(img)

    # Subtle radial vignette (optional)
    # Skip for simplicity

    cx, cy = w // 2, h // 2

    # Big monogram center
    f_mono = _load_font(int(h * 0.30), bold=True)
    text = 'PUP-SK'
    bbox = d.textbbox((0, 0), text, font=f_mono)
    tw = bbox[2] - bbox[0]
    tx = cx - tw / 2 - bbox[0]
    ty = cy - (bbox[3] - bbox[1]) / 2 - bbox[1] - 40
    d.text((tx, ty), text, fill=WHITE, font=f_mono)

    # Underline accent bar
    bar_w = int(w * 0.18)
    bar_h = 10
    d.rectangle((cx - bar_w // 2, ty + (bbox[3] - bbox[1]) + 30,
                 cx + bar_w // 2, ty + (bbox[3] - bbox[1]) + 30 + bar_h),
                fill=GREEN)

    # Sub label "GARAGE"
    f_sub = _load_font(int(h * 0.08), bold=True)
    sub = 'G A R A G E'
    bbox = d.textbbox((0, 0), sub, font=f_sub)
    sx = cx - (bbox[2] - bbox[0]) / 2 - bbox[0]
    sy = ty + int(h * 0.30) + 80
    d.text((sx, sy), sub, fill=GREEN, font=f_sub)

    # Footer
    f_foot = _load_font(int(h * 0.022), bold=True)
    foot = 'HONDA ECU TUNING SUITE  -  BY SURASEK'
    bbox = d.textbbox((0, 0), foot, font=f_foot)
    fx = cx - (bbox[2] - bbox[0]) / 2 - bbox[0]
    fy = h - 80 - bbox[1]
    d.text((fx, fy), foot, fill=GREY, font=f_foot)

    img.save(os.path.join(OUT, 'logo_splash.png'))
    print('Saved: logo_splash.png')


def variant_icon_set():
    """Generate Android-compatible icon set."""
    base = os.path.join(OUT, 'logo_icon.png')
    if not os.path.exists(base):
        variant_icon(512)
    icon_dir = os.path.join(OUT, 'icons')
    os.makedirs(icon_dir, exist_ok=True)
    img = Image.open(base).convert('RGBA')
    for sz in (16, 24, 32, 48, 64, 72, 96, 128, 144, 192, 256, 512):
        out = img.resize((sz, sz), Image.LANCZOS)
        out.save(os.path.join(icon_dir, f'icon_{sz}.png'))
        print(f'Saved icon_{sz}.png')
    # Also save as .ico (multi-resolution Windows icon)
    sizes_ico = [(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)]
    img.save(os.path.join(OUT, 'pupsk.ico'),
             format='ICO', sizes=sizes_ico)
    print('Saved pupsk.ico')


if __name__ == '__main__':
    variant_badge(512)
    variant_wordmark(1200, 320)
    variant_icon(512)
    variant_splash(1920, 1080)
    variant_icon_set()
    print(f'\nAll logos saved to: {OUT}')
