"""
Honda ECU Cockpit — Android Kivy app
Opens directly to the Cockpit screen. User taps CONNECT to pair with the
Super Connext BLE box, or the app auto-reconnects to the last used device
on startup.
"""
import os, sys, asyncio, threading, traceback

os.environ.setdefault('KIVY_NO_ARGS', '1')

# Python's FileFinder may cache a half-populated kivy/ directory listing
# on first launch while p4a is still extracting _python_bundle. Drop the
# cache and force-load kivy.input below to dodge a transient
# ModuleNotFoundError that breaks the SDL2 window provider.
import importlib
import importlib.util
importlib.invalidate_caches()


def _force_load_kivy_input():
    """Manually load kivy.input by pointing at its __init__.pyc on disk.

    Python's auto-discovery cannot find this subpackage on Android even
    though every file is in place and kivy.__spec__.submodule_search_locations
    is correct.  Loading it explicitly via importlib.util sidesteps the
    importer entirely and registers kivy.input in sys.modules so the
    rest of Kivy can `from kivy.input import ...` normally.
    """
    try:
        import kivy
    except Exception as e:
        print(f'[force] cannot import kivy itself: {e}')
        return
    kivy_dir = os.path.dirname(kivy.__file__)
    input_dir = os.path.join(kivy_dir, 'input')
    # Try .pyc first, then .py
    for ext in ('.pyc', '.py'):
        init = os.path.join(input_dir, '__init__' + ext)
        if os.path.isfile(init):
            try:
                spec = importlib.util.spec_from_file_location(
                    'kivy.input', init,
                    submodule_search_locations=[input_dir])
                if spec is None:
                    print(f'[force] no spec from {init}')
                    continue
                mod = importlib.util.module_from_spec(spec)
                sys.modules['kivy.input'] = mod
                spec.loader.exec_module(mod)
                print(f'[force] loaded kivy.input from {init}')
                return
            except Exception as e:
                print(f'[force] exec {init} failed: '
                      f'{type(e).__name__}: {e}')
    print('[force] could not locate kivy/input/__init__.*')


_force_load_kivy_input()


def _install_crash_handler():
    """Catch uncaught exceptions and print/save a traceback so we get
    a usable signal even when Android would otherwise abort silently."""
    def _hook(exc_type, exc_value, tb):
        msg = ''.join(traceback.format_exception(exc_type, exc_value, tb))
        try: print('[FATAL]\n' + msg)
        except Exception: pass
        try:
            from kivy.app import App
            base = App.get_running_app().user_data_dir \
                   if App.get_running_app() else os.getcwd()
            with open(os.path.join(base, 'last_crash.txt'),
                       'w', encoding='utf-8') as f:
                f.write(msg)
        except Exception: pass
    sys.excepthook = _hook


_install_crash_handler()

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from kivy.config import Config
# Landscape orientation — wider than tall (typical tablet/phone-on-side)
Config.set('graphics', 'width',  '1280')
Config.set('graphics', 'height', '720')
Config.set('graphics', 'minimum_width',  '800')
Config.set('graphics', 'minimum_height', '480')
# Multisample anti-aliasing for smoother fonts and gauge curves.
# 0 on Android — BlueStacks/houdini GL ES drivers silently drop frames
# with MSAA enabled, leaving a fully black canvas.
Config.set('graphics', 'multisamples', '0')

# Register Thai-capable font BEFORE any Kivy widget is created
from src.font_setup import setup_fonts
setup_fonts()

# ── Apply saved theme accent BEFORE any widget is created ────────────
from src import app_config
from src.widgets import theme as _theme
_saved_accent = app_config.get_accent()
_theme.apply_accent(app_config.hex_to_rgba(_saved_accent))

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, NoTransition
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock

from src.ble_client import BleClient
from src.gps import GpsProvider
from src.protocol.super_connext import parse_live_data, parse_dtc
from src.protocol import honda_dtc
from src.widgets import theme as Theme
from src.widgets.bottom_nav import BottomNav
from src.widgets.playback_bar import PlaybackBar
from src.session import SessionRecorder, SessionPlayer
from src.screens.splash_screen   import SplashScreen
from src.screens.connect_screen  import ConnectScreen
from src.screens.cockpit_screen  import CockpitScreen
from src.screens.trends_screen   import TrendsScreen
from src.screens.afrmap_screen   import AfrMapScreen
from src.screens.dyno_screen     import DynoScreen
from src.screens.dtc_screen      import DTCScreen
from src.screens.settings_screen import SettingsScreen
from src.screens.about_screen    import AboutScreen
from src.widgets.side_menu       import SideMenu


class HondaECUCockpitApp(App):
    title = 'PUP-SK GARAGE'

    def _apply_android_immersive(self):
        """Hide status + nav bars game-style. Uses Android's IMMERSIVE
        STICKY flags so swiping from an edge briefly reveals them but
        they auto-hide after a second."""
        try:
            from jnius import autoclass
            from android.runnable import run_on_ui_thread
            View = autoclass('android.view.View')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity = PythonActivity.mActivity
            if activity is None:
                return
            flags = (
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
            )

            @run_on_ui_thread
            def _set_flags():
                try:
                    activity.getWindow().getDecorView() \
                        .setSystemUiVisibility(flags)
                except Exception as e:
                    print(f'[android] decorView err: {e}')
            _set_flags()
        except Exception:
            # Not on Android — nothing to do
            pass

    def on_resume(self):
        # Re-assert immersive after the system temporarily un-hid the
        # bars (e.g. user pulled the notification shade down).
        self._apply_android_immersive()

    def _request_android_permissions(self):
        """On Android 12+ BLE scan/connect require runtime permission."""
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.BLUETOOTH_SCAN,
                Permission.BLUETOOTH_CONNECT,
                Permission.ACCESS_FINE_LOCATION,
                Permission.ACCESS_COARSE_LOCATION,
            ])
            print('[android] BLE permissions requested')
        except Exception:
            # Not on Android — skip silently
            pass

    def _set_window_icon(self):
        """Use our generated .ico for the window/taskbar."""
        try:
            from kivy.core.window import Window
            ico = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'assets', 'logo', 'icon_256.png')
            ico = os.path.normpath(ico)
            ico = os.path.join(os.path.dirname(ico), 'icons', 'icon_256.png')
            if os.path.exists(ico):
                Window.set_icon(ico)
        except Exception: pass

    def build(self):
        self._set_window_icon()
        self._request_android_permissions()
        # Schedule immersive after the activity finishes laying out the
        # first frame — too early and the decorView call is a no-op.
        try:
            from kivy.clock import Clock as _Clock
            _Clock.schedule_once(
                lambda dt: self._apply_android_immersive(), 0.5)
        except Exception: pass
        n = honda_dtc.load_dtc_table()
        print(f'[app] Loaded {n} Honda DTC codes')

        # BLE
        self.ble = BleClient()
        self.ble.set_data_callback(self._on_ble_packet)
        self._device_name = ''
        self._prev_screen = 'cockpit'

        # Session record / playback
        self.recorder = SessionRecorder()
        self.player = SessionPlayer(on_sample=self._dispatch_live)

        # GPS — used for speed display in the tachometer center.
        # NOT started automatically: on Android emulators (BlueStacks,
        # Genymotion, etc.) the LocationListener fires through a JNI
        # proxy and houdini's ARM translation can't detach the thread
        # mid-call → SIGABRT.  Start via app.start_gps() once the user
        # is on a real device (e.g. from Settings or a one-time prompt).
        self.gps = GpsProvider()
        self.gps.set_speed_callback(self._on_gps_speed)
        print('[gps] provider ready (call app.start_gps() to enable)')

        # Root layout
        root = BoxLayout(orientation='vertical')
        # Background fill (solid color) + optional image overlay
        with root.canvas.before:
            Color(*Theme.BG)
            self._bg_color_rect = Rectangle(pos=root.pos, size=root.size)
            # Hidden by default — only visible when a texture is loaded
            self._bg_image_color = Color(1, 1, 1, 0)
            self._bg_image_rect = Rectangle(pos=root.pos, size=root.size)
        self._root_widget = root
        root.bind(pos=lambda *a: self._update_root_bg(),
                  size=lambda *a: self._update_root_bg())
        # Apply saved background preset / image
        self.apply_background(app_config.get_background())

        # Screen manager — DO NOT add ConnectScreen to bottom nav; it's modal
        self.sm = ScreenManager(transition=NoTransition())
        root.add_widget(self.sm)

        self.splash_screen   = SplashScreen(self, duration=2.0)
        self.cockpit_screen  = CockpitScreen(self)
        self.trends_screen   = TrendsScreen(self)
        self.afrmap_screen   = AfrMapScreen(self)
        self.dyno_screen     = DynoScreen(self)
        self.dtc_screen      = DTCScreen(self)
        self.connect_screen  = ConnectScreen(self)
        self.settings_screen = SettingsScreen(self)
        self.about_screen    = AboutScreen(self)
        for s in (self.splash_screen, self.cockpit_screen, self.trends_screen,
                  self.afrmap_screen, self.dyno_screen, self.dtc_screen,
                  self.connect_screen, self.settings_screen, self.about_screen):
            self.sm.add_widget(s)

        # ➜ START ON SPLASH (transitions to cockpit after 2s)
        self.sm.current = 'splash'

        # Floating playback bar — always visible above bottom nav
        self.playback_bar = PlaybackBar(self)
        root.add_widget(self.playback_bar)

        # Bottom nav — racing-style numbered tabs
        self.nav = BottomNav(self.sm, items=[
            ('01', 'Cockpit', 'cockpit'),
            ('02', 'Trends',  'trends'),
            ('03', 'AF Map',  'afrmap'),
            ('04', 'Dyno',    'dyno'),
            ('05', 'DTC',     'dtc'),
        ])
        root.add_widget(self.nav)
        # highlight cockpit initially
        self.nav._on_tap('cockpit')

        # Background asyncio loop
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_async, daemon=True)
        self._thread.start()

        # Try auto-reconnect if we have a saved device
        Clock.schedule_once(lambda dt: self._try_auto_reconnect(), 1.5)

        return root

    def start_gps(self) -> bool:
        """Explicitly start GPS — call once the user opts in."""
        ok = self.gps.start()
        print(f'[gps] started: {ok}')
        return ok

    def _run_async(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def submit_async(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def on_stop(self):
        try:
            asyncio.run_coroutine_threadsafe(self.ble.disconnect(), self._loop)
        except Exception: pass
        try: self.gps.stop()
        except Exception: pass
        try:
            self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception: pass

    # ── Side menu drawer ────────────────────────────────────────────────
    def open_menu(self):
        """Show the hamburger drawer menu."""
        SideMenu(self).open()

    # ── GPS speed → tachometer ─────────────────────────────────────────
    def _on_gps_speed(self, kmh: float):
        # GPS callback may fire on another thread — schedule UI update
        Clock.schedule_once(
            lambda dt: self.cockpit_screen.tach.set_speed(kmh), 0)

    # ── Root background painter ─────────────────────────────────────────
    def _update_root_bg(self):
        r = self._root_widget
        self._bg_color_rect.pos  = r.pos
        self._bg_color_rect.size = r.size
        # Fit the image preserving aspect ratio (contain) — letterbox edges
        tex = self._bg_image_rect.texture
        if tex is not None and tex.width > 0 and tex.height > 0:
            img_w, img_h = tex.size
            win_w, win_h = r.size
            scale = min(win_w / img_w, win_h / img_h)
            new_w = img_w * scale
            new_h = img_h * scale
            new_x = r.x + (win_w - new_w) / 2
            new_y = r.y + (win_h - new_h) / 2
            self._bg_image_rect.pos  = (new_x, new_y)
            self._bg_image_rect.size = (new_w, new_h)
        else:
            # No image — just match root (won't show because alpha=0)
            self._bg_image_rect.pos  = r.pos
            self._bg_image_rect.size = r.size

    def apply_background(self, value: str):
        """Apply a background preset key or a file path."""
        import os
        tex = None
        if value and os.path.isfile(value):
            # Custom user image
            try:
                from kivy.core.image import Image as CoreImage
                tex = CoreImage(value).texture
            except Exception as e:
                print(f'[bg] Failed to load image: {e}')
                tex = None
        else:
            preset_path = self._preset_image_path(value)
            if preset_path and os.path.isfile(preset_path):
                try:
                    from kivy.core.image import Image as CoreImage
                    tex = CoreImage(preset_path).texture
                except Exception:
                    tex = None
        # Apply texture and toggle visibility
        if tex is not None:
            self._bg_image_rect.texture = tex
            self._bg_image_color.rgba = (1, 1, 1, 1)
            try:
                print(f'[bg] Loaded background ({tex.width}x{tex.height})')
            except Exception: pass
            # Re-fit to current window size
            self._update_root_bg()
        else:
            self._bg_image_rect.texture = None
            self._bg_image_color.rgba = (1, 1, 1, 0)   # hide rectangle

    def _preset_image_path(self, key: str) -> str:
        """Resolve a built-in background preset key to a file path."""
        import os
        here = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(here, 'assets', 'bg', f'{key}.png')

    # ── Auto-reconnect on startup ───────────────────────────────────────
    def _try_auto_reconnect(self):
        last = app_config.get_last_device()
        if not last.get('address'):
            return     # no previous device
        addr = last['address']; name = last.get('name', '')
        print(f'[app] Auto-reconnecting to last device: {name} ({addr})')
        self.cockpit_screen.conn_lbl.text = f'⌛ Reconnecting…'
        self.cockpit_screen.conn_lbl.color = Theme.WARNING
        self.submit_async(self._auto_reconnect_async(addr, name))

    async def _auto_reconnect_async(self, address, name):
        try:
            ok = await self.ble.connect(address)
        except Exception:
            ok = False
        def after(dt):
            if ok:
                self._device_name = name
                self.cockpit_screen.set_connection_status(True, name)
                print(f'[app] Auto-reconnect OK')
            else:
                self.cockpit_screen.set_connection_status(False)
                print(f'[app] Auto-reconnect failed — user can tap CONNECT')
        Clock.schedule_once(after, 0)

    # ── Connect screen callbacks ────────────────────────────────────────
    def on_connected(self, address, name):
        self._device_name = name
        self.cockpit_screen.set_connection_status(True, name)
        # Return to previous tab (cockpit by default)
        target = getattr(self, '_prev_screen', 'cockpit')
        if self.sm.has_screen(target):
            self.sm.current = target
            self.nav._on_tap(target)

    def on_disconnect_request(self):
        self.submit_async(self._do_disconnect())

    async def _do_disconnect(self):
        await self.ble.disconnect()
        Clock.schedule_once(lambda dt: self._after_disconnect(), 0)

    def _after_disconnect(self):
        self.cockpit_screen.set_connection_status(False)
        # Stay on current screen — user just disconnects, doesn't navigate away

    # ── BLE packet handler ──────────────────────────────────────────────
    def _on_ble_packet(self, text: str):
        if '&M' in text:
            ld = parse_live_data(text)
            if ld is not None and ld.valid:
                Clock.schedule_once(lambda dt: self._on_live(ld), 0)
        elif '&RDTC' in text:
            r = parse_dtc(text)
            Clock.schedule_once(lambda dt: self.dtc_screen.on_dtc_response(r), 0)
        elif '&CDTCDONE' in text:
            Clock.schedule_once(lambda dt: self.dtc_screen.on_clear_done(), 0)

    def _on_live(self, ld):
        """Live BLE sample → record (if active) + dispatch (unless playing back)."""
        try:
            if self.recorder.is_active:
                self.recorder.append(ld)
        except Exception: pass
        # Suppress live dispatch while a session is loaded for playback
        if not self.player.is_loaded:
            self._dispatch_live(ld)

    def _dispatch_live(self, ld):
        try: self.cockpit_screen.update_data(ld)
        except Exception: pass
        try: self.trends_screen.push_data(ld)
        except Exception: pass
        try: self.afrmap_screen.push_data(ld)
        except Exception: pass
        try: self.dyno_screen.feed(ld)
        except Exception: pass


# asyncio.create_task compat for background loop
import asyncio as _asyncio
def _ct(coro):
    try:
        loop = _asyncio.get_running_loop()
        return loop.create_task(coro)
    except RuntimeError:
        app = App.get_running_app()
        if app and hasattr(app, '_loop'):
            return _asyncio.run_coroutine_threadsafe(coro, app._loop)
        return None
_asyncio.create_task = _ct


if __name__ == '__main__':
    HondaECUCockpitApp().run()
