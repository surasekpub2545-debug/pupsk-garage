"""Side drawer menu — opened from the hamburger button on Cockpit."""
from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, Line

from . import theme as Theme
from .racing_ui import paint_bg


class MenuItem(Button):
    """Menu row — icon + Thai label, large touch target."""
    def __init__(self, icon, label, on_pick, **kw):
        kw.setdefault('size_hint', (1, None))
        kw.setdefault('height', 64)
        kw.setdefault('background_color', (0, 0, 0, 0))
        kw.setdefault('halign', 'left')
        kw.setdefault('valign', 'middle')
        accent = Theme.primary_hex()
        super().__init__(
            text=f'[size=24][color={accent}][b]{icon}[/b][/color][/size]   '
                 f'[size=18][b]{label}[/b][/size]',
            markup=True, color=Theme.TEXT, **kw)
        self.bind(size=lambda l, s: setattr(l, 'text_size',
                                             (s[0] - 12, s[1])))
        self.bind(on_release=lambda *a: on_pick())
        with self.canvas.before:
            Color(*Theme.GRID_DIM)
            self._line = Line(points=[self.x + 8, self.y,
                                        self.x + self.width - 8, self.y],
                               width=1)
        self.bind(pos=self._resize, size=self._resize)

    def _resize(self, *a):
        self._line.points = [self.x + 8, self.y,
                              self.x + self.width - 8, self.y]


class SideMenu(ModalView):
    """Modal that shows a left-aligned drawer; tap right side to dismiss."""
    def __init__(self, app, **kw):
        kw.setdefault('size_hint', (1, 1))
        kw.setdefault('background_color', (0, 0, 0, 0))
        kw.setdefault('background', '')
        super().__init__(**kw)
        self.app = app

        root = BoxLayout(orientation='horizontal')
        self.add_widget(root)

        # Left panel ───────────────────────────────────────────────
        panel = BoxLayout(orientation='vertical', size_hint=(0.42, 1),
                          padding=(16, 16), spacing=4)
        paint_bg(panel, Theme.BG_DARK, border=Theme.PRIMARY)
        root.add_widget(panel)

        # Title — wordmark
        header = BoxLayout(orientation='horizontal',
                            size_hint=(1, None), height=70)
        accent = Theme.primary_hex()
        title = Label(
            text=f'[size=22][b][color={accent}]PUP-SK[/color]   '
                 f'[color=ffffff]GARAGE[/color][/b][/size]',
            markup=True, halign='left', valign='middle')
        title.bind(size=lambda l, s: setattr(l, 'text_size', s))
        header.add_widget(title)
        panel.add_widget(header)

        # Primary accent divider
        divider = Widget(size_hint=(1, None), height=2)
        with divider.canvas:
            Color(*Theme.PRIMARY)
            self._div_r = Rectangle(pos=divider.pos, size=divider.size)
        divider.bind(pos=lambda *a: setattr(self._div_r, 'pos', divider.pos),
                      size=lambda *a: setattr(self._div_r, 'size', divider.size))
        panel.add_widget(divider)
        panel.add_widget(Widget(size_hint=(1, None), height=8))

        # Menu items
        # ASCII-only icons — Sarabun has no glyphs for ◉ / ► so they show
        # as tofu on Android.
        items = [
            ('+', 'จัดการอุปกรณ์',          self._goto_connect),
            ('!', 'อ่านรหัสความผิดพลาด',   self._goto_dtc),
            ('>', 'ทดสอบความเร็ว',         self._goto_dyno),
            ('=', 'ตั้งค่า',                 self._goto_settings),
            ('i', 'เกี่ยวกับเรา',           self._goto_about),
        ]
        for icon, label, action in items:
            mi = MenuItem(icon, label,
                           on_pick=lambda act=action: self._pick(act))
            panel.add_widget(mi)

        # Spacer pushes footer down
        panel.add_widget(Widget())

        # Footer — version
        footer = Label(
            text='[size=11][color=99aaccff]v1.0.0[/color][/size]',
            markup=True, size_hint=(1, None), height=22,
            halign='left', valign='middle')
        footer.bind(size=lambda l, s: setattr(l, 'text_size', s))
        panel.add_widget(footer)

        # Right tap-to-dismiss area
        right = Button(text='', background_color=(0, 0, 0, 0.55),
                        size_hint=(0.58, 1))
        right.bind(on_release=lambda *a: self.dismiss())
        root.add_widget(right)

    def _pick(self, action):
        self.dismiss()
        action()

    def _goto(self, screen_name):
        self.app._prev_screen = self.app.sm.current
        if self.app.sm.has_screen(screen_name):
            self.app.sm.current = screen_name
            # If the destination is in the bottom nav, also highlight it
            if hasattr(self.app, 'nav') and \
               screen_name in self.app.nav.buttons:
                self.app.nav._on_tap(screen_name)

    def _goto_connect(self):  self._goto('connect')
    def _goto_dtc(self):       self._goto('dtc')
    def _goto_dyno(self):      self._goto('dyno')
    def _goto_settings(self):  self._goto('settings')
    def _goto_about(self):     self._goto('about')
