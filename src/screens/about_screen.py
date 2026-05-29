"""About screen — logo, version, features, credits."""
import os
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.scrollview import ScrollView

from src.widgets import theme as Theme
from src.widgets.racing_ui import paint_bg, RacingButton

APP_VERSION = '1.0.0'


class AboutScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.name = 'about'

        root = BoxLayout(orientation='vertical', padding=(14, 10), spacing=8)
        self.add_widget(root)

        # Header bar
        topbar = BoxLayout(orientation='horizontal', size_hint=(1, None),
                            height=56, spacing=8, padding=(10, 4))
        paint_bg(topbar, Theme.BG_DARK)
        btn_back = RacingButton('back', size_hint=(0.18, 1), font_size=14)
        btn_back.bind(on_release=lambda *a: self._go_back())
        topbar.add_widget(btn_back)
        title = Label(
            text='[size=22][b][color=00d4ff]A B O U T[/color][/b][/size]',
            markup=True, halign='center', valign='middle',
            size_hint=(0.64, 1))
        title.bind(size=lambda l, s: setattr(l, 'text_size', s))
        topbar.add_widget(title)
        topbar.add_widget(Label(text='', size_hint=(0.18, 1)))
        root.add_widget(topbar)

        # Scrollable body
        sv = ScrollView(bar_width=4, bar_color=Theme.PRIMARY)
        body = BoxLayout(orientation='vertical', size_hint_y=None,
                          padding=(20, 16), spacing=14)
        body.bind(minimum_height=body.setter('height'))
        sv.add_widget(body)
        root.add_widget(sv)

        # Wordmark — Label so it follows the accent color
        accent = Theme.primary_hex()
        body.add_widget(Label(
            text=f'[size=46][b][color={accent}]PUP-SK[/color]   '
                 f'[color=ffffff]GARAGE[/color][/b][/size]',
            markup=True, size_hint=(1, None), height=70,
            halign='center', valign='middle'))

        # Version
        ver = Label(
            text=f'[size=18][b]Version {APP_VERSION}[/b][/size]',
            markup=True, size_hint=(1, None), height=34,
            color=Theme.TEXT, halign='center', valign='middle')
        ver.bind(size=lambda l, s: setattr(l, 'text_size', s))
        body.add_widget(ver)

        # Tagline
        desc = Label(
            text=('[size=14][color=99aaccff]'
                  'Honda ECU Cockpit — Race-grade live dashboard\n'
                  'for Honda K-Line ECUs via Super Connext BLE box.'
                  '[/color][/size]'),
            markup=True, size_hint=(1, None), height=60,
            halign='center', valign='middle')
        desc.bind(size=lambda l, s: setattr(l, 'text_size', s))
        body.add_widget(desc)

        # Features
        body.add_widget(self._section('FEATURES'))
        for feat in [
            '> Realtime ECU dashboard (RPM, TPS, ECT, IAT, INJ, IGN, MAP, AFR)',
            '> GPS speed display in tachometer center',
            '> AFR target heatmap (TunerPro-style)',
            '> Dyno auto-recording + Save / Load / Compare runs',
            '> Trends / Live charts',
            '> DTC read & clear (47 Honda codes)',
            '> Custom accent color & background image',
        ]:
            body.add_widget(self._item(feat))

        # Developer
        body.add_widget(self._section('DEVELOPER'))
        body.add_widget(self._item('Surasek (Pup) — PUP-SK Garage'))
        body.add_widget(self._item('surasekpub2545@gmail.com'))

        # Hardware
        body.add_widget(self._section('HARDWARE SUPPORTED'))
        body.add_widget(self._item('> Honda Wave 110i K-Line ECU'))
        body.add_widget(self._item('> Super Connext BLE box (HM-10 / BLE5)'))
        body.add_widget(self._item('> Android 8.0+ with Bluetooth LE'))

        # License
        body.add_widget(self._section('LICENSE'))
        body.add_widget(self._item(
            'Personal use only. Not for resale.\n'
            'Honda DTC list used for diagnostic display only.\n'
            'Use at your own risk — author is not responsible '
            'for engine damage caused by improper tuning.'))

        # Built-with
        body.add_widget(self._section('BUILT WITH'))
        body.add_widget(self._item(
            'Kivy 2.3  •  Python 3.11  •  Bleak  •  Pillow  •  Plyer'))

    def _section(self, title):
        head = BoxLayout(orientation='horizontal', size_hint=(1, None),
                          height=34, padding=(8, 0))
        paint_bg(head, Theme.BG_DARK)
        lbl = Label(
            text=f'[size=14][b]{"  ".join(title)}[/b][/size]',
            markup=True, color=Theme.PRIMARY,
            size_hint=(1, 1), halign='left', valign='middle')
        lbl.bind(size=lambda l, s: setattr(l, 'text_size', s))
        head.add_widget(lbl)
        return head

    def _item(self, text):
        lbl = Label(
            text=text, font_size=14,
            color=Theme.TEXT, size_hint=(1, None),
            halign='left', valign='top', padding=(8, 4))
        def _adjust(*a):
            lbl.text_size = (lbl.width - 16, None)
            lbl.texture_update()
            lbl.height = lbl.texture_size[1] + 8
        lbl.bind(size=_adjust)
        return lbl

    def _go_back(self):
        sm = self.app.sm
        target = getattr(self.app, '_prev_screen', 'cockpit')
        if sm.has_screen(target):
            sm.current = target
            if hasattr(self.app, 'nav') and target in self.app.nav.buttons:
                self.app.nav._on_tap(target)
