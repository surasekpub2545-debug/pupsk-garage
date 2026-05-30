"""Trends screen — racing-style scrolling strip charts."""
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView

from src.widgets import theme as Theme
from src.widgets.stripchart import StripChart
from src.widgets.racing_ui import paint_bg, RacingButton


def _rgba_to_hex(rgba):
    r, g, b = rgba[:3]
    return f'{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'


class _TapBox(BoxLayout):
    """BoxLayout that fires on_tap when the user taps it.  Inner widgets
    still see the touch first so labels/buttons inside keep working."""
    def __init__(self, on_tap, **kw):
        super().__init__(**kw)
        self._on_tap = on_tap

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        if super().on_touch_down(touch):
            return True
        try:
            self._on_tap()
        except Exception as e:
            print(f'[trends] expand cb err: {e}')
        return True


class TrendsScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.name = 'trends'

        root = BoxLayout(orientation='vertical', padding=(10, 8), spacing=6)
        self.add_widget(root)

        # Header strip
        header = BoxLayout(orientation='horizontal', size_hint=(1, None),
                            height=36, padding=(10, 4))
        paint_bg(header, Theme.BG_DARK)
        header.add_widget(Label(
            text='[size=15][b][color=00ff70]T R E N D S[/color][/b][/size]',
            markup=True, size_hint=(0.5, 1), halign='left', valign='middle'))
        header.children[0].bind(size=lambda l, s: setattr(l, 'text_size', s))
        header.add_widget(Label(
            text='[size=11]TAP A CHART TO EXPAND[/size]',
            markup=True, color=Theme.TEXT_DIM,
            size_hint=(0.5, 1), halign='right', valign='middle'))
        header.children[0].bind(size=lambda l, s: setattr(l, 'text_size', s))
        root.add_widget(header)

        # Scrollable grid of charts — 2 columns
        sv = ScrollView(bar_width=4, bar_color=Theme.PRIMARY)
        grid = GridLayout(cols=2, size_hint_y=None, spacing=6, padding=4)
        grid.bind(minimum_height=grid.setter('height'))
        sv.add_widget(grid)
        root.add_widget(sv)

        self.charts = {}            # key → mini chart
        self.value_lbls = {}        # key → header value Label
        self._chart_specs = {}      # key → spec for expand modal
        self._expanded = {}         # key → big chart instance for live update

        chart_specs = [
            ('RPM',     'RPM',   0, 12000, Theme.PRIMARY),
            ('TPS',     '%',     0, 100,   Theme.PRIMARY),
            ('ECT',     'C',     0, 130,   Theme.WARNING),
            ('IAT',     'C',     0, 80,    Theme.ACCENT),
            ('MAP',     'KPA',   0, 110,   Theme.ACCENT),
            ('INJ',     'MS',    0, 18,    Theme.PRIMARY),
            ('IGN',     'BTDC',  -10, 50,  Theme.WARNING),
            ('AFR',     'AFR',   10, 20,   Theme.WARNING),
            ('SPD',     'KMH',   0, 160,   Theme.PRIMARY),
        ]
        for key, units, lo, hi, color in chart_specs:
            self._chart_specs[key] = (units, lo, hi, color)
            wrap = _TapBox(
                on_tap=lambda k=key: self._expand_chart(k),
                orientation='vertical', size_hint=(1, None),
                height=160, spacing=0)
            # Header row
            head = BoxLayout(orientation='horizontal', size_hint=(1, None),
                              height=22, padding=(8, 0))
            paint_bg(head, Theme.BG_DARK)
            title_lbl = Label(text=f'[b]{"  ".join(key)}[/b]',
                               markup=True, color=color, font_size=12,
                               size_hint=(0.5, 1),
                               halign='left', valign='middle')
            title_lbl.bind(size=lambda l, s: setattr(l, 'text_size', s))
            head.add_widget(title_lbl)
            val_lbl = Label(text='--', color=color, bold=True, font_size=14,
                             size_hint=(0.4, 1),
                             halign='right', valign='middle')
            val_lbl.bind(size=lambda l, s: setattr(l, 'text_size', s))
            head.add_widget(val_lbl)
            u_lbl = Label(text=units, color=Theme.TEXT_MUTED, font_size=10,
                           size_hint=(0.1, 1),
                           halign='right', valign='middle')
            u_lbl.bind(size=lambda l, s: setattr(l, 'text_size', s))
            head.add_widget(u_lbl)
            wrap.add_widget(head)
            # Chart — disable StripChart's built-in tap-to-zoom so our
            # _TapBox catches the touch and opens the richer modal below.
            c = StripChart(title=key, units=units, low=lo, high=hi,
                           color=color, zoomable=False, size_hint=(1, 1))
            wrap.add_widget(c)
            grid.add_widget(wrap)
            self.charts[key] = c
            self.value_lbls[key] = val_lbl

    # ── Expand modal ─────────────────────────────────────────
    def _expand_chart(self, key):
        units, lo, hi, color = self._chart_specs[key]
        color_hex = _rgba_to_hex(color)

        view = ModalView(size_hint=(0.95, 0.92),
                          background_color=(0, 0, 0, 0),
                          background='', auto_dismiss=True)
        box = BoxLayout(orientation='vertical', padding=14, spacing=8)
        paint_bg(box, Theme.BG_DARK, border=Theme.PRIMARY, border_width=2)
        view.add_widget(box)

        # Header
        head = BoxLayout(orientation='horizontal', size_hint=(1, None),
                          height=52, spacing=10)
        title = Label(
            text=f'[size=22][b][color={color_hex}]'
                 f'{"  ".join(key)}[/color][/b][/size]   '
                 f'[size=14][color=99aacc]{units}[/color][/size]',
            markup=True, halign='left', valign='middle',
            size_hint=(0.7, 1))
        title.bind(size=lambda l, s: setattr(l, 'text_size', s))
        head.add_widget(title)
        self._expanded_value_lbl = Label(
            text=self.value_lbls[key].text, color=color, bold=True,
            font_size=34, size_hint=(0.2, 1),
            halign='right', valign='middle')
        self._expanded_value_lbl.bind(
            size=lambda l, s: setattr(l, 'text_size', s))
        head.add_widget(self._expanded_value_lbl)
        btn_close = RacingButton('close', danger=True, font_size=14,
                                   size_hint=(0.1, 1))
        head.add_widget(btn_close)
        box.add_widget(head)

        # Big chart
        big = StripChart(title=key, units=units, low=lo, high=hi,
                          color=color, size_hint=(1, 1))
        # Seed with the small chart's history so the expanded view starts
        # showing data immediately instead of from blank.
        try:
            src_vals = getattr(self.charts[key], '_values', None) \
                or getattr(self.charts[key], 'values', None) \
                or getattr(self.charts[key], '_data', None)
            if src_vals:
                for v in list(src_vals):
                    big.push(v)
        except Exception: pass
        box.add_widget(big)

        # Track for live updates
        self._expanded[key] = big

        def _close(*a):
            self._expanded.pop(key, None)
            view.dismiss()
        btn_close.bind(on_release=_close)
        view.bind(on_dismiss=lambda *a: self._expanded.pop(key, None))
        view.open()

    # ── Live data ────────────────────────────────────────────
    def push_data(self, d):
        if d is None: return
        try:
            values = {
                'RPM': (d.rpm,       f'{int(d.rpm)}'),
                'TPS': (d.tps_deg,   f'{d.tps_deg:.1f}'),
                'ECT': (d.ect_c,     f'{d.ect_c:.0f}'),
                'IAT': (d.iat_c,     f'{d.iat_c:.0f}'),
                'MAP': (d.map_kpa,   f'{d.map_kpa}'),
                'INJ': (d.injector,  f'{d.injector:.2f}'),
                'IGN': (d.ig_deg,    f'{d.ig_deg:.1f}'),
                'AFR': (d.afr,       f'{d.afr:.1f}'),
                'SPD': (d.spd,       f'{d.spd}'),
            }
            for key, (raw, text) in values.items():
                self.charts[key].push(raw)
                self.value_lbls[key].text = text
                # Also feed expanded view if open
                big = self._expanded.get(key)
                if big is not None:
                    big.push(raw)
                    if hasattr(self, '_expanded_value_lbl') and \
                       self._expanded_value_lbl is not None:
                        # Only update the readout for the currently
                        # expanded chart's key — cheap heuristic: the
                        # last call wins
                        if list(self._expanded.keys())[-1] == key:
                            self._expanded_value_lbl.text = text
        except Exception: pass

    def reset_all(self):
        for c in self.charts.values(): c.reset()
        for c in self._expanded.values(): c.reset()

    def on_enter(self, *a):
        from kivy.clock import Clock
        def _redraw(*x):
            for c in self.charts.values():
                try: c._redraw()
                except Exception: pass
        Clock.schedule_once(_redraw, 0)
