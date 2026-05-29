"""Floating playback control bar — always visible above bottom nav."""
import time
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.clock import Clock

from . import theme as Theme
from .racing_ui import paint_bg, RacingButton


def _fmt_time(s):
    s = max(0, int(s))
    return f'{s // 60:02d}:{s % 60:02d}'


class PlaybackBar(BoxLayout):
    """Always-on strip with REC / OPEN / PLAY / TIME / SEEK / CLOSE."""

    def __init__(self, app, **kw):
        kw.setdefault('orientation', 'horizontal')
        kw.setdefault('size_hint', (1, None))
        kw.setdefault('height', 52)
        kw.setdefault('padding', (10, 6))
        kw.setdefault('spacing', 8)
        super().__init__(**kw)
        self.app = app
        paint_bg(self, Theme.BG_DARK)
        self._user_seeking = False
        self._build()
        Clock.schedule_interval(self._refresh, 1/10.0)

    def _build(self):
        # State indicator
        self.state_lbl = Label(
            text='[size=15][color=99aacc][b]READY[/b][/color][/size]',
            markup=True, size_hint=(None, 1), width=120,
            halign='left', valign='middle')
        self.state_lbl.bind(size=lambda l, s: setattr(l, 'text_size', s))
        self.add_widget(self.state_lbl)

        # Record / stop
        self.btn_rec = RacingButton('rec', danger=True, font_size=14,
                                      size_hint=(None, 1), width=84)
        self.btn_rec.bind(on_release=lambda *a: self._toggle_rec())
        self.add_widget(self.btn_rec)

        # Open session file
        self.btn_open = RacingButton('open', font_size=14,
                                       size_hint=(None, 1), width=84)
        self.btn_open.bind(on_release=lambda *a: self._open_session())
        self.add_widget(self.btn_open)

        # Play / pause
        self.btn_play = RacingButton('play', primary=True, font_size=14,
                                       size_hint=(None, 1), width=84)
        self.btn_play.bind(on_release=lambda *a: self._toggle_play())
        self.add_widget(self.btn_play)

        # Time readout
        self.time_lbl = Label(
            text='[size=13][color=cccccc]00:00 / 00:00[/color][/size]',
            markup=True, size_hint=(None, 1), width=120,
            halign='center', valign='middle')
        self.time_lbl.bind(size=lambda l, s: setattr(l, 'text_size', s))
        self.add_widget(self.time_lbl)

        # Seek slider — fills remaining space
        self.slider = Slider(min=0, max=1, value=0, size_hint=(1, 1))
        self.slider.bind(on_touch_down=self._on_slider_down,
                          on_touch_up=self._on_slider_up,
                          value=self._on_slider_value)
        self.add_widget(self.slider)

        # Close playback
        self.btn_close = RacingButton('close', font_size=14,
                                        size_hint=(None, 1), width=84)
        self.btn_close.bind(on_release=lambda *a: self._close_session())
        self.add_widget(self.btn_close)

    # ── Actions ─────────────────────────────────────────────
    def _toggle_rec(self):
        rec = self.app.recorder
        if rec.is_active:
            self._save_recording()
        else:
            rec.start()

    def _save_recording(self):
        rec = self.app.recorder
        rec.stop()
        if not rec.samples:
            return
        path = ''
        try:
            from tkinter import filedialog, Tk
            r = Tk(); r.withdraw()
            path = filedialog.asksaveasfilename(
                title='Save session',
                defaultextension='.session',
                filetypes=[('Session', '*.session')],
                initialfile=time.strftime('session_%Y%m%d_%H%M%S.session'))
            r.destroy()
        except Exception:
            pass
        if path:
            try:
                rec.save(path)
                print(f'[session] saved {len(rec.samples)} samples → {path}')
            except Exception as e:
                print(f'[session] save failed: {e}')

    def _open_session(self):
        path = ''
        try:
            from tkinter import filedialog, Tk
            r = Tk(); r.withdraw()
            path = filedialog.askopenfilename(
                title='Open session',
                filetypes=[('Session', '*.session'), ('All', '*.*')])
            r.destroy()
        except Exception:
            pass
        if not path:
            return
        try:
            self.app.player.load(path)
            print(f'[session] loaded {len(self.app.player.samples)} '
                  f'samples (dur {self.app.player.duration:.1f}s)')
        except Exception as e:
            print(f'[session] load failed: {e}')

    def _toggle_play(self):
        p = self.app.player
        if not p.is_loaded:
            return
        p.toggle()

    def _close_session(self):
        self.app.player.close()

    # ── Slider interaction ──────────────────────────────────
    def _on_slider_down(self, slider, touch):
        if slider.collide_point(*touch.pos) and self.app.player.is_loaded:
            self._user_seeking = True
        return False

    def _on_slider_up(self, slider, touch):
        if self._user_seeking:
            self.app.player.seek(slider.value)
            self._user_seeking = False
        return False

    def _on_slider_value(self, slider, value):
        if self._user_seeking and self.app.player.is_loaded:
            self.app.player.seek(value)

    # ── Periodic UI sync ────────────────────────────────────
    def _refresh(self, dt):
        rec = self.app.recorder
        p = self.app.player

        if rec.is_active:
            self.state_lbl.text = (
                f'[size=15][color=ff173f][b]> REC '
                f'{_fmt_time(rec.elapsed)}[/b][/color][/size]')
            self.btn_rec.text = '  '.join('STOP')
            self._set_disabled(self.btn_rec, False)
            self._set_disabled(self.btn_open, True)
            self._set_disabled(self.btn_play, True)
            self._set_disabled(self.btn_close, True)
            self._set_disabled(self.slider, True)
            self.time_lbl.opacity = 0
        elif p.is_loaded:
            mode  = 'PLAYING' if p.is_playing else 'PAUSED'
            color = '00ff70'  if p.is_playing else 'ffc600'
            self.state_lbl.text = (f'[size=15][color={color}][b]{mode}'
                                     f'[/b][/color][/size]')
            self.btn_play.text = ('  '.join('PAUSE')
                                    if p.is_playing else '  '.join('PLAY'))
            self._set_disabled(self.btn_rec, True)
            self._set_disabled(self.btn_open, True)
            self._set_disabled(self.btn_play, False)
            self._set_disabled(self.btn_close, False)
            self._set_disabled(self.slider, False)
            self.slider.max = max(0.001, p.duration)
            if not self._user_seeking:
                self.slider.value = p.t
            self.time_lbl.opacity = 1
            self.time_lbl.text = (f'[size=13][color=cccccc]'
                                    f'{_fmt_time(p.t)} / '
                                    f'{_fmt_time(p.duration)}'
                                    f'[/color][/size]')
        else:
            self.state_lbl.text = (
                '[size=15][color=99aacc][b]READY[/b][/color][/size]')
            self.btn_rec.text = '  '.join('REC')
            self.btn_play.text = '  '.join('PLAY')
            self._set_disabled(self.btn_rec, False)
            self._set_disabled(self.btn_open, False)
            self._set_disabled(self.btn_play, True)
            self._set_disabled(self.btn_close, True)
            self._set_disabled(self.slider, True)
            self.time_lbl.opacity = 0

    @staticmethod
    def _set_disabled(w, disabled):
        w.disabled = disabled
        w.opacity = 0.35 if disabled else 1.0
