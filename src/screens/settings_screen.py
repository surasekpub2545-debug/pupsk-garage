"""Settings screen — theme color + background picker."""
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle, Line
from kivy.clock import Clock

from src.widgets import theme as Theme
from src.widgets.racing_ui import paint_bg, RacingButton
from src import app_config


# Available color presets
COLOR_PRESETS = [
    ('#00ff70', 'racing green'),
    ('#ff173f', 'racing red'),
    ('#00d4ff', 'ice cyan'),
    ('#ffc600', 'amber'),
    ('#ff48d6', 'neon pink'),
    ('#ffffff', 'pure white'),
    ('#ff7700', 'sunset orange'),
    ('#a070ff', 'royal purple'),
]

# Available background presets
BG_PRESETS = [
    ('solid',    'solid black',    'flat carbon-black'),
    ('carbon',   'carbon fiber',   'woven carbon pattern'),
    ('hex',      'hex grid',       'hexagonal mesh'),
    ('brushed',  'brushed metal',  'dark brushed steel'),
]


def _hex_to_rgba(h, a=1.0):
    return app_config.hex_to_rgba(h, a)


class ColorSwatch(Button):
    """A clickable color swatch button."""
    def __init__(self, hex_color, label, on_pick, **kw):
        super().__init__(
            text=f'[size=10][color=ffffffaa]{label.upper()}[/color][/size]',
            markup=True, background_color=(0, 0, 0, 0),
            halign='center', valign='bottom', **kw)
        self.hex_color = hex_color
        self._rgba = _hex_to_rgba(hex_color)
        self._selected = False
        with self.canvas.before:
            Color(*self._rgba)
            self._fill = Rectangle(pos=self.pos, size=self.size)
            Color(*Theme.GRID)
            self._outline = Line(rectangle=(self.x, self.y, self.width, self.height),
                                  width=1)
        self.bind(pos=self._resize, size=self._resize)
        self.bind(on_release=lambda *a: on_pick(hex_color))

    def _resize(self, *a):
        self._fill.pos  = self.pos
        self._fill.size = self.size
        self._outline.rectangle = (self.x, self.y, self.width, self.height)

    def set_selected(self, selected):
        self._selected = selected
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self._rgba)
            self._fill = Rectangle(pos=self.pos, size=self.size)
            if selected:
                Color(1, 1, 1, 1)
                self._outline = Line(rectangle=(self.x, self.y, self.width, self.height),
                                      width=3)
            else:
                Color(*Theme.GRID)
                self._outline = Line(rectangle=(self.x, self.y, self.width, self.height),
                                      width=1)


class BgSwatch(Button):
    """A background preset swatch."""
    def __init__(self, key, label, sub, on_pick, **kw):
        super().__init__(
            text=(f'[size=12][b]{label.upper()}[/b][/size]\n'
                  f'[size=9][color=99aaccff]{sub}[/color][/size]'),
            markup=True, background_color=(0,0,0,0),
            color=Theme.TEXT, halign='center', valign='middle', **kw)
        self.key = key
        self._selected = False
        with self.canvas.before:
            Color(*Theme.BG_PANEL)
            self._fill = Rectangle(pos=self.pos, size=self.size)
            Color(*Theme.GRID)
            self._outline = Line(rectangle=(self.x, self.y, self.width, self.height),
                                  width=1)
        self.bind(pos=self._resize, size=self._resize)
        self.bind(on_release=lambda *a: on_pick(key))

    def _resize(self, *a):
        self._fill.pos = self.pos
        self._fill.size = self.size
        self._outline.rectangle = (self.x, self.y, self.width, self.height)

    def set_selected(self, selected):
        self._selected = selected
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*Theme.BG_PANEL)
            self._fill = Rectangle(pos=self.pos, size=self.size)
            if selected:
                Color(*Theme.PRIMARY)
                self._outline = Line(rectangle=(self.x, self.y, self.width, self.height),
                                      width=3)
            else:
                Color(*Theme.GRID)
                self._outline = Line(rectangle=(self.x, self.y, self.width, self.height),
                                      width=1)


class SettingsScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.name = 'settings'
        # transparent — root bg shows through

        self._current_accent = app_config.get_accent()
        self._current_bg     = app_config.get_background()

        root = BoxLayout(orientation='vertical', padding=(14, 10), spacing=8)
        self.add_widget(root)

        # ── Top header ─────────────────────────────────────────────────
        topbar = BoxLayout(orientation='horizontal', size_hint=(1, None),
                            height=44, spacing=8, padding=(10, 4))
        paint_bg(topbar, Theme.BG_DARK)
        btn_back = RacingButton('back', size_hint=(0.18, 1), font_size=12)
        btn_back.bind(on_release=lambda *a: self._go_back())
        topbar.add_widget(btn_back)
        title = Label(
            text='[size=15][b][color=00ff70]S E T T I N G S[/color][/b][/size]',
            markup=True, halign='center', valign='middle',
            size_hint=(0.64, 1))
        title.bind(size=lambda l, s: setattr(l, 'text_size', s))
        topbar.add_widget(title)
        topbar.add_widget(Label(text='', size_hint=(0.18, 1)))
        root.add_widget(topbar)

        # ── Scrollable content ───────────────────────────────────────
        sv = ScrollView(bar_width=4, bar_color=Theme.PRIMARY)
        content = BoxLayout(orientation='vertical', size_hint_y=None,
                             padding=(6, 6), spacing=14)
        content.bind(minimum_height=content.setter('height'))
        sv.add_widget(content)
        root.add_widget(sv)

        # ── Accent color section ─────────────────────────────────────
        sec_color = self._make_section_header('ACCENT COLOR',
                                                'หลักของ UI')
        content.add_widget(sec_color)

        color_grid = GridLayout(cols=4, size_hint_y=None,
                                  spacing=8, padding=(0, 4))
        color_grid.bind(minimum_height=color_grid.setter('height'))
        self._color_swatches = []
        for hex_c, label in COLOR_PRESETS:
            sw = ColorSwatch(hex_c, label,
                              on_pick=lambda h: self._pick_color(h),
                              size_hint=(1, None), height=72)
            color_grid.add_widget(sw)
            self._color_swatches.append(sw)
            if hex_c.lower() == self._current_accent.lower():
                sw.set_selected(True)
        content.add_widget(color_grid)

        # ── Background section ───────────────────────────────────────
        sec_bg = self._make_section_header('BACKGROUND',
                                             'พื้นหลังของแอป')
        content.add_widget(sec_bg)

        bg_grid = GridLayout(cols=2, size_hint_y=None,
                              spacing=8, padding=(0, 4))
        bg_grid.bind(minimum_height=bg_grid.setter('height'))
        self._bg_swatches = []
        for key, label, sub in BG_PRESETS:
            sw = BgSwatch(key, label, sub,
                           on_pick=lambda k: self._pick_bg(k),
                           size_hint=(1, None), height=70)
            bg_grid.add_widget(sw)
            self._bg_swatches.append(sw)
            if key == self._current_bg:
                sw.set_selected(True)
        content.add_widget(bg_grid)

        # Custom background file picker
        custom_row = BoxLayout(orientation='horizontal', size_hint=(1, None),
                                height=60, spacing=8)
        self.custom_lbl = Label(
            text=f'[size=11]CUSTOM IMAGE: '
                 f'[color=cccccc]{self._current_bg if self._current_bg not in [k for k,_,_ in BG_PRESETS] else "(none)"}[/color][/size]',
            markup=True, color=Theme.TEXT_DIM,
            size_hint=(0.65, 1),
            halign='left', valign='middle')
        self.custom_lbl.bind(size=lambda l, s: setattr(l, 'text_size', s))
        custom_row.add_widget(self.custom_lbl)
        btn_pick = RacingButton('pick image', font_size=12,
                                  size_hint=(0.35, 1))
        btn_pick.bind(on_release=lambda *a: self._pick_custom_image())
        custom_row.add_widget(btn_pick)
        content.add_widget(custom_row)

        # ── Save / Reset bar ─────────────────────────────────────────
        save_row = BoxLayout(orientation='horizontal', size_hint=(1, None),
                              height=64, spacing=8)
        btn_save = RacingButton('save & restart', primary=True, font_size=15,
                                  size_hint=(0.5, 1))
        btn_save.bind(on_release=lambda *a: self._on_save())
        save_row.add_widget(btn_save)
        btn_reset = RacingButton('reset defaults', danger=True, font_size=13,
                                   size_hint=(0.5, 1))
        btn_reset.bind(on_release=lambda *a: self._on_reset())
        save_row.add_widget(btn_reset)
        content.add_widget(save_row)

        # Info line
        info = Label(
            text='[size=10][color=99aaccff]'
                 'การเปลี่ยนสีจะมีผลหลังปิดและเปิดแอปใหม่ '
                 '— พื้นหลังเปลี่ยนทันที[/color][/size]',
            markup=True, size_hint=(1, None), height=28,
            halign='center', valign='middle')
        info.bind(size=lambda l, s: setattr(l, 'text_size', s))
        content.add_widget(info)

    def _make_section_header(self, title, sub):
        head = BoxLayout(orientation='horizontal', size_hint=(1, None),
                          height=30, padding=(8, 0))
        paint_bg(head, Theme.BG_DARK)
        head.add_widget(Label(
            text=f'[size=13][b]{"  ".join(title)}[/b][/size]',
            markup=True, color=Theme.PRIMARY,
            size_hint=(0.5, 1), halign='left', valign='middle'))
        head.children[0].bind(size=lambda l, s: setattr(l, 'text_size', s))
        head.add_widget(Label(
            text=f'[size=10][color=99aaccff]{sub}[/color][/size]',
            markup=True, size_hint=(0.5, 1),
            halign='right', valign='middle'))
        head.children[0].bind(size=lambda l, s: setattr(l, 'text_size', s))
        return head

    # ── Pickers ─────────────────────────────────────────────────────
    def _pick_color(self, hex_c):
        self._current_accent = hex_c
        for sw in self._color_swatches:
            sw.set_selected(sw.hex_color.lower() == hex_c.lower())

    def _pick_bg(self, key):
        self._current_bg = key
        for sw in self._bg_swatches:
            sw.set_selected(sw.key == key)
        self.custom_lbl.text = (f'[size=11]CUSTOM IMAGE: '
                                  f'[color=cccccc](none)[/color][/size]')
        # Apply background immediately
        if hasattr(self.app, 'apply_background'):
            self.app.apply_background(key)

    def _pick_custom_image(self):
        """Open native image picker, then crop dialog for the selected image."""
        from src.widgets.file_picker import pick_image_native

        def _on_picked(path):
            from src.widgets.image_crop_dialog import ImageCropDialog
            ImageCropDialog(path, on_apply=self._on_crop_applied).open()

        pick_image_native(on_pick=_on_picked, title='Pick background image')

    def _on_crop_applied(self, cropped_path):
        """Callback after the crop dialog produces the final image."""
        import os
        self._current_bg = cropped_path
        for sw in self._bg_swatches:
            sw.set_selected(False)
        self.custom_lbl.text = (f'[size=11]CUSTOM IMAGE: '
                                  f'[color=00ff70]{os.path.basename(cropped_path)}'
                                  f'[/color][/size]')
        if hasattr(self.app, 'apply_background'):
            self.app.apply_background(cropped_path)

    # ── Save / Reset ────────────────────────────────────────────────
    def _on_save(self):
        app_config.set_accent(self._current_accent)
        app_config.set_background(self._current_bg)

        # Show confirmation + offer restart
        from kivy.uix.modalview import ModalView
        view = ModalView(size_hint=(0.7, 0.4),
                         background_color=Theme.BG_DARK)
        box = BoxLayout(orientation='vertical', padding=20, spacing=14)
        paint_bg(box, Theme.BG_PANEL, border=Theme.PRIMARY)
        view.add_widget(box)
        box.add_widget(Label(
            text='[size=18][b][color=00ff70]SAVED[/color][/b][/size]',
            markup=True, size_hint=(1, None), height=40))
        box.add_widget(Label(
            text=('บันทึกแล้ว\n\n'
                  'สีหลักจะมีผลหลังเปิดแอปใหม่\n'
                  'พื้นหลังเปลี่ยนทันที'),
            color=Theme.TEXT, halign='center', valign='middle'))
        btn_close = RacingButton('ok', primary=True, font_size=14,
                                   size_hint=(1, None), height=48)
        btn_close.bind(on_release=lambda *a: view.dismiss())
        box.add_widget(btn_close)
        view.open()

    def _on_reset(self):
        self._current_accent = app_config.DEFAULT_ACCENT
        self._current_bg     = app_config.DEFAULT_BG
        for sw in self._color_swatches:
            sw.set_selected(sw.hex_color.lower() == self._current_accent.lower())
        for sw in self._bg_swatches:
            sw.set_selected(sw.key == self._current_bg)
        self.custom_lbl.text = ('[size=11]CUSTOM IMAGE: '
                                  '[color=cccccc](none)[/color][/size]')
        if hasattr(self.app, 'apply_background'):
            self.app.apply_background(self._current_bg)

    def _go_back(self):
        sm = self.app.sm
        target = getattr(self.app, '_prev_screen', 'cockpit')
        if sm.has_screen(target):
            sm.current = target
            self.app.nav._on_tap(target)
