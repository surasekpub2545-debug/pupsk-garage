"""Racing bottom navigation — sharp tabs with accent bar on active."""
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle, Line

from . import theme as Theme


class NavTab(Button):
    """Single tab — racing style with top accent line on active."""
    def __init__(self, code, label, on_press_cb, **kw):
        super().__init__(
            text='[size=20][b]  ' + '  '.join(label.upper()) + '  [/b][/size]',
            markup=True,
            background_color=(0, 0, 0, 0),
            color=Theme.TEXT_DIM,
            font_size=17, halign='center', valign='middle',
            **kw)
        self._on_press_cb = on_press_cb
        self._active = False
        with self.canvas.before:
            # Base background — slightly different from panel bg
            Color(*Theme.BG_RACE)
            self._bg = Rectangle(pos=self.pos, size=self.size)
            # Carbon divider lines on left & right
            Color(*Theme.GRID_DIM)
            self._div_l = Line(points=[self.x, self.y, self.x, self.y + self.height], width=1)
            # Top accent (changes color on active)
            Color(*Theme.GRID_DIM)
            self._top_accent = Rectangle(
                pos=(self.x, self.y + self.height - 3),
                size=(self.width, 3))
        self.bind(pos=self._resize, size=self._resize)
        self.bind(on_release=lambda *a: self._on_press_cb())

    def _resize(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._div_l.points = [self.x, self.y, self.x, self.y + self.height]
        self._top_accent.pos = (self.x, self.y + self.height - 3)
        self._top_accent.size = (self.width, 3)

    def set_active(self, active: bool):
        self._active = active
        # Redraw with new accent color
        self.canvas.before.clear()
        with self.canvas.before:
            if active:
                Color(*Theme.BG_DARK)         # darker = "selected"
            else:
                Color(*Theme.BG_RACE)
            self._bg = Rectangle(pos=self.pos, size=self.size)
            # Carbon dividers
            Color(*Theme.GRID_DIM)
            self._div_l = Line(points=[self.x, self.y, self.x, self.y + self.height], width=1)
            # Top accent
            Color(*(Theme.PRIMARY if active else Theme.GRID_DIM))
            self._top_accent = Rectangle(
                pos=(self.x, self.y + self.height - 3),
                size=(self.width, 3))
        self.color = Theme.PRIMARY if active else Theme.TEXT_DIM


class BottomNav(BoxLayout):
    def __init__(self, screen_manager, items, on_tab=None, **kw):
        """items: list of (code, label, screen_name)
                  code is short 2-char identifier (01, 02, ...)
        """
        super().__init__(orientation='horizontal',
                          size_hint=(1, None), height=86, **kw)
        self.sm = screen_manager
        self.on_tab = on_tab
        # Panel background
        with self.canvas.before:
            Color(*Theme.BG_DARK)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *a: setattr(self._bg, 'pos', self.pos),
                  size=lambda *a: setattr(self._bg, 'size', self.size))

        self.buttons = {}
        for code, label, sname in items:
            tab = NavTab(code, label,
                          on_press_cb=lambda n=sname: self._on_tap(n))
            self.buttons[sname] = tab
            self.add_widget(tab)

    def _on_tap(self, sname):
        if self.sm.has_screen(sname):
            self.sm.current = sname
        for n, b in self.buttons.items():
            b.set_active(n == sname)
        if self.on_tab:
            self.on_tab(sname)
