"""
Register a Thai-capable font as Kivy's default.
Falls back gracefully across platforms.
"""
import os, sys
from kivy.core.text import LabelBase


def _find_font():
    """Return path to a Thai-capable TTF, or None."""
    candidates = []

    # Bundled font (highest priority — same look on all platforms)
    here = os.path.dirname(os.path.abspath(__file__))
    for sub in ('../assets/fonts', 'assets/fonts'):
        for name in ('Sarabun-Regular.ttf', 'NotoSansThai-Regular.ttf',
                     'IBMPlexSansThai-Regular.ttf', 'Prompt-Regular.ttf'):
            candidates.append(os.path.join(here, sub, name))

    # Windows system fonts
    candidates.extend([
        r'C:\Windows\Fonts\tahoma.ttf',
        r'C:\Windows\Fonts\leelawui.ttf',
        r'C:\Windows\Fonts\segoeui.ttf',
    ])

    # Android system fonts
    candidates.extend([
        '/system/fonts/NotoSansThai-Regular.ttf',
        '/system/fonts/DroidSansThai-Regular.ttf',
        '/system/fonts/Roboto-Regular.ttf',
    ])

    # Linux / macOS common
    candidates.extend([
        '/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf',
        '/Library/Fonts/Arial Unicode.ttf',
    ])

    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _find_bold():
    """Return path to a bold variant."""
    here = os.path.dirname(os.path.abspath(__file__))
    for sub in ('../assets/fonts', 'assets/fonts'):
        for name in ('Sarabun-Bold.ttf', 'NotoSansThai-Bold.ttf',
                     'IBMPlexSansThai-Bold.ttf', 'Prompt-Bold.ttf'):
            p = os.path.join(here, sub, name)
            if os.path.exists(p): return p

    for path in [r'C:\Windows\Fonts\tahomabd.ttf',
                 r'C:\Windows\Fonts\leelawdb.ttf',
                 '/system/fonts/NotoSansThai-Bold.ttf',
                 '/system/fonts/Roboto-Bold.ttf']:
        if os.path.exists(path): return path
    return None


def setup_fonts():
    """Override Roboto with a Thai-capable font globally."""
    regular = _find_font()
    bold    = _find_bold()
    if not regular:
        print('[font] No Thai font found — using Kivy default')
        return False
    print(f'[font] Using regular: {regular}')
    print(f'[font] Using bold:    {bold or "(same as regular)"}')
    # Override the default "Roboto" alias — every Kivy widget uses this by default
    LabelBase.register(
        name='Roboto',
        fn_regular=regular,
        fn_bold=bold or regular,
        fn_italic=regular,
        fn_bolditalic=bold or regular,
    )
    return True
