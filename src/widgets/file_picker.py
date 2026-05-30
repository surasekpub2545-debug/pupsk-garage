"""
Cross-platform Kivy file picker for app-internal files.

Browses `user_data_dir/<subdir>` so it works the same on Windows / Android
without needing a native filesystem picker.  Modes:

    AppFilePicker(mode='open', subdir='sessions', ext='.session',
                   on_pick=cb)            # cb(path)

    AppFilePicker(mode='save', subdir='sessions', ext='.session',
                   default_filename='run_001', on_pick=cb)
"""
import os
import time
from kivy.app import App
from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle, Line

from . import theme as Theme
from .racing_ui import paint_bg, RacingButton


def app_dir(subdir: str = '') -> str:
    """Return user_data_dir/<subdir>, creating it if needed."""
    base = App.get_running_app().user_data_dir
    path = os.path.join(base, subdir) if subdir else base
    try: os.makedirs(path, exist_ok=True)
    except Exception: pass
    return path


class _FileRow(Button):
    """Single file row with name + size + mtime."""
    def __init__(self, path, on_pick, **kw):
        kw.setdefault('size_hint', (1, None))
        kw.setdefault('height', 56)
        kw.setdefault('background_color', (0, 0, 0, 0))
        kw.setdefault('halign', 'left')
        kw.setdefault('valign', 'middle')
        kw.setdefault('color', Theme.TEXT)
        try:
            size = os.path.getsize(path)
            mt = time.strftime('%Y-%m-%d %H:%M',
                                time.localtime(os.path.getmtime(path)))
            sub = f'{size/1024:.1f} KB  •  {mt}'
        except Exception:
            sub = ''
        super().__init__(
            text=f'  [size=15][b]{os.path.basename(path)}[/b][/size]\n'
                 f'  [size=11][color=99aacc]{sub}[/color][/size]',
            markup=True, **kw)
        self.bind(size=lambda l, s: setattr(l, 'text_size', s))
        self.path = path
        with self.canvas.before:
            Color(*Theme.BG_PANEL)
            self._bg = Rectangle(pos=self.pos, size=self.size)
            Color(*Theme.GRID_DIM)
            self._line = Line(rectangle=(self.x, self.y,
                                            self.width, self.height),
                               width=1)
        self.bind(pos=self._repaint, size=self._repaint)
        self.bind(on_release=lambda *a: on_pick(self.path))

    def _repaint(self, *a):
        self._bg.pos  = self.pos
        self._bg.size = self.size
        self._line.rectangle = (self.x, self.y, self.width, self.height)


class AppFilePicker(ModalView):
    """Modal picker for files in app's user_data_dir/<subdir>."""

    def __init__(self, mode='open', subdir='', ext='',
                 default_filename='', on_pick=None, title=None, **kw):
        kw.setdefault('size_hint', (0.88, 0.92))
        kw.setdefault('background_color', (0, 0, 0, 0))
        kw.setdefault('background', '')
        super().__init__(**kw)
        self.mode      = mode
        self.subdir    = subdir
        self.ext       = ext
        self.on_pick   = on_pick
        self._dir      = app_dir(subdir)

        root = BoxLayout(orientation='vertical', padding=14, spacing=10)
        paint_bg(root, Theme.BG_DARK, border=Theme.PRIMARY, border_width=2)
        self.add_widget(root)

        title_text = title or ('SAVE FILE' if mode == 'save' else 'OPEN FILE')
        head = BoxLayout(orientation='horizontal',
                          size_hint=(1, None), height=44)
        head.add_widget(Label(
            text=f'[size=20][b][color=00d4ff]'
                 f'{"  ".join(title_text)}[/color][/b][/size]',
            markup=True, halign='left', valign='middle'))
        head.children[0].bind(size=lambda l, s: setattr(l, 'text_size', s))
        root.add_widget(head)

        path_lbl = Label(
            text=f'[size=12][color=99aacc]{self._dir}[/color][/size]',
            markup=True, size_hint=(1, None), height=22,
            halign='left', valign='middle')
        path_lbl.bind(size=lambda l, s: setattr(l, 'text_size', s))
        root.add_widget(path_lbl)

        sv = ScrollView(bar_width=4, bar_color=Theme.PRIMARY)
        self.list_box = BoxLayout(orientation='vertical', size_hint_y=None,
                                    padding=(2, 4), spacing=4)
        self.list_box.bind(minimum_height=self.list_box.setter('height'))
        sv.add_widget(self.list_box)
        root.add_widget(sv)
        self._refresh_list()

        if mode == 'save':
            inp_row = BoxLayout(orientation='horizontal', size_hint=(1, None),
                                 height=54, spacing=8)
            lbl = Label(
                text='[size=14][b]FILENAME[/b][/size]', markup=True,
                color=Theme.TEXT_DIM, size_hint=(0.25, 1),
                halign='right', valign='middle')
            lbl.bind(size=lambda l, s: setattr(l, 'text_size', s))
            inp_row.add_widget(lbl)
            self.name_input = TextInput(
                text=default_filename, size_hint=(0.75, 0.8),
                background_color=Theme.BG_PANEL,
                foreground_color=Theme.PRIMARY, cursor_color=Theme.PRIMARY,
                font_size=18, multiline=False)
            inp_row.add_widget(self.name_input)
            root.add_widget(inp_row)

        actions = BoxLayout(orientation='horizontal', size_hint=(1, None),
                             height=60, spacing=8)
        btn_cancel = RacingButton('cancel', danger=True, font_size=16,
                                    size_hint=(0.5, 1))
        btn_cancel.bind(on_release=lambda *a: self.dismiss())
        actions.add_widget(btn_cancel)
        if mode == 'save':
            btn_save = RacingButton('save', primary=True, font_size=16,
                                      size_hint=(0.5, 1))
            btn_save.bind(on_release=lambda *a: self._do_save())
            actions.add_widget(btn_save)
        root.add_widget(actions)

    def _refresh_list(self):
        self.list_box.clear_widgets()
        try:
            ext = (self.ext or '').lower()
            files = sorted(
                [f for f in os.listdir(self._dir)
                 if (not ext or f.lower().endswith(ext)) and
                    os.path.isfile(os.path.join(self._dir, f))],
                key=lambda f: os.path.getmtime(os.path.join(self._dir, f)),
                reverse=True)
        except Exception:
            files = []
        if not files:
            self.list_box.add_widget(Label(
                text='[size=14][color=99aacc]'
                     'ไม่มีไฟล์ในโฟลเดอร์นี้[/color][/size]',
                markup=True, size_hint=(1, None), height=48,
                halign='center', valign='middle'))
            return
        for fn in files:
            full = os.path.join(self._dir, fn)
            self.list_box.add_widget(_FileRow(full, on_pick=self._on_row_pick))

    def _on_row_pick(self, path):
        if self.mode == 'save':
            base = os.path.basename(path)
            if self.ext and base.lower().endswith(self.ext.lower()):
                base = base[:-len(self.ext)]
            self.name_input.text = base
        else:
            self.dismiss()
            if self.on_pick:
                self.on_pick(path)

    def _do_save(self):
        name = (self.name_input.text or '').strip()
        if not name:
            return
        if self.ext and not name.lower().endswith(self.ext.lower()):
            name += self.ext
        path = os.path.join(self._dir, name)
        self.dismiss()
        if self.on_pick:
            self.on_pick(path)


# ── Native image picker (system / SAF) ────────────────────────────────
def pick_image_native(on_pick, title='Pick image'):
    """Open the platform's native image picker.

    on_pick(path) is called with the chosen path (or never if cancelled).
    Uses plyer.filechooser when available; falls back to tkinter.

    The plyer/SAF callback fires from a Java thread on Android, so we
    bounce on_pick through Clock.schedule_once before touching any Kivy
    widget — otherwise creating the crop dialog raises
    'Cannot create graphics instruction outside the main Kivy thread'.
    """
    from kivy.clock import Clock

    def _main_thread_pick(path):
        Clock.schedule_once(lambda dt: on_pick(path), 0)

    # 1. plyer (works on Android + most desktops)
    try:
        from plyer import filechooser
        def _cb(selection):
            if selection:
                _main_thread_pick(selection[0])
        filechooser.open_file(
            title=title, on_selection=_cb,
            filters=[('Image', '*.png', '*.jpg', '*.jpeg', '*.bmp')])
        return
    except Exception:
        pass
    # 2. tkinter desktop fallback (already on the main thread)
    try:
        from tkinter import filedialog, Tk
        r = Tk(); r.withdraw()
        path = filedialog.askopenfilename(
            title=title,
            filetypes=[('Image', '*.png *.jpg *.jpeg *.bmp')])
        r.destroy()
        if path:
            on_pick(path)
    except Exception:
        pass
