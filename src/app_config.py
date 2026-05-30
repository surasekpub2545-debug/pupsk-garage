"""
Persistent app config — last connected device, preferences.
Saves to platform-appropriate user data directory.
"""
import os, json


def _config_dir() -> str:
    """Return a stable per-app config directory.

    Module load happens BEFORE App.run() returns, so App.get_running_app()
    is None at that point and previously this fell back to a desktop path
    on Android — which meant the load path and the save path (after the
    App was running) were different folders.  Saved settings worked for
    one session and disappeared on next launch.

    On Android, p4a sets ANDROID_PRIVATE to the app's private storage; on
    desktop the App is up by the time we save and user_data_dir resolves.
    """
    # Android: p4a-provided env var, available from the very first import.
    private = os.environ.get('ANDROID_PRIVATE')
    if private:
        try:
            os.makedirs(private, exist_ok=True)
        except Exception:
            pass
        return private
    # Otherwise prefer the running Kivy App if there is one.
    try:
        from kivy.app import App
        app = App.get_running_app()
        if app is not None:
            d = app.user_data_dir
            try: os.makedirs(d, exist_ok=True)
            except Exception: pass
            return d
    except Exception:
        pass
    # Desktop fallback: %APPDATA% on Windows, ~/.config on Linux.
    base = os.environ.get('APPDATA') or os.path.expanduser('~/.config')
    d = os.path.join(base, 'PUP-SK-GARAGE')
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass
    return d


_CACHE = None


def _load() -> dict:
    global _CACHE
    if _CACHE is not None: return _CACHE
    path = os.path.join(_config_dir(), 'app_config.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            _CACHE = json.load(f)
    except Exception:
        _CACHE = {}
    return _CACHE


def _save():
    if _CACHE is None: return
    path = os.path.join(_config_dir(), 'app_config.json')
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(_CACHE, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def get_last_device() -> dict:
    """Returns {'address': ..., 'name': ...} or {}"""
    c = _load()
    return c.get('last_device', {})


def set_last_device(address: str, name: str):
    c = _load()
    c['last_device'] = {'address': address, 'name': name}
    _save()


def clear_last_device():
    c = _load()
    if 'last_device' in c:
        del c['last_device']
        _save()


def get(key, default=None):
    return _load().get(key, default)


def set_(key, value):
    c = _load()
    c[key] = value
    _save()


# ── Theme / appearance settings ─────────────────────────────────────
DEFAULT_ACCENT = '#00d4ff'      # cyan-blue (PUP-SK GARAGE)
DEFAULT_BG     = 'solid'        # 'solid', 'carbon', 'hex', 'brushed', or file path

def get_accent() -> str:
    return _load().get('accent_color', DEFAULT_ACCENT)

def set_accent(hex_color: str):
    set_('accent_color', hex_color)

def get_background() -> str:
    return _load().get('background', DEFAULT_BG)

def set_background(value: str):
    set_('background', value)

def hex_to_rgba(hex_color: str, alpha: float = 1.0):
    """'#00ff70' → (0.0, 1.0, 0.439, 1.0)"""
    h = hex_color.lstrip('#')
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return (r/255.0, g/255.0, b/255.0, alpha)
    return (0.0, 1.0, 0.439, alpha)
