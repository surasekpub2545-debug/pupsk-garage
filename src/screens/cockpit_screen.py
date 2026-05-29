"""Cockpit screen — racing-style realtime dashboard."""
import os
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.graphics import Color, Rectangle, Line

from src.widgets import theme as Theme
from src.widgets.tachometer import Tachometer
from src.widgets.racing_ui import ValueCard, RacingPanel, LedNumber, paint_bg


class CockpitScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.name = 'cockpit'
        self._connected = False
        # transparent — root bg shows through

        root = BoxLayout(orientation='vertical', padding=(10, 8, 10, 6),
                          spacing=6)
        self.add_widget(root)

        # ── Top bar — title strip ───────────────────────────────────────
        topbar = BoxLayout(orientation='horizontal', size_hint=(1, None),
                            height=58, spacing=10, padding=(6, 0))
        paint_bg(topbar, Theme.BG_DARK)

        # Hamburger menu (settings)
        btn_menu = Button(
            text='[size=30][b]≡[/b][/size]', markup=True,
            background_color=(0, 0, 0, 0), color=Theme.PRIMARY,
            size_hint=(None, 1), width=62,
            halign='center', valign='middle')
        btn_menu.bind(on_release=lambda *a: self._open_menu())
        topbar.add_widget(btn_menu)

        # Wordmark logo — Label markup so it follows the accent color
        accent = Theme.primary_hex()
        title = Label(
            text=f'[size=24][b][color={accent}]PUP-SK[/color]   '
                 f'[color=ffffff]GARAGE[/color][/b][/size]',
            markup=True, size_hint=(None, 1), width=220,
            halign='left', valign='middle')
        title.bind(size=lambda lbl, sz: setattr(lbl, 'text_size', sz))
        topbar.add_widget(title)

        # Spacer fills the rest before status + connect button
        topbar.add_widget(Label(text='', size_hint=(1, 1)))

        self.conn_lbl = Label(
            text='[b]O F F L I N E[/b]', markup=True,
            color=Theme.TEXT_DIM, font_size=18,
            size_hint=(None, 1), width=170,
            halign='right', valign='middle')
        self.conn_lbl.bind(size=lambda lbl, sz: setattr(lbl, 'text_size', sz))
        topbar.add_widget(self.conn_lbl)

        self.btn_conn = Button(
            text='C O N N E C T', background_color=(0,0,0,0),
            color=Theme.BG_DARK, bold=True, font_size=17,
            size_hint=(None, 1), width=190)
        with self.btn_conn.canvas.before:
            Color(*Theme.PRIMARY)
            self.btn_conn._bg = Rectangle(pos=self.btn_conn.pos,
                                            size=self.btn_conn.size)
        self.btn_conn.bind(pos=lambda *a: setattr(self.btn_conn._bg, 'pos', self.btn_conn.pos),
                            size=lambda *a: setattr(self.btn_conn._bg, 'size', self.btn_conn.size))
        self.btn_conn.bind(on_release=lambda *a: self._on_conn_press())
        topbar.add_widget(self.btn_conn)
        root.add_widget(topbar)

        # ── Main body — 3 columns: gauges | tach | gauges ───────────────
        body = BoxLayout(orientation='horizontal', size_hint=(1, 1), spacing=6)
        root.add_widget(body)

        # LEFT GAUGES
        left_col = BoxLayout(orientation='vertical', size_hint=(0.26, 1),
                              spacing=6)
        body.add_widget(left_col)

        # CENTER (TACH + RPM PANEL)
        center = BoxLayout(orientation='vertical', size_hint=(0.48, 1),
                            spacing=6)
        body.add_widget(center)

        # Tach without panel wrap — bg image shows behind dial
        self.tach = Tachometer(size_hint=(1, 0.78))
        center.add_widget(self.tach)

        # RPM giant LED panel — use same transparency as other panels
        rpm_panel = BoxLayout(orientation='horizontal', size_hint=(1, 0.22),
                               padding=(14, 6))
        paint_bg(rpm_panel, Theme.BG_PANEL, border=Theme.GRID)
        rpm_panel.add_widget(Label(
            text='[b]R P M[/b]', markup=True,
            color=Theme.TEXT_DIM, font_size=20,
            size_hint=(0.3, 1), halign='left', valign='middle'))
        rpm_panel.children[0].bind(size=lambda lbl, sz: setattr(lbl, 'text_size', sz))
        self.rpm_big = LedNumber('0', color=Theme.PRIMARY, font_size=74,
                                   size_hint=(0.7, 1))
        rpm_panel.add_widget(self.rpm_big)
        center.add_widget(rpm_panel)

        # RIGHT GAUGES
        right_col = BoxLayout(orientation='vertical', size_hint=(0.26, 1),
                               spacing=6)
        body.add_widget(right_col)

        # 8 cards distributed (4 left, 4 right)
        self.cards = {}
        specs = [
            ('TPS',  'TPS',   '%',     Theme.PRIMARY),
            ('ECT',  'ECT',   'C',     Theme.ACCENT),
            ('IAT',  'IAT',   'C',     Theme.ACCENT),
            ('SPD',  'SPEED', 'KMH',   Theme.PRIMARY),
            ('INJ',  'INJ',   'MS',    Theme.PRIMARY),
            ('IGN',  'SPARK', 'BTDC',  Theme.WARNING),
            ('MAP',  'MAP',   'KPA',   Theme.ACCENT),
            ('AFR',  'AFR',   '',      Theme.WARNING),
        ]
        for i, (k, t, u, c) in enumerate(specs):
            card = ValueCard(t, u, color=c)
            self.cards[k] = card
            (left_col if i < 4 else right_col).add_widget(card)

    def update_data(self, d):
        if d is None: return
        try:
            self.tach.set_value(d.rpm)
            self.rpm_big.text = f'{int(d.rpm)}'
            self.cards['TPS'].set_value(f'{d.tps_deg:.1f}')
            self.cards['ECT'].set_value(f'{d.ect_c:.0f}')
            self.cards['IAT'].set_value(f'{d.iat_c:.0f}')
            self.cards['SPD'].set_value(f'{d.spd}')
            self.cards['INJ'].set_value(f'{d.injector:.2f}')
            self.cards['IGN'].set_value(f'{d.ig_deg:.1f}')
            self.cards['MAP'].set_value(f'{d.map_kpa}')
            self.cards['AFR'].set_value(f'{d.afr:.1f}')
            # If GPS isn't active (desktop dev), fall back to ECU speed
            # for the dial center display
            try:
                gps = getattr(self.app, 'gps', None)
                if gps is None or not gps.active:
                    self.tach.set_speed(d.spd)
            except Exception: pass
        except Exception: pass

    def set_connection_status(self, connected: bool, name: str = ''):
        self._connected = connected
        if connected:
            self.conn_lbl.text = f'[b][color=00ff70]L I V E[/color][/b]'
            self.conn_lbl.color = (1, 1, 1, 1)
            self.btn_conn.text = 'D I S C O N N E C T'
            self.btn_conn._bg.rgba = None
            self.btn_conn.canvas.before.clear()
            with self.btn_conn.canvas.before:
                Color(*Theme.DANGER)
                self.btn_conn._bg = Rectangle(pos=self.btn_conn.pos,
                                                size=self.btn_conn.size)
            self.btn_conn.color = (1, 1, 1, 1)
        else:
            self.conn_lbl.text = '[b]O F F L I N E[/b]'
            self.conn_lbl.color = Theme.TEXT_DIM
            self.btn_conn.text = 'C O N N E C T'
            self.btn_conn.canvas.before.clear()
            with self.btn_conn.canvas.before:
                Color(*Theme.PRIMARY)
                self.btn_conn._bg = Rectangle(pos=self.btn_conn.pos,
                                                size=self.btn_conn.size)
            self.btn_conn.color = Theme.BG_DARK

    def _on_conn_press(self):
        if self._connected:
            self.app.on_disconnect_request()
        else:
            self.app._prev_screen = self.app.sm.current
            self.app.sm.current = 'connect'

    def _open_menu(self):
        self.app.open_menu()
