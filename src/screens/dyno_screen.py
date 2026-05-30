"""
Dyno screen — racing-style auto-triggered HP/torque curve with
live RPM/AFR/SPD/ECT readout and interactive chart cursor.
"""
import math, time, json, os
from datetime import datetime
from collections import namedtuple
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle, Line, Ellipse
from kivy.clock import Clock

from src.widgets import theme as Theme
from src.widgets.racing_ui import paint_bg, RacingButton, LedNumber
from src import dyno


LoadedSample = namedtuple('LoadedSample',
                          't rpm speed accel hp torque_nm')


# ── Chart series palettes ─────────────────────────────────────────
# index 0 = default (single / newest / live run).  Older runs cycle
# through later entries so each compared run gets a distinct color.
HP_PALETTE = [
    (0.000, 1.000, 0.439, 1),   # #00ff70 — racing green (default)
    (0.000, 0.831, 1.000, 1),   # #00d4ff — cyan
    (1.000, 0.776, 0.000, 1),   # #ffc600 — amber
    (0.627, 0.392, 1.000, 1),   # #a064ff — purple
    (1.000, 0.392, 0.784, 1),   # #ff64c8 — pink
]
TQ_PALETTE = [
    (1.000, 0.196, 0.235, 1),   # #ff323c — racing red (default)
    (1.000, 0.549, 0.000, 1),   # #ff8c00 — orange
    (1.000, 0.000, 0.706, 1),   # #ff00b4 — magenta
    (0.392, 0.392, 1.000, 1),   # #6464ff — blue
    (0.706, 1.000, 0.392, 1),   # #b4ff64 — lime
]
AFR_PALETTE = [
    (1.000, 1.000, 1.000, 1),   # #ffffff — white (default)
    (0.784, 0.784, 0.784, 1),   # #c8c8c8 — gray
    (1.000, 0.784, 0.392, 1),   # #ffc864 — cream
    (1.000, 0.392, 0.392, 1),   # #ff6464 — salmon
    (0.392, 1.000, 1.000, 1),   # #64ffff — pale cyan
]

# Default colors (toggle buttons, peak labels, cursor text use these)
HP_COLOR  = HP_PALETTE[0]
TQ_COLOR  = TQ_PALETTE[0]
AFR_COLOR = AFR_PALETTE[0]
HP_HEX    = '00ff70'
TQ_HEX    = 'ff323c'
AFR_HEX   = 'ffffff'


# ──────────────────────────────────────────────────────────────────────
# Chart canvas — HP/Nm curves + interactive cursor
# ──────────────────────────────────────────────────────────────────────
class DynoChartCanvas(Widget):
    AFR_MIN = 10.0
    AFR_MAX = 18.0

    def __init__(self, on_cursor=None, **kw):
        super().__init__(**kw)
        self.runs = []
        self.run_afrs = []
        self.show_hp = True
        self.show_tq = True
        self.show_afr = True
        self.live_run = None
        self.live_afrs = []
        self.rpm_min = 2000
        self.rpm_max = 13000      # headroom for high-rev sport bikes
        self.redline = 0          # >0 = draw a red vertical line at this RPM
        # Cursor state
        self.cursor_rpm = None
        self._on_cursor = on_cursor
        # Cached geometry
        self._plot_rect = (0, 0, 0, 0, 0, 0)   # x, y, w, h, m_l, m_b
        self.bind(size=lambda *a: self.redraw(),
                  pos=lambda *a: self.redraw())

    # ── Touch → cursor ──────────────────────────────────────
    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        print(f'[chart] touch at x={touch.x:.0f} y={touch.y:.0f}')
        self._set_cursor_from_x(touch.x)
        return True

    def on_touch_move(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        self._set_cursor_from_x(touch.x)
        return True

    def _set_cursor_from_x(self, tx):
        x, y, w, h = self.x, self.y, self.width, self.height
        m_l, m_r = 50, 50
        plot_w = max(1, w - m_l - m_r)
        frac = (tx - x - m_l) / plot_w
        frac = max(0, min(1, frac))
        rpm = self.rpm_min + frac * (self.rpm_max - self.rpm_min)
        self.cursor_rpm = rpm
        self._emit_cursor()
        self.redraw()

    def clear_cursor(self):
        self.cursor_rpm = None
        if self._on_cursor:
            self._on_cursor(None)
        self.redraw()

    def _emit_cursor(self):
        """Find nearest sample (last run / live run) at cursor RPM, emit values."""
        if self._on_cursor is None or self.cursor_rpm is None:
            return
        # Pick most relevant run: live during recording, else newest
        if self.live_run:
            run = self.live_run
            afrs = self.live_afrs or []
        elif self.runs:
            run = self.runs[-1]
            afrs = self.run_afrs[-1] if self.run_afrs else []
        else:
            # No runs loaded — still report the cursor RPM so the user
            # gets immediate feedback that the tap registered.
            self._on_cursor({'rpm': self.cursor_rpm, 'no_data': True})
            return
        if not run:
            self._on_cursor({'rpm': self.cursor_rpm, 'no_data': True})
            return
        # nearest sample by RPM
        best_i, best_d = 0, float('inf')
        for i, s in enumerate(run):
            d = abs(s.rpm - self.cursor_rpm)
            if d < best_d:
                best_d, best_i = d, i
        s = run[best_i]
        afr = None
        if best_i < len(afrs):
            afr = afrs[best_i]
        self._on_cursor({
            'rpm':   s.rpm,
            'hp':    s.hp,
            'tq':    s.torque_nm,
            'speed': s.speed,
            'afr':   afr,
        })

    # ── Draw ────────────────────────────────────────────────
    def redraw(self, *a):
        self.canvas.clear()
        x, y, w, h = self.x, self.y, self.width, self.height
        if w < 100 or h < 100:
            return

        all_runs = list(self.runs)
        all_afrs = list(self.run_afrs)
        if self.live_run:
            all_runs.append(self.live_run)
            all_afrs.append(self.live_afrs or [])

        with self.canvas:
            # Background
            Color(*Theme.BG_DARK)
            Rectangle(pos=(x, y), size=(w, h))
            Color(*Theme.GRID)
            Line(rectangle=(x, y, w, h), width=1)
            Color(*Theme.PRIMARY)
            Rectangle(pos=(x, y + h - 2), size=(w, 2))

            m_l, m_r, m_t, m_b = 50, 50, 16, 28
            plot_w = w - m_l - m_r
            plot_h = h - m_t - m_b
            self._plot_rect = (x, y, w, h, m_l, m_b)

            # X-axis RPM labels
            for r in range(int(self.rpm_min), int(self.rpm_max) + 1, 1000):
                if r < self.rpm_min or r > self.rpm_max:
                    continue
                gx = x + m_l + plot_w * (r - self.rpm_min) / max(1, self.rpm_max - self.rpm_min)
                Color(*Theme.GRID_DIM)
                Line(points=[gx, y + m_b, gx, y + h - m_t],
                     width=1, dash_length=2, dash_offset=4)
                # RPM number under the tick
                from kivy.core.text import Label as _CL
                lbl = _CL(text=f'{r // 1000}k' if r else '0',
                          font_size=11, color=Theme.TEXT_DIM, bold=True)
                lbl.refresh()
                tx = lbl.texture
                Color(1, 1, 1, 1)
                Rectangle(texture=tx,
                            pos=(gx - tx.width / 2, y + m_b - tx.height - 2),
                            size=tx.size)

            # Redline marker
            if self.redline and self.rpm_min <= self.redline <= self.rpm_max:
                rx = x + m_l + plot_w * (self.redline - self.rpm_min) / \
                     max(1, self.rpm_max - self.rpm_min)
                Color(*Theme.DANGER)
                Line(points=[rx, y + m_b, rx, y + h - m_t], width=2)

            # Y grid
            for i in range(1, 5):
                gy = y + m_b + plot_h * i / 5
                Color(*Theme.GRID_DIM)
                Line(points=[x + m_l, gy, x + w - m_r, gy],
                     width=1, dash_length=2, dash_offset=4)

            if not all_runs:
                # "No data" hint
                from kivy.core.text import Label as CoreLabel
                lbl = CoreLabel(text='— NO DATA — START A RUN',
                                  font_size=14, color=Theme.TEXT_DIM,
                                  bold=True)
                lbl.refresh()
                tx = lbl.texture
                Color(1, 1, 1, 1)
                Rectangle(texture=tx,
                            pos=(x + (w - tx.width) / 2,
                                  y + (h - tx.height) / 2),
                            size=tx.size)
                # Draw cursor line even with no data so user gets
                # visual feedback that the tap registered
                if self.cursor_rpm is not None:
                    frac = (self.cursor_rpm - self.rpm_min) / \
                        max(1, self.rpm_max - self.rpm_min)
                    frac = max(0, min(1, frac))
                    cx = x + m_l + plot_w * frac
                    Color(1, 1, 1, 0.85)
                    Line(points=[cx, y + m_b, cx, y + h - m_t],
                         width=1.5)
                return

            # Build (sample, afr) pair lists per run, filtered by RPM window
            filtered_pairs = []
            for ridx, run in enumerate(all_runs):
                run_afrs = all_afrs[ridx] if ridx < len(all_afrs) else []
                pairs = []
                for i, s in enumerate(run):
                    if self.rpm_min <= s.rpm <= self.rpm_max:
                        afr = run_afrs[i] if i < len(run_afrs) else None
                        pairs.append((s, afr))
                if pairs:
                    filtered_pairs.append(pairs)
            if not filtered_pairs:
                return

            hp_max = max(1.0, max(p[0].hp for r in filtered_pairs for p in r))
            tq_max = max(1.0, max(p[0].torque_nm
                                    for r in filtered_pairs for p in r))

            def x_of(r):
                return x + m_l + plot_w * (r - self.rpm_min) / \
                       max(1, self.rpm_max - self.rpm_min)

            def y_hp(v):  return y + m_b + plot_h * v / hp_max
            def y_tq(v):  return y + m_b + plot_h * v / tq_max
            def y_afr(v): return y + m_b + plot_h * \
                (max(self.AFR_MIN, min(self.AFR_MAX, v)) - self.AFR_MIN) / \
                (self.AFR_MAX - self.AFR_MIN)

            n = len(filtered_pairs)
            for idx, pairs in enumerate(filtered_pairs):
                # Newest / live run = palette index 0 (default colors).
                # Older runs cycle through the palette so each is distinct.
                pi = (n - 1) - idx
                is_newest = (idx == n - 1)
                w_line = 3 if is_newest else 2

                hp_col  = HP_PALETTE[pi  % len(HP_PALETTE)]
                tq_col  = TQ_PALETTE[pi  % len(TQ_PALETTE)]
                afr_col = AFR_PALETTE[pi % len(AFR_PALETTE)]

                sorted_pairs = sorted(pairs, key=lambda p: p[0].rpm)
                if self.show_hp:
                    pts = []
                    for s, _ in sorted_pairs:
                        pts.extend([x_of(s.rpm), y_hp(s.hp)])
                    if len(pts) >= 4:
                        r0, g0, b0, _ = hp_col
                        Color(r0, g0, b0, 0.25)
                        Line(points=pts, width=w_line + 4)
                        Color(*hp_col)
                        Line(points=pts, width=w_line)
                if self.show_tq:
                    pts = []
                    for s, _ in sorted_pairs:
                        pts.extend([x_of(s.rpm), y_tq(s.torque_nm)])
                    if len(pts) >= 4:
                        r0, g0, b0, _ = tq_col
                        Color(r0, g0, b0, 0.20)
                        Line(points=pts, width=w_line + 4)
                        Color(*tq_col)
                        Line(points=pts, width=w_line)
                if self.show_afr:
                    pts = []
                    for s, afr in sorted_pairs:
                        try:
                            v = float(afr)
                        except (TypeError, ValueError):
                            continue
                        if v <= 0:
                            continue
                        pts.extend([x_of(s.rpm), y_afr(v)])
                    if len(pts) >= 4:
                        r0, g0, b0, _ = afr_col
                        Color(r0, g0, b0, 0.20)
                        Line(points=pts, width=w_line + 3,
                              dash_length=6, dash_offset=4)
                        Color(*afr_col)
                        Line(points=pts, width=w_line,
                              dash_length=6, dash_offset=4)

            # Right-side AFR axis labels (only if AFR shown)
            if self.show_afr:
                from kivy.core.text import Label as CoreLabel
                for v in (12, 13, 14, 15, 16):
                    yy = y_afr(v)
                    Color(*AFR_COLOR)
                    Line(points=[x + w - m_r - 4, yy,
                                  x + w - m_r + 2, yy], width=1)
                    lbl = CoreLabel(text=str(v), font_size=11,
                                      color=AFR_COLOR, bold=True)
                    lbl.refresh()
                    tx = lbl.texture
                    Color(1, 1, 1, 1)
                    Rectangle(texture=tx,
                                pos=(x + w - m_r + 4, yy - tx.height / 2),
                                size=tx.size)
                lbl = CoreLabel(text='AFR', font_size=10,
                                  color=AFR_COLOR, bold=True)
                lbl.refresh()
                tx = lbl.texture
                Color(1, 1, 1, 1)
                Rectangle(texture=tx,
                            pos=(x + w - m_r + 4, y + h - m_t - 14),
                            size=tx.size)

            # ── Cursor ─────────────────────────────────────
            if self.cursor_rpm is not None:
                cx = x_of(max(self.rpm_min,
                                min(self.rpm_max, self.cursor_rpm)))
                Color(1, 1, 1, 0.85)
                Line(points=[cx, y + m_b, cx, y + h - m_t], width=1.5)
                # Dots at intersections with the most recent / live run
                ref_run = self.live_run if self.live_run else \
                          (self.runs[-1] if self.runs else None)
                if ref_run:
                    best, bd = None, float('inf')
                    for s in ref_run:
                        d = abs(s.rpm - self.cursor_rpm)
                        if d < bd: bd, best = d, s
                    if best:
                        if self.show_hp:
                            ux, uy = x_of(best.rpm), y_hp(best.hp)
                            Color(*HP_COLOR)
                            Ellipse(pos=(ux - 5, uy - 5), size=(10, 10))
                            Color(1, 1, 1, 1)
                            Line(circle=(ux, uy, 5), width=1.5)
                        if self.show_tq:
                            ux, uy = x_of(best.rpm), y_tq(best.torque_nm)
                            Color(*TQ_COLOR)
                            Ellipse(pos=(ux - 5, uy - 5), size=(10, 10))
                            Color(1, 1, 1, 1)
                            Line(circle=(ux, uy, 5), width=1.5)
                        # Cursor AFR dot
                        if self.show_afr:
                            ref_afrs = (self.live_afrs if self.live_run
                                         else (self.run_afrs[-1]
                                                if self.run_afrs else []))
                            best_i = None
                            for i, s in enumerate(ref_run):
                                if s is best: best_i = i; break
                            try:
                                v = float(ref_afrs[best_i])
                            except Exception:
                                v = None
                            if v and v > 0:
                                ux, uy = x_of(best.rpm), y_afr(v)
                                Color(*AFR_COLOR)
                                Ellipse(pos=(ux - 5, uy - 5), size=(10, 10))
                                Color(1, 1, 1, 1)
                                Line(circle=(ux, uy, 5), width=1.5)


# ──────────────────────────────────────────────────────────────────────
# Dyno screen
# ──────────────────────────────────────────────────────────────────────
class DynoScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.name = 'dyno'

        # ── State ───────────────────────────────────────────
        self.spec = dyno.VehicleSpec()
        self.state = 'idle'
        self.samples = []
        self.t0 = 0.0
        self.runs = []
        self.run_afrs = []
        self.run_labels = []
        self._vehicle_vals = {
            'tire':         '70/90-17',
            'mass':         '195',
            'gear':         '11.5',
            'driveline':    '0.12',
            'rolling':      '0.018',
            'drag':         '0.95',
            'air_density':  '1.20',
            'frontal_area': '0.55',
            'wheel_circ_m': 1.745,
        }

        root = BoxLayout(orientation='vertical', padding=(10, 8), spacing=6)
        self.add_widget(root)

        # ── Header strip ────────────────────────────────────
        head = BoxLayout(orientation='horizontal', size_hint=(1, None),
                          height=42, padding=(10, 4))
        paint_bg(head, Theme.BG_DARK)
        head.add_widget(Label(
            text='[size=18][b][color=00ff70]D Y N O[/color][/b][/size]',
            markup=True, size_hint=(0.3, 1),
            halign='left', valign='middle'))
        head.children[0].bind(size=lambda l, s: setattr(l, 'text_size', s))
        self.status_lbl = Label(
            text='[size=14]IDLE[/size]',
            markup=True, color=Theme.TEXT_DIM,
            size_hint=(0.7, 1), halign='right', valign='middle')
        self.status_lbl.bind(size=lambda l, s: setattr(l, 'text_size', s))
        head.add_widget(self.status_lbl)
        root.add_widget(head)

        # ── LIVE READOUT (RPM / AFR / SPD / ECT / IAT) ──────
        live = BoxLayout(orientation='horizontal', size_hint=(1, None),
                          height=78, spacing=6, padding=(8, 6))
        paint_bg(live, Theme.BG_PANEL, border=Theme.GRID)
        self.live_rpm = self._live_cell(live, 'R P M',  '0',  Theme.PRIMARY, 0.24)
        self.live_afr = self._live_cell(live, 'A F R',  '--', Theme.WARNING, 0.19)
        self.live_spd = self._live_cell(live, 'S P D',  '0',  Theme.PRIMARY, 0.19)
        self.live_tps = self._live_cell(live, 'T P S',  '0',  Theme.ACCENT,  0.19)
        self.live_ect = self._live_cell(live, 'E C T',  '--', Theme.ACCENT,  0.19)
        root.add_widget(live)

        # State for all dyno setup values (edited via popup, not inline)
        self._dyno_cfg = {
            'chart_rpm_min': 2000.0,
            'chart_rpm_max': 13000.0,
            'redline':       0.0,
            'trig_start':    3000.0,
            'trig_stop':     9000.0,
        }

        # ── Settings row — just two buttons, popups hold the rest ──
        tr = BoxLayout(orientation='horizontal', size_hint=(1, None),
                        height=54, spacing=8, padding=(8, 4))
        paint_bg(tr, Theme.BG_PANEL, border=Theme.GRID)
        btn_veh = RacingButton('vehicle settings', font_size=14,
                                 size_hint=(0.5, 1))
        btn_veh.bind(on_release=lambda *a: self._open_vehicle_popup())
        tr.add_widget(btn_veh)
        btn_dyno = RacingButton('dyno settings', primary=True, font_size=14,
                                  size_hint=(0.5, 1))
        btn_dyno.bind(on_release=lambda *a: self._open_dyno_popup())
        tr.add_widget(btn_dyno)
        root.add_widget(tr)

        # ── Run controls row ────────────────────────────────
        cr = BoxLayout(orientation='horizontal', size_hint=(1, None),
                        height=64, spacing=6)
        self.btn_run = RacingButton('start', danger=True, font_size=18,
                                      size_hint=(0.40, 1))
        self.btn_run.bind(on_release=lambda *a: self._toggle_run())
        cr.add_widget(self.btn_run)
        btn_clr = RacingButton('clear', font_size=14, size_hint=(0.15, 1))
        btn_clr.bind(on_release=lambda *a: self._clear())
        cr.add_widget(btn_clr)
        btn_save = RacingButton('save run', primary=True, font_size=14,
                                  size_hint=(0.15, 1))
        btn_save.bind(on_release=lambda *a: self._on_save_run())
        cr.add_widget(btn_save)
        btn_load = RacingButton('load run', font_size=14, size_hint=(0.15, 1))
        btn_load.bind(on_release=lambda *a: self._on_load_run())
        cr.add_widget(btn_load)
        btn_cmp = RacingButton('compare', font_size=14, size_hint=(0.15, 1))
        btn_cmp.bind(on_release=lambda *a: self._on_compare())
        cr.add_widget(btn_cmp)
        root.add_widget(cr)

        # ── Combined peak + cursor strip + toggles (compact) ────
        pk = BoxLayout(orientation='horizontal', size_hint=(1, None),
                        height=56, spacing=6, padding=(10, 4))
        paint_bg(pk, Theme.BG_PANEL, border=Theme.GRID)

        # Peak HP
        col1 = BoxLayout(orientation='horizontal', size_hint=(0.16, 1),
                          spacing=4)
        col1.add_widget(Label(
            text='[size=11][b][color=66798a]PEAK HP[/color][/b][/size]',
            markup=True, size_hint=(0.45, 1),
            halign='right', valign='middle'))
        col1.children[0].bind(size=lambda l, s: setattr(l, 'text_size', s))
        self.peak_hp_lbl = LedNumber('--', color=HP_COLOR, font_size=24,
                                       halign='left',
                                       size_hint=(0.55, 1))
        col1.add_widget(self.peak_hp_lbl)
        pk.add_widget(col1)

        # Peak Nm
        col2 = BoxLayout(orientation='horizontal', size_hint=(0.16, 1),
                          spacing=4)
        col2.add_widget(Label(
            text='[size=11][b][color=66798a]PEAK Nm[/color][/b][/size]',
            markup=True, size_hint=(0.45, 1),
            halign='right', valign='middle'))
        col2.children[0].bind(size=lambda l, s: setattr(l, 'text_size', s))
        self.peak_tq_lbl = LedNumber('--', color=TQ_COLOR, font_size=24,
                                       halign='left',
                                       size_hint=(0.55, 1))
        col2.add_widget(self.peak_tq_lbl)
        pk.add_widget(col2)

        # Divider
        sep = Widget(size_hint=(None, 1), width=2)
        with sep.canvas:
            Color(*Theme.GRID)
            self._sep_r = Rectangle(pos=sep.pos, size=sep.size)
        sep.bind(pos=lambda *a: setattr(self._sep_r, 'pos', sep.pos),
                  size=lambda *a: setattr(self._sep_r, 'size', sep.size))
        pk.add_widget(sep)

        # Cursor info — single label that takes the remaining horizontal
        # space so the panel is just one short row.
        self.cursor_lbl = Label(
            text='[size=13][color=99aacc]'
                 'แตะที่กราฟเพื่อดูค่าในช่วง RPM นั้น[/color][/size]',
            markup=True, color=Theme.TEXT,
            halign='left', valign='middle', size_hint=(0.56, 1))
        self.cursor_lbl.bind(size=lambda l, s: setattr(l, 'text_size', s))
        pk.add_widget(self.cursor_lbl)

        # × clear cursor (tiny)
        btn_clr_cur = Button(text='[size=11][color=99aacc]× clear[/color][/size]',
                              markup=True, background_color=(0, 0, 0, 0),
                              size_hint=(None, 1), width=70,
                              halign='right', valign='middle')
        btn_clr_cur.bind(size=lambda l, s: setattr(l, 'text_size', s))
        btn_clr_cur.bind(on_release=lambda *a: self._on_clear_cursor())
        pk.add_widget(btn_clr_cur)
        root.add_widget(pk)

        # ── Series toggle row + EXPAND button ───────────────
        tg = BoxLayout(orientation='horizontal', size_hint=(1, None),
                        height=36, spacing=6, padding=(8, 4))
        paint_bg(tg, Theme.BG_DARK)
        self.tog_hp  = self._make_toggle('HP',  HP_COLOR,  True,
                                            lambda v: self._tog('hp', v))
        self.tog_tq  = self._make_toggle('Nm',  TQ_COLOR,  True,
                                            lambda v: self._tog('tq', v))
        self.tog_afr = self._make_toggle('AFR', AFR_COLOR, True,
                                            lambda v: self._tog('afr', v))
        tg.add_widget(self.tog_hp)
        tg.add_widget(self.tog_tq)
        tg.add_widget(self.tog_afr)
        legend = Label(
            text='[size=11][color=99aacc]'
                 'แตะปุ่มเพื่อเปิด/ปิดเส้น  •  แตะกราฟเพื่อดูค่า'
                 '[/color][/size]',
            markup=True, halign='right', valign='middle')
        legend.bind(size=lambda l, s: setattr(l, 'text_size', s))
        tg.add_widget(legend)
        btn_expand = RacingButton('expand', primary=True, font_size=13,
                                    size_hint=(None, 1), width=110)
        btn_expand.bind(on_release=lambda *a: self._open_chart_fullscreen())
        tg.add_widget(btn_expand)
        root.add_widget(tg)

        # ── Chart ───────────────────────────────────────────
        self.chart = DynoChartCanvas(on_cursor=self._on_cursor,
                                       size_hint=(1, 1))
        root.add_widget(self.chart)
        # Sync initial chart range from cfg defaults
        self._apply_chart_range(redraw=False)

    # ── Helpers ─────────────────────────────────────────────
    def _make_toggle(self, label, color, initial, on_change):
        """Pill button that toggles a chart curve on/off."""
        btn = Button(text=f'[b]{label}[/b]', markup=True,
                      background_color=(0, 0, 0, 0),
                      color=(0, 0, 0, 1) if initial else Theme.TEXT_DIM,
                      size_hint=(None, 1), width=80, font_size=15)
        btn._active = initial
        btn._color = color

        def _paint(*a):
            btn.canvas.before.clear()
            with btn.canvas.before:
                if btn._active:
                    Color(*btn._color)
                else:
                    Color(0.08, 0.10, 0.13, 1)
                btn._bg = Rectangle(pos=btn.pos, size=btn.size)
                Color(*Theme.GRID)
                btn._ol = Line(rectangle=(btn.x, btn.y, btn.width, btn.height),
                                width=1)

        _paint()
        btn.bind(pos=_paint, size=_paint)

        def _toggle(*a):
            btn._active = not btn._active
            btn.color = (0, 0, 0, 1) if btn._active else Theme.TEXT_DIM
            _paint()
            on_change(btn._active)

        btn.bind(on_release=_toggle)
        return btn

    def _tog(self, which, active):
        if   which == 'hp':  self.chart.show_hp = active
        elif which == 'tq':  self.chart.show_tq = active
        elif which == 'afr': self.chart.show_afr = active
        self.chart.redraw()

    def _live_cell(self, parent, label, default, color, width_frac):
        col = BoxLayout(orientation='vertical', size_hint=(width_frac, 1))
        col.add_widget(Label(
            text=f'[size=11][b][color=66798a]{label}[/color][/b][/size]',
            markup=True, size_hint=(1, None), height=16,
            halign='center', valign='middle'))
        col.children[0].bind(size=lambda l, s: setattr(l, 'text_size', s))
        led = LedNumber(default, color=color, font_size=32, halign='center')
        col.add_widget(led)
        parent.add_widget(col)
        return led

    def on_enter(self, *a):
        Clock.schedule_once(lambda dt: self._force_redraw(), 0)

    def on_leave(self, *a):
        pass

    def _force_redraw(self):
        try: self.chart.redraw()
        except Exception: pass
        try: self.canvas.ask_update()
        except Exception: pass

    # ── Cursor callback ─────────────────────────────────────
    def _on_cursor(self, info):
        if info is None:
            self.cursor_lbl.text = ('[size=14][color=99aacc]'
                'แตะที่กราฟเพื่อดูค่าในช่วง RPM นั้น'
                '[/color][/size]')
            return
        # No-data path — just show the cursor RPM
        if info.get('no_data'):
            self.cursor_lbl.text = (
                f'[size=16][b]'
                f'[color=ffffff]{int(info["rpm"])}[/color] '
                f'[color=66798a]RPM[/color]   '
                f'[color=99aacc](ยังไม่มี'
                f'ข้อมูล — START / LOAD A RUN)'
                f'[/color][/b][/size]')
            return
        afr_s = f'{info["afr"]:.1f}' if info.get('afr') else '--'
        self.cursor_lbl.text = (
            f'[size=16][b]'
            f'[color=ffffff]{int(info["rpm"])}[/color] [color=66798a]RPM[/color]   '
            f'[color={HP_HEX}]{info["hp"]:.1f}[/color] [color=66798a]HP[/color]   '
            f'[color={TQ_HEX}]{info["tq"]:.1f}[/color] [color=66798a]Nm[/color]   '
            f'[color={AFR_HEX}]{afr_s}[/color] [color=66798a]AFR[/color]   '
            f'[color=ffffff]{info["speed"]:.0f}[/color] [color=66798a]km/h[/color]'
            f'[/b][/size]')

    def _on_clear_cursor(self):
        self.chart.clear_cursor()

    # ── Chart RPM display range / redline ───────────────────
    def _apply_chart_range(self, redraw=True):
        """Push CHART RPM range + redline + trigger thresholds from
        self._dyno_cfg into the canvas."""
        c = self._dyno_cfg
        lo, hi = c['chart_rpm_min'], c['chart_rpm_max']
        if hi <= lo:
            hi = lo + 1000
        self.chart.rpm_min = lo
        self.chart.rpm_max = hi
        self.chart.redline = c['redline']
        if redraw:
            self.chart.redraw()

    # ── Dyno settings popup ─────────────────────────────────
    def _open_dyno_popup(self):
        from src.screens.dyno_settings_popup_chart import DynoSettingsPopup
        DynoSettingsPopup(self._dyno_cfg, on_save=self._apply_dyno_cfg).open()

    # ── Fullscreen chart + Save PNG ─────────────────────────
    def _open_chart_fullscreen(self):
        from kivy.app import App
        from kivy.uix.floatlayout import FloatLayout
        view = ModalView(size_hint=(0.98, 0.96),
                          background_color=(0, 0, 0, 0), background='',
                          auto_dismiss=True)
        box = BoxLayout(orientation='vertical', padding=10, spacing=6)
        paint_bg(box, Theme.BG_DARK, border=Theme.PRIMARY, border_width=2)
        view.add_widget(box)

        # Top bar — title + buttons
        head = BoxLayout(orientation='horizontal', size_hint=(1, None),
                          height=50, spacing=8)
        head.add_widget(Label(
            text='[size=22][b][color=00d4ff]'
                 'D Y N O   C H A R T[/color][/b][/size]',
            markup=True, halign='left', valign='middle', size_hint=(0.5, 1)))
        head.children[0].bind(size=lambda l, s: setattr(l, 'text_size', s))
        head.add_widget(Label(text='', size_hint=(0.2, 1)))
        btn_png = RacingButton('save png', primary=True, font_size=15,
                                 size_hint=(0.15, 1))
        head.add_widget(btn_png)
        btn_close = RacingButton('close', danger=True, font_size=15,
                                   size_hint=(0.15, 1))
        btn_close.bind(on_release=lambda *a: view.dismiss())
        head.add_widget(btn_close)
        box.add_widget(head)

        # Stage = chart with stats overlay floating on top-left
        stage = FloatLayout(size_hint=(1, 1))
        box.add_widget(stage)

        # Stats overlay label state — captured here so the on_cursor
        # callback can update it without poking at attributes set later.
        peak_hp_txt = self.peak_hp_lbl.text  # current visible value
        peak_tq_txt = self.peak_tq_lbl.text

        def _stats_text(cursor=None):
            lines = [
                f'[size=18][b][color=00d4ff]PUP-SK GARAGE — DYNO[/color][/b][/size]',
                f'[size=15][color=99aacc]PEAK[/color]  '
                f'[color={HP_HEX}]{peak_hp_txt} HP[/color]   '
                f'[color={TQ_HEX}]{peak_tq_txt} Nm[/color][/size]',
            ]
            if cursor and not cursor.get('no_data'):
                afr_s = (f'{cursor["afr"]:.1f}'
                          if cursor.get('afr') else '--')
                lines.append(
                    f'[size=14][color=99aacc]CURSOR[/color]  '
                    f'[color=ffffff]{int(cursor["rpm"])} RPM[/color]  '
                    f'[color={HP_HEX}]{cursor["hp"]:.1f} HP[/color]  '
                    f'[color={TQ_HEX}]{cursor["tq"]:.1f} Nm[/color]  '
                    f'[color={AFR_HEX}]{afr_s} AFR[/color]  '
                    f'[color=ffffff]{cursor["speed"]:.0f} km/h[/color]'
                    f'[/size]')
            elif cursor and cursor.get('no_data'):
                lines.append(
                    f'[size=14][color=99aacc]CURSOR[/color]  '
                    f'[color=ffffff]{int(cursor["rpm"])} RPM[/color] '
                    f'[color=99aacc](ยังไม่มีข้อมูล)[/color][/size]')
            return '\n'.join(lines)

        # Big chart with its own cursor callback that updates both the
        # screen's main cursor label AND this modal's stats overlay.
        def _modal_cursor(info):
            try: self._on_cursor(info)
            except Exception: pass
            stats.text = _stats_text(info)

        big = DynoChartCanvas(on_cursor=_modal_cursor, size_hint=(1, 1))
        big.runs       = list(self.chart.runs)
        big.run_afrs   = list(self.chart.run_afrs)
        big.live_run   = self.chart.live_run
        big.live_afrs  = list(self.chart.live_afrs or [])
        big.show_hp    = self.chart.show_hp
        big.show_tq    = self.chart.show_tq
        big.show_afr   = self.chart.show_afr
        big.rpm_min    = self.chart.rpm_min
        big.rpm_max    = self.chart.rpm_max
        big.redline    = self.chart.redline
        stage.add_widget(big)

        # Stats overlay — top-left, in its own dark box so the chart's
        # top accent line / grid don't cut through the text.  Wrapped in
        # a BoxLayout that we paint with a semi-transparent dark fill.
        stats_box = BoxLayout(
            orientation='vertical',
            size_hint=(None, None), size=(560, 122),
            pos_hint={'x': 0.005, 'top': 0.99},
            padding=(14, 10))
        paint_bg(stats_box, (0, 0, 0, 0.78), border=Theme.PRIMARY)
        stats = Label(
            text=_stats_text(), markup=True, color=Theme.TEXT,
            halign='left', valign='top')
        stats.bind(size=lambda l, s: setattr(l, 'text_size', s))
        stats.disabled = True
        stats_box.add_widget(stats)
        stats_box.disabled = True   # don't swallow taps for the chart
        stage.add_widget(stats_box)

        def _do_save_png(*_):
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            base = App.get_running_app().user_data_dir
            out_dir = os.path.join(base, 'dyno', 'png')
            try: os.makedirs(out_dir, exist_ok=True)
            except Exception: pass
            out = os.path.join(out_dir, f'dyno_{ts}.png')
            try:
                ok = stage.export_to_png(out)
            except Exception as e:
                ok = False
                print(f'[dyno png] export failed: {e}')
            if ok:
                btn_png.text = '  '.join('SAVED'.upper())
                self._set_status(f'PNG SAVED — {out}', '00ff70')
            else:
                btn_png.text = '  '.join('FAILED'.upper())
                self._set_status('PNG SAVE FAILED', 'ff173f')
        btn_png.bind(on_release=_do_save_png)

        view.open()

    def _apply_dyno_cfg(self, new_cfg):
        self._dyno_cfg.update(new_cfg)
        self._apply_chart_range(redraw=True)
        self._set_status(
            f'CHART {int(new_cfg["chart_rpm_min"])} → '
            f'{int(new_cfg["chart_rpm_max"])} RPM, '
            f'TRIG {int(new_cfg["trig_start"])} → '
            f'{int(new_cfg["trig_stop"])} RPM' +
            (f', REDLINE {int(new_cfg["redline"])}'
             if new_cfg.get("redline") else ''),
            '00d4ff')

    # ── Vehicle settings ────────────────────────────────────
    def _open_vehicle_popup(self):
        from src.screens.dyno_settings_popup import VehicleSettingsPopup
        popup = VehicleSettingsPopup(
            current_values=self._vehicle_vals,
            on_save=self._apply_vehicle_settings)
        popup.open()

    def _apply_vehicle_settings(self, values):
        self._vehicle_vals.update(values)
        from src.screens.dyno_settings_popup import _parse_tire
        circ = _parse_tire(values.get('tire', ''))
        if circ is not None:
            self._vehicle_vals['wheel_circ_m'] = circ
        circ_val = self._vehicle_vals.get('wheel_circ_m', '?')
        try: circ_txt = f'{float(circ_val):.3f}m'
        except: circ_txt = str(circ_val)
        self._set_status(
            f'VEHICLE SAVED — wheel circ {circ_txt}', '00d4ff')

    def _current_spec(self):
        spec = dyno.VehicleSpec()
        v = self._vehicle_vals
        def _f(key, default):
            try: return float(v.get(key, default))
            except: return default
        spec.mass_kg            = _f('mass',         195.0)
        spec.overall_gear_ratio = _f('gear',         11.5)
        spec.driveline_loss     = _f('driveline',    0.12)
        spec.rolling_coef       = _f('rolling',      0.018)
        spec.drag_coef          = _f('drag',         0.95)
        spec.air_density        = _f('air_density',  1.20)
        spec.frontal_area_m2    = _f('frontal_area', 0.55)
        wc = v.get('wheel_circ_m')
        try: spec.wheel_circ_m = float(wc) if wc else 1.745
        except: spec.wheel_circ_m = 1.745
        return spec

    def _set_status(self, text, color='cccccc'):
        self.status_lbl.text = f'[size=14][color={color}]{text}[/color][/size]'

    # ── Run control ─────────────────────────────────────────
    def _toggle_run(self):
        if self.state in ('armed', 'recording'):
            was_rec = (self.state == 'recording')
            self.state = 'idle'
            self.btn_run.text = '  '.join('start'.upper())
            if was_rec:
                self._process()
            else:
                self._set_status('CANCELLED', 'ffc600')
            return
        s = self._dyno_cfg['trig_start']
        e = self._dyno_cfg['trig_stop']
        if e <= s:
            self._set_status('STOP RPM MUST BE > START RPM', 'ff173f'); return
        self.samples = []
        self.state = 'armed'
        self.btn_run.text = '  '.join('cancel'.upper())
        self._set_status(f'ARMED — WAITING FOR RPM >= {int(s)}', 'ffc600')

    def _clear(self):
        self.runs = []; self.run_afrs = []; self.run_labels = []
        self.peak_hp_lbl.text = '--'; self.peak_tq_lbl.text = '--'
        self.chart.runs = []; self.chart.run_afrs = []
        self.chart.live_run = None; self.chart.live_afrs = []
        self.chart.clear_cursor()
        self.chart.redraw()
        self._set_status('CLEARED', 'cccccc')

    # ── Save / Load / Compare ───────────────────────────────
    def _on_save_run(self):
        if not self.runs:
            self._set_status('NO RUN TO SAVE', 'ff173f'); return
        run  = self.runs[-1]
        afrs = self.run_afrs[-1]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        def _save(path):
            spec = self._current_spec()
            data = {
                'version':    1,
                'created':    datetime.now().isoformat(timespec='seconds'),
                'label':      os.path.splitext(os.path.basename(path))[0],
                'tire_size':  self._vehicle_vals.get('tire', ''),
                'spec':       getattr(spec, '__dict__', {}),
                'samples': [
                    {'t': s.t, 'rpm': s.rpm, 'speed': s.speed,
                     'accel': s.accel, 'hp': s.hp, 'torque_nm': s.torque_nm,
                     'afr': afrs[i] if i < len(afrs) else None}
                    for i, s in enumerate(run)
                ],
            }
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                self._set_status(
                    f'SAVED — {os.path.basename(path)} ({len(run)} SAMPLES)',
                    '00d4ff')
            except Exception as e:
                self._set_status(f'SAVE FAILED — {e}', 'ff173f')

        from src.widgets.file_picker import AppFilePicker
        AppFilePicker(mode='save', subdir='dyno', ext='.dyno',
                       default_filename=f'dyno_{ts}',
                       on_pick=_save, title='SAVE DYNO RUN').open()

    def _on_load_run(self):
        def _load(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                run = []
                afrs = []
                for sd in data.get('samples', []):
                    run.append(LoadedSample(
                        t        = sd.get('t', 0),
                        rpm      = sd.get('rpm', 0),
                        speed    = sd.get('speed', 0),
                        accel    = sd.get('accel', 0),
                        hp       = sd.get('hp', 0),
                        torque_nm= sd.get('torque_nm', 0),
                    ))
                    afrs.append(sd.get('afr'))
                if not run:
                    self._set_status('EMPTY FILE', 'ff173f'); return
                self.runs.append(run); self.run_afrs.append(afrs)
                label = data.get('label') or \
                        os.path.basename(path).replace('.dyno', '')
                self.run_labels.append(label)
                while len(self.runs) > 5:
                    self.runs.pop(0)
                    self.run_afrs.pop(0)
                    self.run_labels.pop(0)
                self.chart.runs = list(self.runs)
                self.chart.run_afrs = list(self.run_afrs)
                self.chart.live_run = None
                self.chart.redraw()
                try:
                    peak_hp, peak_tq = dyno.peaks(run)
                    if peak_hp: self.peak_hp_lbl.text = f'{peak_hp.hp:.1f}'
                    if peak_tq: self.peak_tq_lbl.text = f'{peak_tq.torque_nm:.1f}'
                except Exception: pass
                self._set_status(
                    f'LOADED {label} — {len(self.runs)} ON CHART', '00d4ff')
            except Exception as e:
                self._set_status(f'LOAD FAILED — {e}', 'ff173f')

        from src.widgets.file_picker import AppFilePicker
        AppFilePicker(mode='open', subdir='dyno', ext='.dyno',
                       on_pick=_load, title='LOAD DYNO RUN').open()

    def _on_compare(self):
        view = ModalView(size_hint=(0.7, 0.75),
                          background_color=(0, 0, 0, 0.7),
                          background='')
        wrap = BoxLayout(orientation='vertical', padding=(16, 12), spacing=8)
        paint_bg(wrap, Theme.BG_PANEL, border=Theme.PRIMARY, border_width=2)
        view.add_widget(wrap)
        wrap.add_widget(Label(
            text='[size=20][b][color=00d4ff]C O M P A R E   R U N S[/color][/b][/size]',
            markup=True, size_hint=(1, None), height=38,
            halign='center', valign='middle'))
        if not self.runs:
            wrap.add_widget(Label(
                text='[size=14][color=99aabb]No runs yet — do a dyno run or load a file[/color][/size]',
                markup=True))
        else:
            sv = ScrollView(bar_width=4, bar_color=Theme.PRIMARY)
            box = BoxLayout(orientation='vertical',
                             size_hint_y=None, spacing=6, padding=4)
            box.bind(minimum_height=box.setter('height'))
            sv.add_widget(box)
            wrap.add_widget(sv)
            for i, run in enumerate(self.runs):
                label = self.run_labels[i] if i < len(self.run_labels) else f'Run {i+1}'
                try:
                    peak_hp, peak_tq = dyno.peaks(run)
                    hp_s = f'{peak_hp.hp:5.1f} HP @ {int(peak_hp.rpm)}'
                    tq_s = f'{peak_tq.torque_nm:5.1f} Nm @ {int(peak_tq.rpm)}'
                except Exception:
                    hp_s = '-- HP'; tq_s = '-- Nm'
                row = BoxLayout(orientation='vertical', size_hint=(1, None),
                                  height=62, padding=(10, 6))
                paint_bg(row, Theme.BG_DARK, border=Theme.GRID)
                row.add_widget(Label(
                    text=f'[size=15][b][color=00d4ff]{label}[/color][/b][/size]',
                    markup=True, size_hint=(1, None), height=22,
                    halign='left', valign='middle'))
                row.children[0].bind(
                    size=lambda l, s: setattr(l, 'text_size', s))
                row.add_widget(Label(
                    text=f'[size=14]{hp_s}    [color=99aabb]|[/color]    {tq_s}[/size]',
                    markup=True, color=Theme.TEXT, size_hint=(1, None), height=20,
                    halign='left', valign='middle'))
                row.children[0].bind(
                    size=lambda l, s: setattr(l, 'text_size', s))
                box.add_widget(row)
        btn_close = RacingButton('close', danger=True, font_size=16,
                                   size_hint=(1, None), height=50)
        btn_close.bind(on_release=lambda *a: view.dismiss())
        wrap.add_widget(btn_close)
        view.open()

    # ── Process completed run ───────────────────────────────
    def _process(self):
        if len(self.samples) < 5:
            self._set_status(f'TOO FEW SAMPLES ({len(self.samples)})', 'ff173f')
            return
        spec = self._current_spec()
        ts = [s[0] for s in self.samples]
        rpms = [s[1] for s in self.samples]
        afrs = [s[2] for s in self.samples]
        all_s = dyno.compute_run(ts, rpms, spec)
        i0, i1 = dyno.best_run_window(all_s)
        run = all_s[i0:i1]; afr_run = afrs[i0:i1]
        if not run:
            self._set_status('NO VALID PULL WINDOW', 'ff173f'); return
        self.runs.append(run); self.run_afrs.append(afr_run)
        self.run_labels.append(f'Run {len(self.runs)}')
        if len(self.runs) > 5:
            self.runs.pop(0); self.run_afrs.pop(0); self.run_labels.pop(0)
        self.chart.runs = list(self.runs)
        self.chart.run_afrs = list(self.run_afrs)
        self.chart.live_run = None
        self.chart.live_afrs = []
        # Chart RPM range comes from the dedicated CHART RPM fields,
        # not from the trigger thresholds.
        self._apply_chart_range(redraw=False)
        self.chart.redraw()
        peak_hp, peak_tq = dyno.peaks(run)
        if peak_hp:
            self.peak_hp_lbl.text = f'{peak_hp.hp:.1f}'
        if peak_tq:
            self.peak_tq_lbl.text = f'{peak_tq.torque_nm:.1f}'
        self._set_status(f'DONE — {len(run)} SAMPLES, '
                          f'{run[-1].t - run[0].t:.1f} S', '00ff70')

    # ── Live data feed ──────────────────────────────────────
    def feed(self, d):
        if d is None: return
        rpm = getattr(d, 'rpm', 0)
        afr = getattr(d, 'afr', 0)
        # Update live readout — every frame, regardless of state
        try:
            self.live_rpm.text = f'{int(rpm)}'
            self.live_afr.text = f'{afr:.1f}'
            self.live_spd.text = f'{int(getattr(d, "spd", 0))}'
            self.live_tps.text = f'{getattr(d, "tps_deg", 0):.0f}'
            self.live_ect.text = f'{int(getattr(d, "ect_c", 0))}'
        except Exception: pass

        if self.state == 'armed':
            start_rpm = self._dyno_cfg['trig_start']
            if rpm >= start_rpm:
                self.state = 'recording'
                self.t0 = time.time(); self.samples = []
                self.btn_run.text = '  '.join('stop'.upper())
                self._set_status(f'> REC @ {int(rpm)} RPM', 'ff173f')

        if self.state == 'recording':
            t = time.time() - self.t0
            self.samples.append((t, rpm, afr))
            try:
                spec = self._current_spec()
                ts = [s[0] for s in self.samples]
                rpms = [s[1] for s in self.samples]
                afrs = [s[2] for s in self.samples]
                if len(ts) >= 3:
                    live = dyno.compute_run(ts, rpms, spec)
                    self.chart.live_run = live
                    self.chart.live_afrs = afrs
                    self.chart.redraw()
            except Exception: pass
            stop_rpm = self._dyno_cfg['trig_stop']
            if rpm >= stop_rpm:
                self.state = 'idle'
                self.btn_run.text = '  '.join('start'.upper())
                self._set_status(f'AUTO-STOP @ {int(rpm)} RPM — PROCESSING',
                                  '00ff70')
                self._process()
