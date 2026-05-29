"""
Kivy scrolling strip chart — like the Tkinter one but for mobile.
Tap to expand to fullscreen zoom popup.
"""
from collections import deque
from kivy.uix.widget import Widget
from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, Line, Rectangle
from kivy.properties import StringProperty, NumericProperty

from . import theme as Theme


class StripChart(Widget):
    title = StringProperty('')
    units = StringProperty('')

    def __init__(self, title='', units='', low=0, high=100, history=300,
                 color=None, zoomable=True, **kw):
        super().__init__(**kw)
        self.title = title
        self.units = units
        self.low = low; self.high = high
        self.color = color or Theme.PRIMARY
        self.history = history
        self.data = deque([None]*history, maxlen=history)
        self.zoomable = zoomable
        self._zoom_popup = None
        self.bind(size=lambda *a: self._redraw(),
                  pos=lambda *a: self._redraw())
        self._redraw()

    def push(self, v):
        self.data.append(v)
        self._redraw()

    def reset(self):
        self.data = deque([None]*self.history, maxlen=self.history)
        self._redraw()

    def on_touch_down(self, touch):
        if not self.zoomable: return False
        if not self.collide_point(*touch.pos): return False
        self._open_zoom(); return True

    def _open_zoom(self):
        if self._zoom_popup is not None: return
        view = ModalView(size_hint=(0.95, 0.85))
        wrap = BoxLayout(orientation='vertical', padding=10, spacing=8)
        view.add_widget(wrap)
        # Header
        hdr = BoxLayout(orientation='horizontal', size_hint=(1, None), height=44)
        hdr.add_widget(Label(text=f'[b]{self.title} [{self.units}][/b]',
                              markup=True, color=Theme.ACCENT, font_size=18))
        btn = Button(text='✕ CLOSE', size_hint=(0.25, 1),
                      background_color=Theme.DANGER, color=(1,1,1,1), bold=True)
        btn.bind(on_release=lambda *a: view.dismiss())
        hdr.add_widget(btn)
        wrap.add_widget(hdr)
        # Big chart (non-zoomable to avoid recursion)
        big = StripChart(title=self.title, units=self.units,
                         low=self.low, high=self.high,
                         history=self.history, color=self.color,
                         zoomable=False, size_hint=(1, 1))
        big.data = deque(list(self.data), maxlen=self.history)
        wrap.add_widget(big)
        # Sync data periodically
        from kivy.clock import Clock
        def _sync(dt):
            if view._is_open:
                big.data = deque(list(self.data), maxlen=self.history)
                big._redraw()
                Clock.schedule_once(_sync, 0.1)
        view._is_open = True
        view.bind(on_dismiss=lambda *a: setattr(view, '_is_open', False))
        Clock.schedule_once(_sync, 0.1)
        view.bind(on_dismiss=lambda *a: setattr(self, '_zoom_popup', None))
        self._zoom_popup = view
        view.open()

    def _redraw(self, *a):
        self.canvas.clear()
        x, y, w, h = self.x, self.y, self.width, self.height
        if w < 50 or h < 40: return
        with self.canvas:
            # Background carbon panel
            Color(*Theme.BG_PANEL)
            Rectangle(pos=(x, y), size=(w, h))
            # Carbon outline
            Color(*Theme.GRID)
            Line(rectangle=(x, y, w, h), width=1)
            # Top accent strip (color = chart's color, racing style)
            Color(*self.color)
            Rectangle(pos=(x, y + h - 2), size=(w, 2))
            # Grid lines (horizontal)
            for i in range(1, 4):
                gy = y + h * i / 4
                Color(*Theme.GRID_DIM)
                Line(points=[x + 8, gy, x + w - 8, gy],
                     width=1, dash_length=2, dash_offset=4)
            # Plot trace
            n = len(self.data)
            if n >= 2 and self.high > self.low:
                px0 = x + 8; px1 = x + w - 8
                py0 = y + 6; py1 = y + h - 8
                pts = []
                for i, v in enumerate(self.data):
                    if v is None: continue
                    px = px0 + (px1 - px0) * i / (n - 1)
                    pct = (v - self.low) / (self.high - self.low)
                    pct = max(0, min(1, pct))
                    py = py0 + (py1 - py0) * pct
                    pts.extend([px, py])
                if len(pts) >= 4:
                    # Glow underlay
                    r, g, b, a = self.color
                    Color(r, g, b, 0.30)
                    Line(points=pts, width=5)
                    Color(*self.color)
                    Line(points=pts, width=2)
