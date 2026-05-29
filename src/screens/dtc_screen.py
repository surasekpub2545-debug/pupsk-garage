"""DTC screen — racing-style read / clear diagnostic trouble codes."""
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle, Line

from src.widgets import theme as Theme
from src.widgets.racing_ui import paint_bg, RacingButton
from src.protocol import super_connext, honda_dtc


class DTCScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.name = 'dtc'
        # transparent — root bg shows through

        root = BoxLayout(orientation='vertical', padding=(10, 8), spacing=6)
        self.add_widget(root)

        # Header strip
        head = BoxLayout(orientation='horizontal', size_hint=(1, None),
                          height=36, padding=(10, 4))
        paint_bg(head, Theme.BG_DARK)
        head.add_widget(Label(
            text='[size=15][b][color=00ff70]D T C[/color][/b][/size]',
            markup=True, size_hint=(0.5, 1), halign='left', valign='middle'))
        head.children[0].bind(size=lambda l, s: setattr(l, 'text_size', s))
        head.add_widget(Label(
            text='[size=11]TROUBLE CODES[/size]',
            markup=True, color=Theme.TEXT_DIM,
            size_hint=(0.5, 1), halign='right', valign='middle'))
        head.children[0].bind(size=lambda l, s: setattr(l, 'text_size', s))
        root.add_widget(head)

        # Actions row
        actions = BoxLayout(orientation='horizontal', size_hint=(1, None),
                             height=64, spacing=8)
        btn_read = RacingButton('read codes', primary=True, font_size=16,
                                  size_hint=(0.5, 1))
        btn_read.bind(on_release=lambda *a: self._on_read())
        actions.add_widget(btn_read)
        btn_clear = RacingButton('clear codes', danger=True, font_size=16,
                                   size_hint=(0.5, 1))
        btn_clear.bind(on_release=lambda *a: self._on_clear())
        actions.add_widget(btn_clear)
        root.add_widget(actions)

        # Status
        self.status_lbl = Label(
            text='[size=12]TAP READ CODES TO SCAN ECU[/size]',
            markup=True, color=Theme.TEXT_DIM,
            size_hint=(1, None), height=28,
            halign='center', valign='middle')
        self.status_lbl.bind(size=lambda l, s: setattr(l, 'text_size', s))
        root.add_widget(self.status_lbl)

        # DTC list
        sv = ScrollView(bar_width=4, bar_color=Theme.PRIMARY)
        self.dtc_box = BoxLayout(orientation='vertical', size_hint_y=None,
                                   spacing=6, padding=4)
        self.dtc_box.bind(minimum_height=self.dtc_box.setter('height'))
        sv.add_widget(self.dtc_box)
        root.add_widget(sv)

    def _on_read(self):
        if not self.app.ble.connected:
            self.status_lbl.text = ('[size=12][color=ff173f]'
                                      'NOT CONNECTED — TAP CONNECT FIRST[/color][/size]')
            return
        self.status_lbl.text = ('[size=12][color=ffc600]'
                                  'READING CODES…[/color][/size]')
        self.dtc_box.clear_widgets()
        self.app.submit_async(self.app.ble.write(super_connext.CMD_READ_DTC))

    def _on_clear(self):
        if not self.app.ble.connected:
            self.status_lbl.text = ('[size=12][color=ff173f]'
                                      'NOT CONNECTED — TAP CONNECT FIRST[/color][/size]')
            return
        self.status_lbl.text = ('[size=12][color=ffc600]'
                                  'CLEARING CODES…[/color][/size]')
        self.app.submit_async(self.app.ble.write(super_connext.CMD_CLEAR_DTC))

    def on_dtc_response(self, dtc):
        if dtc is None:
            self.status_lbl.text = ('[size=12][color=ff173f]'
                                      'PARSE ERROR[/color][/size]')
            return
        self.dtc_box.clear_widgets()
        if dtc.count == 0 or not dtc.codes:
            self.status_lbl.text = ('[size=12][color=00ff70]'
                                      'NO ACTIVE CODES[/color][/size]')
            self.dtc_box.add_widget(
                self._row('--', 'NO ACTIVE TROUBLE CODES', ok=True))
            return
        self.status_lbl.text = (f'[size=12]FOUND [color=ff173f][b]'
                                  f'{dtc.count}[/b][/color] DTC(S)[/size]')
        for code in dtc.codes:
            desc = honda_dtc.lookup(code, 'th')
            self.dtc_box.add_widget(self._row(code, desc))

    def on_clear_done(self):
        self.status_lbl.text = ('[size=12][color=00ff70]'
                                  'CODES CLEARED OK[/color][/size]')
        self.dtc_box.clear_widgets()

    def _row(self, code, desc, ok=False):
        row = BoxLayout(orientation='horizontal', size_hint=(1, None),
                         height=64, spacing=8, padding=(12, 8))
        col_accent = Theme.PRIMARY if ok else Theme.DANGER
        # Racing panel with red accent strip
        with row.canvas.before:
            Color(*Theme.BG_PANEL)
            row._bg = Rectangle(pos=row.pos, size=row.size)
            Color(*Theme.GRID)
            row._outline = Line(rectangle=(row.x, row.y, row.width, row.height), width=1)
            Color(*col_accent)
            row._strip = Rectangle(pos=(row.x, row.y), size=(4, row.height))
        def _resize(*a):
            row._bg.pos = row.pos; row._bg.size = row.size
            row._outline.rectangle = (row.x, row.y, row.width, row.height)
            row._strip.pos = (row.x, row.y); row._strip.size = (4, row.height)
        row.bind(pos=_resize, size=_resize)

        lbl_code = Label(text=f'[size=22][b]{code}[/b][/size]',
                          markup=True, color=col_accent,
                          size_hint=(0.22, 1),
                          halign='left', valign='middle')
        lbl_code.bind(size=lambda l, s: setattr(l, 'text_size', s))
        row.add_widget(lbl_code)
        lbl_desc = Label(text=desc, color=Theme.TEXT, font_size=13,
                          size_hint=(0.78, 1),
                          halign='left', valign='middle')
        lbl_desc.bind(size=lambda l, s: setattr(l, 'text_size', s))
        row.add_widget(lbl_desc)
        return row
