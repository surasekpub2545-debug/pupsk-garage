"""Racing cockpit color palette."""

# Carbon-fiber deep blacks — alpha < 1 so the chosen background image bleeds
# softly through panels. On solid-black bg they look almost the same.
BG          = (1.0, 0.0, 1.0, 1)          # MAGENTA — diagnostic
BG_PANEL    = (0.0, 1.0, 1.0, 1)          # CYAN — diagnostic
BG_DARK     = (1.0, 0.5, 0.0, 1)          # ORANGE — diagnostic
BG_RACE     = (0.0, 1.0, 0.0, 1)          # GREEN — diagnostic

# Carbon hex grid lines
GRID        = (0.118, 0.149, 0.196, 1)    # #1e2632
GRID_DIM    = (0.078, 0.102, 0.137, 1)    # #141a23

# Text — sharp white with hint of cool
TEXT        = (0.96, 0.97, 1.00, 1)
TEXT_DIM    = (0.55, 0.60, 0.72, 1)
TEXT_MUTED  = (0.32, 0.36, 0.45, 1)

# Racing accents — overridable via app_config (loaded by main.py)
# Brand: PUP-SK GARAGE — blue-cyan
PRIMARY     = (0.000, 0.831, 1.000, 1)    # #00d4ff — racing cyan
PRIMARY_DK  = (0.000, 0.502, 1.000, 1)    # #0080ff — deep blue trim


def apply_accent(rgba):
    """Replace the PRIMARY color globally — call this once at app start
    BEFORE any widget is created. Color is a 4-tuple (r,g,b,a)."""
    global PRIMARY, PRIMARY_DK, GLOW_GREEN, STRIPE_HI
    PRIMARY = tuple(rgba)
    PRIMARY_DK = (rgba[0]*0.6, rgba[1]*0.6, rgba[2]*0.6, 1)
    # Update derived colors
    globals()['GLOW_GREEN'] = (rgba[0], rgba[1], rgba[2], 0.35)


def primary_hex() -> str:
    """Current PRIMARY color as 6-char hex (for Kivy [color=...] markup)."""
    r, g, b = PRIMARY[:3]
    return f'{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'
ACCENT      = (0.000, 0.831, 1.000, 1)    # #00d4ff — cyan accent
WARNING     = (1.000, 0.776, 0.000, 1)    # #ffc600 — amber alert
DANGER      = (1.000, 0.090, 0.247, 1)    # #ff173f — racing red
DANGER_DK   = (0.733, 0.000, 0.118, 1)    # #bb001e — brake-light

# Glow / highlight
GLOW_GREEN  = (0.000, 1.000, 0.439, 0.35)
GLOW_RED    = (1.000, 0.090, 0.247, 0.35)
GLOW_CYAN   = (0.000, 0.831, 1.000, 0.35)

# Hex-grid stripe (top of panels, racing-flag feel)
STRIPE_HI   = (0.020, 0.024, 0.035, 1)
STRIPE_LO   = (0.012, 0.016, 0.024, 1)
