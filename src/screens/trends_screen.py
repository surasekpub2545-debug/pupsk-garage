"""Trends screen — racing-style scrolling strip charts."""
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label

from src.widgets import theme as Theme
from src.widgets.stripchart import StripChart
from src.widgets.racing_ui import paint_bg


class TrendsScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.name = 'trends'
        # transparent — root bg shows through

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

        self.charts = {}
        self.value_lbls = {}
        chart_specs = [
            ('RPM',     'RPM',   0, 12000, Theme.PRIMARY),
            ('TPS',     '%',     0, 100,   Theme.PRIMARY),
            ('ECT',     'C',    0, 130,   Theme.WARNING),
            ('IAT',     'C',    0, 80,    Theme.ACCENT),
            ('MAP',     'KPA',   0, 110,   Theme.ACCENT),
            ('INJ',     'MS',    0, 18,    Theme.PRIMARY),
            ('IGN',     'BTDC',  -10, 50,  Theme.WARNING),
            ('AFR',     'AFR',   10, 20,   Theme.WARNING),
            ('SPD',     'KMH',   0, 160,   Theme.PRIMARY),
        ]
        for key, units, lo, hi, color in chart_specs:
            # Wrapper with header strip + chart
            wrap = BoxLayout(orientation='vertical', size_hint=(1, None),
                              height=160, spacing=0)
            # Header row inside the wrap
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
            # Chart
            c = StripChart(title=key, units=units, low=lo, high=hi,
                           color=color, size_hint=(1, 1))
            wrap.add_widget(c)
            grid.add_widget(wrap)
            self.charts[key] = c
            self.value_lbls[key] = val_lbl

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
        except Exception: pass

    def reset_all(self):
        for c in self.charts.values(): c.reset()

    def on_enter(self, *a):
        from kivy.clock import Clock
        def _redraw(*x):
            for c in self.charts.values():
                try: c._redraw()
                except Exception: pass
        Clock.schedule_once(_redraw, 0)
