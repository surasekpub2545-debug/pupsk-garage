"""
Racing Tachometer — F1-style segmented arc with sequential shift lights.
"""
import math
from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, Ellipse, Rectangle
from kivy.properties import NumericProperty, StringProperty
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel

from . import theme as Theme


# Cache rendered text textures so we don't re-rasterize every frame
_TEXT_CACHE = {}


def _text_texture(text, font_size, color, bold=False):
    """Return a Kivy texture of the given text — cached."""
    key = (text, font_size, tuple(color), bold)
    if key in _TEXT_CACHE:
        return _TEXT_CACHE[key]
    lbl = CoreLabel(text=str(text), font_size=font_size,
                    color=color, bold=bold)
    lbl.refresh()
    tex = lbl.texture
    _TEXT_CACHE[key] = tex
    return tex


class Tachometer(Widget):
    value      = NumericProperty(0)
    target     = NumericProperty(0)
    speed_kmh  = NumericProperty(0)    # GPS speed display

    LOW        = 0
    HIGH       = 12000
    WARN       = 8000
    REDLINE    = 10000

    SEGMENTS   = 60                   # number of arc segments
    # Standard automotive tach: 0 RPM at lower-left (7-8 o'clock),
    # sweep CLOCKWISE through top, ends at lower-right (4-5 o'clock).
    START_DEG  = 225                  # lower-left (Kivy angle, counter-clockwise from +x)
    SWEEP_DEG  = -270                 # negative = clockwise sweep

    def __init__(self, **kw):
        super().__init__(**kw)
        self._smooth_alpha = 0.22
        self.bind(size=lambda *a: self._redraw(),
                  pos=lambda *a:  self._redraw(),
                  value=lambda *a: self._redraw())
        Clock.schedule_interval(self._animate, 1/30.0)
        self._redraw()

    def set_value(self, v):
        self.target = max(self.LOW, min(self.HIGH, v))

    def set_speed(self, kmh):
        """Set GPS speed shown in the dial center (km/h)."""
        try: self.speed_kmh = max(0, float(kmh))
        except Exception: self.speed_kmh = 0

    def reset(self):
        self.target = 0; self.value = 0; self.speed_kmh = 0

    def _animate(self, dt):
        if abs(self.value - self.target) > 0.5:
            self.value += (self.target - self.value) * self._smooth_alpha

    def _seg_color(self, frac, active):
        """frac 0..1 along arc.  Color depends on RPM zone."""
        if frac > 0.85:        # red zone (redline)
            base = Theme.DANGER
        elif frac > 0.65:      # amber zone (warning)
            base = Theme.WARNING
        else:                  # green zone
            base = Theme.PRIMARY
        if not active:
            # dim, carbon-colored
            return (base[0]*0.18, base[1]*0.18, base[2]*0.18, 1)
        return base

    def _redraw(self, *a):
        self.canvas.clear()
        cx = self.center_x
        cy = self.center_y - self.height * 0.04
        size = min(self.width, self.height) * 0.92
        r_outer = size / 2 - 6
        r_inner = r_outer - 24
        if r_outer < 30: return

        active_pct = (self.value - self.LOW) / (self.HIGH - self.LOW)
        active_pct = max(0, min(1, active_pct))
        active_seg = int(self.SEGMENTS * active_pct)

        with self.canvas:
            # Outer ring (carbon) — semi-transparent so bg image bleeds through
            Color(0.024, 0.043, 0.075, 0.55)   # darker, ~55% opacity
            Ellipse(pos=(cx - r_outer - 4, cy - r_outer - 4),
                     size=((r_outer + 4)*2, (r_outer + 4)*2))
            Color(*Theme.GRID)
            Line(circle=(cx, cy, r_outer + 4), width=2)

            # Inner face — extra transparent, lets the panel/bg show through
            Color(0.043, 0.051, 0.067, 0.40)   # ~40% opacity
            Ellipse(pos=(cx - r_inner, cy - r_inner),
                     size=(r_inner*2, r_inner*2))

            # Segmented arc — racing-style trapezoid segments
            for i in range(self.SEGMENTS):
                frac = i / (self.SEGMENTS - 1)
                ang = math.radians(self.START_DEG + frac * self.SWEEP_DEG)
                # Each segment as a small line stroke
                col = self._seg_color(frac, i <= active_seg)
                Color(*col)
                x0 = cx + r_inner * math.cos(ang)
                y0 = cy + r_inner * math.sin(ang)
                x1 = cx + r_outer * math.cos(ang)
                y1 = cy + r_outer * math.sin(ang)
                Line(points=[x0, y0, x1, y1], width=2.5)

            # RPM numerals every 1000 (shown as 0, 2, 4 ... 12)
            font_sz = max(16, int(r_inner * 0.17))
            for r in range(0, 13000, 1000):
                pct = (r - self.LOW) / (self.HIGH - self.LOW)
                if not 0 <= pct <= 1: continue
                ang = math.radians(self.START_DEG + pct * self.SWEEP_DEG)
                # Tick mark
                tx0 = cx + (r_inner - 12) * math.cos(ang)
                ty0 = cy + (r_inner - 12) * math.sin(ang)
                tx1 = cx + (r_inner - 4)  * math.cos(ang)
                ty1 = cy + (r_inner - 4)  * math.sin(ang)
                # Color tick + label by zone
                if r >= self.REDLINE:
                    col = Theme.DANGER
                elif r >= self.WARN:
                    col = Theme.WARNING
                else:
                    col = Theme.TEXT
                Color(*col)
                Line(points=[tx0, ty0, tx1, ty1], width=2)
                # Only show numeric labels at even thousands (0,2,4,…,12)
                if r % 2000 == 0:
                    text = str(r // 1000)
                    tex = _text_texture(text, font_sz, col, bold=True)
                    # Position label inward from tick
                    lx = cx + (r_inner - 28) * math.cos(ang) - tex.width / 2
                    ly = cy + (r_inner - 28) * math.sin(ang) - tex.height / 2
                    Color(1, 1, 1, 1)   # tex carries its own color
                    Rectangle(texture=tex, pos=(lx, ly), size=tex.size)

            # "RPM × 1000" tiny label — pinned near very bottom of dial
            rpm_text = 'RPM x 1000'
            tex = _text_texture(rpm_text, max(13, int(r_inner * 0.12)),
                                Theme.TEXT_DIM, bold=True)
            lx = cx - tex.width / 2
            ly = cy - r_inner * 0.82
            Color(1, 1, 1, 1)
            Rectangle(texture=tex, pos=(lx, ly), size=tex.size)

            # Needle — sharp triangle
            ang = math.radians(self.START_DEG + active_pct * self.SWEEP_DEG)
            nx = cx + (r_inner - 8) * math.cos(ang)
            ny = cy + (r_inner - 8) * math.sin(ang)
            # Color based on zone
            if self.value >= self.REDLINE:
                col = Theme.DANGER
            elif self.value >= self.WARN:
                col = Theme.WARNING
            else:
                col = Theme.PRIMARY
            # Glow under needle
            Color(col[0], col[1], col[2], 0.4)
            Line(points=[cx, cy, nx, ny], width=6)
            # Solid needle
            Color(*col)
            Line(points=[cx, cy, nx, ny], width=3)
            # Center hub
            d = 18
            Color(*Theme.BG_DARK)
            Ellipse(pos=(cx-d/2, cy-d/2), size=(d, d))
            Color(*col)
            Line(circle=(cx, cy, d/2), width=2)

            # ── GPS speed — BIG number positioned ABOVE the hub ─────────
            # Drawn AFTER needle/hub so it always renders on top
            spd = int(self.speed_kmh)
            spd_size = max(26, int(r_inner * 0.38))
            tex_s = _text_texture(str(spd), spd_size, Theme.PRIMARY, bold=True)
            sx = cx - tex_s.width / 2
            sy = cy + d/2 + 8
            # Dark semi-transparent backdrop for legibility over needle/arc
            pad_x, pad_y = 10, 4
            Color(0, 0, 0, 0.55)
            Rectangle(pos=(sx - pad_x, sy - pad_y),
                       size=(tex_s.width + pad_x*2, tex_s.height + pad_y*2))
            Color(1, 1, 1, 1)
            Rectangle(texture=tex_s, pos=(sx, sy), size=tex_s.size)
            # "km/h" label above the speed value
            unit_size = max(13, int(r_inner * 0.14))
            tex_u = _text_texture('km/h', unit_size, Theme.TEXT_DIM, bold=True)
            ux = cx - tex_u.width / 2
            uy = sy + tex_s.height + 4
            Color(1, 1, 1, 1)
            Rectangle(texture=tex_u, pos=(ux, uy), size=tex_u.size)

            # Sequential shift lights — arc across the TOP of dial
            # Left-to-right reading order: i=0 furthest left, i=7 rightmost
            n_lights = 8
            light_r = 8
            for i in range(n_lights):
                # angle 111° (upper-left) → 69° (upper-right) in Kivy math
                ang = math.radians(111 - i * (42 / (n_lights - 1)))
                lx = cx + (r_outer + 22) * math.cos(ang) - light_r
                ly = cy + (r_outer + 22) * math.sin(ang) - light_r
                threshold = self.WARN + i * 350
                lit = self.value >= threshold
                if lit:
                    if i < 3: lc = Theme.PRIMARY
                    elif i < 6: lc = Theme.WARNING
                    else: lc = Theme.DANGER
                else:
                    lc = Theme.GRID
                Color(*lc)
                Ellipse(pos=(lx, ly), size=(light_r*2, light_r*2))
