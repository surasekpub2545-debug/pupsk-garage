"""Kivy bar gauge — compact horizontal bar + digital readout."""
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle, Line
from kivy.properties import NumericProperty, StringProperty
from kivy.clock import Clock

from . import theme as Theme


class BarGauge(Widget):
    value  = NumericProperty(0)
    target = NumericProperty(0)
    title  = StringProperty('')
    units  = StringProperty('')

    def __init__(self, title='', units='', low=0, high=100, warn=None, **kw):
        super().__init__(**kw)
        self.title = title
        self.units = units
        self.low = low; self.high = high
        self.warn = warn if warn is not None else (low + (high-low)*0.85)
        self._smooth_alpha = 0.22
        self.bind(size=lambda *a: self._redraw(),
                  pos=lambda *a:  self._redraw(),
                  value=lambda *a: self._redraw())
        Clock.schedule_interval(self._animate, 1/30.0)
        self._redraw()

    def set_value(self, v):
        if v is None: return
        self.target = max(self.low, min(self.high, v))

    def reset(self):
        self.target = self.low; self.value = self.low

    def _animate(self, dt):
        if abs(self.value - self.target) > 0.01:
            self.value += (self.target - self.value) * self._smooth_alpha

    def _redraw(self, *a):
        self.canvas.clear()
        x, y, w, h = self.x, self.y, self.width, self.height
        if w < 20 or h < 20: return
        with self.canvas:
            # Panel background
            Color(*Theme.BG_PANEL)
            Rectangle(pos=(x, y), size=(w, h))
            # Border
            Color(*Theme.GRID)
            Line(rectangle=(x, y, w, h), width=1)

            # Title (top-left)
            # Value (top-right)
            # We use a separate Label later — Canvas can't draw text easily

            # Bar
            pct = (self.value - self.low) / (self.high - self.low) if self.high > self.low else 0
            pct = max(0, min(1, pct))
            bar_w = (w - 16) * pct
            bar_h = 8
            bx = x + 8
            by = y + 8
            # Track
            Color(*Theme.BG_DARK)
            Rectangle(pos=(bx, by), size=(w-16, bar_h))
            # Fill
            if self.value >= self.warn:
                Color(*Theme.DANGER)
            else:
                Color(*Theme.PRIMARY)
            Rectangle(pos=(bx, by), size=(bar_w, bar_h))
