"""Splash screen — shown briefly on app start, then transitions to cockpit."""
import os
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock

from src.widgets import theme as Theme


def _bg(widget, color):
    with widget.canvas.before:
        Color(*color)
        widget._bg = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(pos=lambda *a: setattr(widget._bg, 'pos', widget.pos),
                size=lambda *a: setattr(widget._bg, 'size', widget.size))


class SplashScreen(Screen):
    """Splash — solid black bg + center logo + slogan."""
    def __init__(self, app, duration=2.0, **kw):
        super().__init__(**kw)
        self.app = app
        self.name = 'splash'
        self._duration = duration
        _bg(self, Theme.BG_DARK)

        root = BoxLayout(orientation='vertical', padding=40, spacing=12)
        self.add_widget(root)

        # Top spacer
        root.add_widget(BoxLayout(size_hint=(1, 0.25)))

        # Center wordmark — always Label so it follows the accent color
        accent = Theme.primary_hex()
        root.add_widget(Label(
            text=f'[size=72][b][color=ffffff]PUP-SK[/color][/b][/size]\n'
                 f'[size=42][b][color={accent}]G A R A G E[/color][/b][/size]',
            markup=True, halign='center', valign='middle',
            size_hint=(1, 0.45)))

        # Sub label
        root.add_widget(Label(
            text='[size=14][b][color=99aabb]'
                 'H O N D A   E C U   T U N I N G'
                 '[/color][/b][/size]',
            markup=True, halign='center', valign='middle',
            size_hint=(1, 0.10)))

        # Author line
        root.add_widget(Label(
            text='[size=11][color=556677]B Y   S U R A S E K[/color][/size]',
            markup=True, halign='center', valign='middle',
            size_hint=(1, 0.10)))

        # Bottom spacer
        root.add_widget(BoxLayout(size_hint=(1, 0.10)))

    def on_enter(self, *a):
        # Auto-transition after duration
        Clock.schedule_once(self._goto_cockpit, self._duration)

    def _goto_cockpit(self, dt):
        sm = self.app.sm
        if sm.has_screen('cockpit'):
            sm.current = 'cockpit'
            try:
                self.app.nav._on_tap('cockpit')
            except Exception: pass
