"""
AFR Heatmap — RPM × TPS grid, color-coded by deviation from target.
Bands match the TunerPro RT layout for fine resolution.
"""
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, Line
from kivy.core.text import Label as CoreLabel

from . import theme as Theme


# Cached text textures
_TEXT_CACHE = {}

def _text_texture(text, font_size, color, bold=False):
    key = (text, font_size, tuple(color), bold)
    if key not in _TEXT_CACHE:
        lbl = CoreLabel(text=str(text), font_size=font_size,
                        color=color, bold=bold)
        lbl.refresh()
        _TEXT_CACHE[key] = lbl.texture
    return _TEXT_CACHE[key]


# RPM bands — uniform 500 RPM steps from 1000 to 15000
AFRMAP_RPM_BANDS = list(range(1000, 15001, 500))   # 1000, 1500, 2000, ..., 15000
AFRMAP_TPS_BANDS = [
    0.0, 0.4, 0.8, 1.2, 1.4, 1.9, 3.1, 4.1, 4.9, 5.9, 7.1,
    7.9, 9.9, 12.4, 14.9, 17.3, 19.9, 22.3, 24.8, 27.3, 29.7,
    34.7, 39.5, 44.7, 49.6, 54.6, 59.5, 69.5, 72.5,
]


def _bin(value, bands):
    for i in range(len(bands) - 1):
        if bands[i] <= value < bands[i+1]:
            return i
    if value >= bands[-1]:
        return len(bands) - 1
    return 0


def _color_for_afr(afr, target):
    d = abs(afr - target)
    if d <= 0.3: return (0.000, 0.85, 0.48, 1)   # green
    if d <= 0.6: return (0.494, 0.79, 0.27, 1)   # lime
    if d <= 1.0: return (0.85,  0.76, 0.000, 1)  # yellow
    if d <= 1.5: return (0.88,  0.54, 0.19, 1)   # orange
    if d <= 2.5: return (0.85,  0.35, 0.19, 1)   # dark-orange
    return         (0.88,  0.19, 0.23, 1)        # red


class AfrHeatmap(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.target = 14.7
        self.view_mode = 'Most Recent Sample'
        # cell key (ri, ti) → {'last','sum','n','min','max'}
        self.data = {}
        self.cur_rpm = None
        self.cur_tps = None
        self.bind(size=lambda *a: self.redraw(),
                  pos=lambda *a: self.redraw())
        self.redraw()

    def set_target(self, t):
        try: self.target = float(t)
        except: pass
        self.redraw()

    def set_view_mode(self, m):
        self.view_mode = m; self.redraw()

    def reset(self):
        self.data = {}; self.redraw()

    def sample(self, rpm, tps, afr):
        if rpm is None or tps is None or afr is None: return
        if not (0 <= rpm <= 16000 and 0 <= tps <= 100): return
        if not (8.0 <= afr <= 22.0): return
        self.cur_rpm = rpm; self.cur_tps = tps
        ri = _bin(rpm, AFRMAP_RPM_BANDS)
        ti = _bin(tps, AFRMAP_TPS_BANDS)
        cell = self.data.get((ri, ti))
        if cell is None:
            self.data[(ri, ti)] = {'last':afr, 'sum':afr, 'n':1,
                                   'min':afr, 'max':afr}
        else:
            cell['last'] = afr
            cell['sum']  += afr
            cell['n']    += 1
            if afr < cell['min']: cell['min'] = afr
            if afr > cell['max']: cell['max'] = afr

    def _value(self, cell):
        if not cell or cell['n'] == 0: return None
        m = self.view_mode
        if m == 'Most Recent Sample':   return cell['last']
        if m == 'History Average':      return cell['sum'] / cell['n']
        if m == 'History Maximum':      return cell['max']
        if m == 'History Minimum':      return cell['min']
        if m == 'History Sample Count': return cell['n']
        return cell['last']

    def redraw(self, *a):
        """TunerPro-style: X = TPS (left to right, low to high),
        Y = RPM (top to bottom, low RPM at top, high at bottom)."""
        self.canvas.clear()
        x, y, w, h = self.x, self.y, self.width, self.height
        if w < 100 or h < 100: return
        nr = len(AFRMAP_RPM_BANDS); nt = len(AFRMAP_TPS_BANDS)
        # Margin: left wider for RPM labels, bottom for TPS labels,
        # extra top space for "RPM" header above the column of values.
        m_l, m_r, m_t, m_b = 54, 8, 30, 30
        cw = (w - m_l - m_r) / nt    # columns = TPS bands
        ch = (h - m_t - m_b) / nr    # rows    = RPM bands

        # TPS labels can overlap — skip to keep them readable.
        # RPM labels: show ALL of them (no skip).
        tps_step = max(1, int(45 / cw))
        rpm_step = 1

        with self.canvas:
            # Background
            Color(*Theme.BG_DARK)
            Rectangle(pos=(x, y), size=(w, h))

            # Cells — X = TPS (ti), Y = RPM (ri)
            # RPM low at top → Kivy y high
            # RPM index 0 (1100) at top, last index at bottom
            for ri in range(nr):
                for ti in range(nt):
                    cx0 = x + m_l + ti * cw
                    cy0 = y + m_b + (nr - 1 - ri) * ch   # invert for top→bottom
                    cell = self.data.get((ri, ti))
                    val = self._value(cell)
                    if val is not None:
                        if self.view_mode == 'History Sample Count':
                            col = ((0,0.85,0.48,1) if val >= 50 else
                                   (0.85,0.76,0,1) if val >= 10 else
                                   (0.88,0.54,0.19,1) if val >= 3 else
                                   (0.88,0.19,0.23,1))
                        else:
                            col = _color_for_afr(val, self.target)
                        Color(*col)
                        Rectangle(pos=(cx0, cy0), size=(cw, ch))
                    else:
                        Color(0.086, 0.106, 0.153, 1)
                        Rectangle(pos=(cx0, cy0), size=(cw, ch))
                        Color(*Theme.GRID)
                        Line(rectangle=(cx0, cy0, cw, ch), width=0.5)

            # Highlight current cell
            if self.cur_rpm is not None and self.cur_tps is not None:
                ri = _bin(self.cur_rpm, AFRMAP_RPM_BANDS)
                ti = _bin(self.cur_tps, AFRMAP_TPS_BANDS)
                cx0 = x + m_l + ti * cw
                cy0 = y + m_b + (nr - 1 - ri) * ch
                Color(1, 1, 1, 1)
                Line(rectangle=(cx0, cy0, cw, ch), width=2)

            # ── TPS axis labels (X / bottom) ────────────────────────────
            for ti in range(0, nt, tps_step):
                tps = AFRMAP_TPS_BANDS[ti]
                text = f'{tps:.0f}' if tps == int(tps) else f'{tps:.1f}'
                tex = _text_texture(text, 11, Theme.TEXT_DIM, bold=True)
                tx = x + m_l + ti * cw + cw / 2 - tex.width / 2
                ty = y + 6
                Color(1, 1, 1, 1)
                Rectangle(texture=tex, pos=(tx, ty), size=tex.size)
            # X axis title "TPS%"
            tex = _text_texture('TPS%', 11, Theme.PRIMARY, bold=True)
            Color(1, 1, 1, 1)
            Rectangle(texture=tex,
                       pos=(x + w - m_r - tex.width - 4, y + 6),
                       size=tex.size)

            # ── RPM axis labels (Y / left side) — show every band ──────
            # Auto-pick font size so they all fit
            font_y = max(7, min(10, int(ch * 0.55)))
            for ri in range(0, nr, rpm_step):
                rpm = AFRMAP_RPM_BANDS[ri]
                text = str(rpm)
                tex = _text_texture(text, font_y, Theme.TEXT_DIM, bold=True)
                tx = x + m_l - tex.width - 4
                # RPM low at top → high y in Kivy
                ty = y + m_b + (nr - 1 - ri) * ch + ch / 2 - tex.height / 2
                Color(1, 1, 1, 1)
                Rectangle(texture=tex, pos=(tx, ty), size=tex.size)
            # Y axis title "RPM" — centered ABOVE the RPM column
            tex = _text_texture('RPM', 13, Theme.PRIMARY, bold=True)
            Color(1, 1, 1, 1)
            Rectangle(texture=tex,
                       pos=(x + m_l / 2 - tex.width / 2,
                            y + h - m_t + 6),
                       size=tex.size)
