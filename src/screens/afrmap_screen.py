"""AFR Map screen — racing-style 2D heatmap with view-mode toggle."""
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.graphics import Color, Rectangle

from src.widgets import theme as Theme
from src.widgets.afr_heatmap import AfrHeatmap
from src.widgets.racing_ui import paint_bg, RacingButton


class AfrMapScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.name = 'afrmap'
        # transparent — root bg shows through

        root = BoxLayout(orientation='vertical', padding=(10, 8), spacing=6)
        self.add_widget(root)

        # Header strip
        head = BoxLayout(orientation='horizontal', size_hint=(1, None),
                          height=36, padding=(10, 4))
        paint_bg(head, Theme.BG_DARK)
        head.add_widget(Label(
            text='[size=15][b][color=00ff70]A F   M A P[/color][/b][/size]',
            markup=True, size_hint=(0.5, 1), halign='left', valign='middle'))
        head.children[0].bind(size=lambda l, s: setattr(l, 'text_size', s))
        head.add_widget(Label(
            text='[size=11]RPM × TPS HEATMAP[/size]',
            markup=True, color=Theme.TEXT_DIM,
            size_hint=(0.5, 1), halign='right', valign='middle'))
        head.children[0].bind(size=lambda l, s: setattr(l, 'text_size', s))
        root.add_widget(head)

        # Controls row
        ctrl = BoxLayout(orientation='horizontal', size_hint=(1, None),
                          height=44, spacing=6)
        paint_bg(ctrl, Theme.BG_PANEL, border=Theme.GRID)

        ctrl.add_widget(Label(
            text='[size=11][b]V I E W[/b][/size]',
            markup=True, color=Theme.TEXT_DIM,
            size_hint=(0.12, 1), halign='center', valign='middle'))
        self.view_spinner = Spinner(
            text='Most Recent Sample',
            values=['Most Recent Sample', 'History Average',
                    'History Maximum', 'History Minimum',
                    'History Sample Count'],
            size_hint=(0.43, 1),
            background_normal='', background_color=Theme.BG_DARK,
            color=Theme.PRIMARY, font_size=12, bold=True)
        self.view_spinner.bind(text=lambda spn, val: self.heatmap.set_view_mode(val))
        ctrl.add_widget(self.view_spinner)

        ctrl.add_widget(Label(
            text='[size=11][b]T A R G E T[/b][/size]',
            markup=True, color=Theme.TEXT_DIM,
            size_hint=(0.13, 1), halign='center', valign='middle'))
        self.target_input = TextInput(
            text='14.7', size_hint=(0.14, 1),
            background_color=Theme.BG_DARK,
            foreground_color=Theme.PRIMARY,
            cursor_color=Theme.PRIMARY,
            font_size=15, halign='center', multiline=False)
        self.target_input.bind(text=lambda inp, val: self._target_changed(val))
        ctrl.add_widget(self.target_input)

        btn_reset = RacingButton('reset', danger=True, font_size=11,
                                   size_hint=(0.18, 1))
        btn_reset.bind(on_release=lambda *a: self.heatmap.reset())
        ctrl.add_widget(btn_reset)
        root.add_widget(ctrl)

        # Heatmap
        self.heatmap = AfrHeatmap(size_hint=(1, 1))
        root.add_widget(self.heatmap)

        # Legend strip
        leg = BoxLayout(orientation='horizontal', size_hint=(1, None),
                         height=24, padding=(8, 0), spacing=12)
        paint_bg(leg, Theme.BG_DARK)
        for col_hex, txt in [('00d97a', '0.3'),
                              ('7ec946', '0.6'),
                              ('d9c200', '1.0'),
                              ('e08930', '1.5'),
                              ('d95a30', '2.5'),
                              ('e0303a', '> 2.5')]:
            l = Label(text=f'[size=11][color={col_hex}]■[/color] '
                            f'[color=cccccc]{txt}[/color][/size]',
                       markup=True, halign='center', valign='middle')
            leg.add_widget(l)
        root.add_widget(leg)

    def _target_changed(self, val):
        try:
            v = float(val)
            self.heatmap.set_target(v)
        except: pass

    def push_data(self, d):
        if d is None: return
        self.heatmap.sample(d.rpm, d.tps_deg, d.afr)
        self.heatmap.redraw()

    def on_enter(self, *a):
        from kivy.clock import Clock
        Clock.schedule_once(lambda dt: self.heatmap.redraw(), 0)
