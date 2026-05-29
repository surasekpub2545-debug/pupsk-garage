"""
Racing-style UI helpers — angular panels, accent bars, LED panels.
"""
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle, Line
from kivy.properties import StringProperty, NumericProperty

from . import theme as Theme


def paint_bg(widget, color, border=None, border_width=1):
    """Paint flat background + optional border on a widget."""
    with widget.canvas.before:
        Color(*color)
        widget._bg_rect = Rectangle(pos=widget.pos, size=widget.size)
        if border is not None:
            Color(*border)
            widget._bg_line = Line(rectangle=(widget.x, widget.y,
                                                widget.width, widget.height),
                                    width=border_width)
    def _resize(*a):
        widget._bg_rect.pos  = widget.pos
        widget._bg_rect.size = widget.size
        if hasattr(widget, '_bg_line'):
            widget._bg_line.rectangle = (widget.x, widget.y,
                                          widget.width, widget.height)
    widget.bind(pos=_resize, size=_resize)


class RacingPanel(BoxLayout):
    """Panel with deep black background + accent top bar (carbon look)."""
    def __init__(self, accent_color=None, accent_height=3, **kw):
        kw.setdefault('orientation', 'vertical')
        kw.setdefault('padding', (10, 8))
        kw.setdefault('spacing', 4)
        super().__init__(**kw)
        self._accent = accent_color or Theme.PRIMARY
        self._accent_h = accent_height
        with self.canvas.before:
            # Panel background
            Color(*Theme.BG_PANEL)
            self._bg = Rectangle(pos=self.pos, size=self.size)
            # Carbon outline
            Color(*Theme.GRID)
            self._outline = Line(rectangle=(self.x, self.y, self.width, self.height),
                                  width=1)
            # Accent strip on top
            Color(*self._accent)
            self._accent_rect = Rectangle(
                pos=(self.x, self.y + self.height - accent_height),
                size=(self.width, accent_height))
        self.bind(pos=self._resize, size=self._resize)

    def _resize(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._outline.rectangle = (self.x, self.y, self.width, self.height)
        self._accent_rect.pos = (self.x, self.y + self.height - self._accent_h)
        self._accent_rect.size = (self.width, self._accent_h)


class HeaderLabel(Label):
    """Bold, uppercase, wide-spaced header text."""
    def __init__(self, text, color=None, **kw):
        kw.setdefault('font_size', 20)
        kw.setdefault('bold', True)
        kw.setdefault('halign', 'left')
        kw.setdefault('valign', 'middle')
        kw['color'] = color or Theme.PRIMARY
        # Letter spacing fake via thin space char
        spaced = '  '.join(text.upper())
        super().__init__(text=spaced, **kw)
        self.bind(size=lambda lbl, sz: setattr(lbl, 'text_size', sz))


class LedNumber(Label):
    """Big LED-style digital readout."""
    def __init__(self, text='0', color=None, font_size=54, **kw):
        kw.setdefault('bold', True)
        kw.setdefault('halign', 'right')
        kw.setdefault('valign', 'middle')
        kw['color'] = color or Theme.PRIMARY
        kw['font_size'] = font_size
        super().__init__(text=text, **kw)
        self.bind(size=lambda lbl, sz: setattr(lbl, 'text_size', sz))


class ValueCard(BoxLayout):
    """
    Racing value card:
      ┌─ TPS ─────────────────────┐
      │                            │
      │              23.5  %       │  ← big LED number + tiny units
      │                            │
      └────────────────────────────┘
      thin accent line on left edge
    """
    def __init__(self, title, units, color=None, **kw):
        kw.setdefault('orientation', 'vertical')
        kw.setdefault('padding', (12, 10, 12, 10))
        kw.setdefault('spacing', 2)
        super().__init__(**kw)
        self._color = color or Theme.PRIMARY

        # Background + carbon outline + colored bar on left
        with self.canvas.before:
            Color(*Theme.BG_PANEL)
            self._bg = Rectangle(pos=self.pos, size=self.size)
            Color(*Theme.GRID)
            self._outline = Line(rectangle=(self.x, self.y, self.width, self.height),
                                  width=1)
            Color(*self._color)
            self._strip = Rectangle(pos=(self.x, self.y),
                                     size=(3, self.height))
        self.bind(pos=self._resize, size=self._resize)

        # Title row (small, spaced uppercase, dim)
        title_label = Label(
            text='  '.join(title.upper()),
            font_size=15, color=Theme.TEXT_DIM, bold=True,
            size_hint=(1, None), height=20,
            halign='left', valign='top')
        title_label.bind(size=lambda lbl, sz: setattr(lbl, 'text_size', sz))
        self.add_widget(title_label)

        # Big value row (LED number + units inline)
        row = BoxLayout(orientation='horizontal', spacing=4)
        self.add_widget(row)
        self.value_lbl = LedNumber('--', color=self._color, font_size=46)
        row.add_widget(self.value_lbl)
        u = Label(text=units, color=Theme.TEXT_MUTED,
                   font_size=15, size_hint=(None, 1), width=58,
                   halign='left', valign='bottom')
        u.bind(size=lambda lbl, sz: setattr(lbl, 'text_size', sz))
        row.add_widget(u)

    def _resize(self, *a):
        self._bg.pos  = self.pos
        self._bg.size = self.size
        self._outline.rectangle = (self.x, self.y, self.width, self.height)
        self._strip.pos = (self.x, self.y)
        self._strip.size = (3, self.height)

    def set_value(self, text):
        self.value_lbl.text = text


class RacingButton(Button):
    """Flat racing-style button — sharp edges, bold uppercase, glow on hover."""
    def __init__(self, text='', primary=False, danger=False, **kw):
        if primary:
            bg = Theme.PRIMARY; fg = Theme.BG_DARK
        elif danger:
            bg = Theme.DANGER; fg = (1, 1, 1, 1)
        else:
            bg = Theme.BG_DARK; fg = Theme.PRIMARY
        super().__init__(
            text='  '.join(text.upper()),
            background_color=(0, 0, 0, 0),    # disable default tinting
            color=fg, bold=True,
            font_size=kw.pop('font_size', 18), **kw)
        self._bg_color = bg
        self._fg_color = fg
        with self.canvas.before:
            Color(*bg)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
            # Accent line at bottom
            Color(*Theme.PRIMARY if not (primary or danger) else Theme.BG_DARK)
            self._accent = Rectangle(pos=(self.x, self.y), size=(self.width, 2))
        self.bind(pos=self._resize, size=self._resize)

    def _resize(self, *a):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self._accent.pos = (self.x, self.y)
        self._accent.size = (self.width, 2)
