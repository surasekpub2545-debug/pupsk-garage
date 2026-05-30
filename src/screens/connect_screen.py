"""Connect screen — racing-style BLE scan & pair."""
import asyncio
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle

from src.widgets import theme as Theme
from src.widgets.racing_ui import paint_bg, RacingButton
from src import app_config


class ConnectScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.name = 'connect'
        # transparent — root bg shows through

        root = BoxLayout(orientation='vertical', padding=(14, 10), spacing=8)
        self.add_widget(root)

        # ── Top header bar ─────────────────────────────────────────────
        topbar = BoxLayout(orientation='horizontal', size_hint=(1, None),
                            height=44, spacing=8, padding=(10, 4))
        paint_bg(topbar, Theme.BG_DARK)
        btn_back = RacingButton('back', size_hint=(0.18, 1), font_size=12)
        btn_back.bind(on_release=lambda *a: self._go_back())
        topbar.add_widget(btn_back)

        title = Label(
            text='[size=15][b][color=00ff70]B L E[/color]   '
                 '[color=ffffff]P A I R I N G[/color][/b][/size]',
            markup=True, halign='center', valign='middle',
            size_hint=(0.64, 1))
        title.bind(size=lambda l, s: setattr(l, 'text_size', s))
        topbar.add_widget(title)
        # Spacer for symmetry
        topbar.add_widget(Label(text='', size_hint=(0.18, 1)))
        root.add_widget(topbar)

        # Sub instruction
        sub = Label(text='[size=11]CONNECT TO SUPER CONNEXT BLE BOX[/size]',
                     markup=True, color=Theme.TEXT_DIM,
                     size_hint=(1, None), height=20,
                     halign='center', valign='middle')
        sub.bind(size=lambda l, s: setattr(l, 'text_size', s))
        root.add_widget(sub)

        # Last device shortcut
        self.last_row = BoxLayout(orientation='vertical', size_hint=(1, None),
                                   height=0, spacing=4)
        root.add_widget(self.last_row)
        self._refresh_last_device()

        # Scan button
        self.btn_scan = RacingButton('scan for ble devices', primary=True,
                                       size_hint=(1, None), height=56,
                                       font_size=16)
        self.btn_scan.bind(on_release=lambda *a: self._on_scan())
        root.add_widget(self.btn_scan)

        # Filter toggle — by default show ONLY likely Super Connext boxes
        self._show_all = False
        self._last_scan = []
        self.btn_filter = Button(
            text='[size=12][color=99aacc]'
                 'แสดง: เฉพาะที่น่าจะใช่  (แตะเพื่อแสดงทั้งหมด)'
                 '[/color][/size]',
            markup=True, background_color=(0, 0, 0, 0),
            size_hint=(1, None), height=30,
            halign='center', valign='middle')
        self.btn_filter.bind(size=lambda l, s: setattr(l, 'text_size', s))
        self.btn_filter.bind(on_release=lambda *a: self._toggle_filter())
        root.add_widget(self.btn_filter)

        # Status line
        self.status_lbl = Label(text='[size=12]TAP SCAN TO FIND DEVICES[/size]',
                                 markup=True, color=Theme.TEXT_DIM,
                                 size_hint=(1, None), height=24,
                                 halign='center')
        self.status_lbl.bind(size=lambda l, s: setattr(l, 'text_size', s))
        root.add_widget(self.status_lbl)

        # Device list
        sv = ScrollView(bar_width=4, bar_color=Theme.PRIMARY)
        self.dev_box = BoxLayout(orientation='vertical', size_hint_y=None,
                                   spacing=6, padding=4)
        self.dev_box.bind(minimum_height=self.dev_box.setter('height'))
        sv.add_widget(self.dev_box)
        root.add_widget(sv)

    def on_pre_enter(self, *a):
        self._refresh_last_device()

    def _refresh_last_device(self):
        self.last_row.clear_widgets()
        last = app_config.get_last_device()
        if not last.get('address'):
            self.last_row.height = 0; return
        self.last_row.height = 70
        addr = last['address']; name = last.get('name', '(unnamed)')
        btn = Button(
            text=f'[size=12][b]» RECONNECT TO LAST DEVICE[/b][/size]\n'
                 f'[size=11]{name}   {addr}[/size]',
            markup=True, background_color=(0, 0, 0, 0),
            color=Theme.BG_DARK, halign='center', valign='middle',
            size_hint=(1, 1))
        with btn.canvas.before:
            Color(*Theme.PRIMARY)
            btn._bg = Rectangle(pos=btn.pos, size=btn.size)
        btn.bind(pos=lambda *a: setattr(btn._bg, 'pos', btn.pos),
                  size=lambda *a: setattr(btn._bg, 'size', btn.size))
        btn.bind(on_release=lambda *a, ad=addr, nm=name: self._connect_to(ad, nm))
        self.last_row.add_widget(btn)

    def _go_back(self):
        sm = self.app.sm
        target = getattr(self.app, '_prev_screen', 'cockpit')
        if sm.has_screen(target):
            sm.current = target
            self.app.nav._on_tap(target)

    def _on_scan(self):
        self.status_lbl.text = '[size=12][color=ffc600]SCANNING (6 SEC)…[/color][/size]'
        self.btn_scan.disabled = True
        self.dev_box.clear_widgets()
        self.app.submit_async(self._scan_async())

    async def _scan_async(self):
        try:
            devices = await self.app.ble.scan(timeout=6.0)
        except Exception as e:
            Clock.schedule_once(
                lambda dt, m=str(e): self._set_status(f'SCAN ERROR — {m}'), 0)
            return
        Clock.schedule_once(lambda dt: self._render_devices(devices), 0)

    def _set_status(self, text):
        self.status_lbl.text = f'[size=12]{text}[/size]'
        self.btn_scan.disabled = False

    def _toggle_filter(self):
        self._show_all = not self._show_all
        if self._show_all:
            self.btn_filter.text = ('[size=12][color=99aacc]'
                'แสดง: ทั้งหมด  (แตะเพื่อกรองเฉพาะที่น่าจะใช่)'
                '[/color][/size]')
        else:
            self.btn_filter.text = ('[size=12][color=99aacc]'
                'แสดง: เฉพาะที่น่าจะใช่  (แตะเพื่อแสดงทั้งหมด)'
                '[/color][/size]')
        self._render_devices(self._last_scan)

    def _render_devices(self, devices):
        self.btn_scan.disabled = False
        self._last_scan = devices
        self.dev_box.clear_widgets()
        if not devices:
            self.status_lbl.text = ('[size=12][color=ff173f]'
                                      'NO DEVICES FOUND — CHECK BLUETOOTH[/color][/size]')
            return

        # Filter: default = only named + relevant devices.  When the user
        # taps "show all" we list every BLE device the radio saw.
        if self._show_all:
            shown = devices
        else:
            shown = [d for d in devices
                     if d.get('relevant') or
                     (d.get('name') and d['name'] != '(unnamed)')]
            # If filtering hid everything, fall back to showing all so the
            # user isn't staring at a blank list.
            if not shown:
                shown = devices

        self.status_lbl.text = (
            f'[size=12]FOUND {len(devices)} DEVICE(S)'
            + (f' — SHOWING {len(shown)}'
               if len(shown) != len(devices) else '')
            + '[/size]')
        for d in shown:
            btn = self._make_device_row(d)
            self.dev_box.add_widget(btn)

    def _make_device_row(self, d):
        relevant = d.get('relevant', False)
        rssi = d.get('rssi')
        rssi_s = f'   RSSI {rssi}' if rssi is not None else ''
        marker = '●' if relevant else ' '
        name = d["name"]; addr = d["address"]
        text = (f'[size=14][b]{marker} {name.upper()}[/b][/size]\n'
                f'[size=11]{addr}{rssi_s}[/size]')
        b = Button(text=text, markup=True,
                   size_hint=(1, None), height=72,
                   background_color=(0,0,0,0),
                   color=(Theme.BG_DARK if relevant else Theme.TEXT),
                   halign='left', valign='middle')
        with b.canvas.before:
            if relevant:
                Color(*Theme.PRIMARY)
            else:
                Color(*Theme.BG_PANEL)
            b._bg = Rectangle(pos=b.pos, size=b.size)
            # Carbon outline
            from kivy.graphics import Line
            Color(*Theme.GRID)
            b._outline = Line(rectangle=(b.x, b.y, b.width, b.height), width=1)
        def _resize(*a):
            b._bg.pos = b.pos; b._bg.size = b.size
            b._outline.rectangle = (b.x, b.y, b.width, b.height)
        b.bind(pos=_resize, size=_resize)
        b.bind(text_size=lambda *a: None)
        b.bind(size=lambda btn, sz: setattr(btn, 'text_size',
                                              (sz[0] - 20, sz[1])))
        b.bind(on_release=lambda *a, ad=d['address'], nm=d['name']:
                          self._connect_to(ad, nm))
        return b

    def _connect_to(self, address, name):
        self.status_lbl.text = (f'[size=12][color=ffc600]'
                                  f'CONNECTING TO {name.upper()}…[/color][/size]')
        self.btn_scan.disabled = True
        self.app.submit_async(self._connect_async(address, name))

    async def _connect_async(self, address, name):
        ok = await self.app.ble.connect(address)
        def after(dt):
            log = getattr(self.app.ble, 'log_lines', []) or []
            if ok:
                app_config.set_last_device(address, name)
                # Show the log briefly then navigate so the user can see
                # the box layout even on a successful connect.
                self._show_log('CONNECTED', log, color='00ff70')
                Clock.schedule_once(
                    lambda dt2: self.app.on_connected(address, name), 1.5)
            else:
                self._show_log('CONNECTION FAILED', log, color='ff173f')
                self.btn_scan.disabled = False
        Clock.schedule_once(after, 0)

    def _show_log(self, header, log_lines, color='ffc600'):
        self.status_lbl.text = (f'[size=12][color={color}]{header}'
                                  f'  (screenshot this)[/color][/size]')
        self.dev_box.clear_widgets()
        body = '\n'.join(log_lines) if log_lines else '(no log)'
        lbl = Label(
            text=f'[size=12][color=cccccc]{body}[/color][/size]',
            markup=True, size_hint=(1, None),
            halign='left', valign='top')
        lbl.bind(width=lambda l, w: setattr(l, 'text_size', (w - 20, None)))
        lbl.bind(texture_size=lambda l, ts: setattr(l, 'height', ts[1] + 10))
        self.dev_box.add_widget(lbl)
