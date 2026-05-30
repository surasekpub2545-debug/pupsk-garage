"""Dyno chart + trigger settings popup.

Consolidates the four RPM fields (chart range min/max, trigger start/stop)
plus the optional redline marker so the Dyno screen itself can be just
header + live readout + run buttons + chart, giving the chart back the
vertical space that was previously eaten by inline TextInputs.
"""
from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput

from src.widgets import theme as Theme
from src.widgets.racing_ui import paint_bg, RacingButton


_FIELDS = [
    # (key,           label,                  units,  color,         hint)
    ('chart_rpm_min', 'CHART RPM MIN',        'rpm',  Theme.PRIMARY, 'ขอบซ้ายของกราฟ'),
    ('chart_rpm_max', 'CHART RPM MAX',        'rpm',  Theme.PRIMARY, 'ขอบขวาของกราฟ'),
    ('redline',       'REDLINE',              'rpm',  Theme.DANGER,
     'เส้นแดงในกราฟ (ว่าง = ไม่แสดง)'),
    ('trig_start',    'TRIGGER START RPM',    'rpm',  Theme.WARNING,
     'รอบที่เริ่มบันทึกอัตโนมัติ'),
    ('trig_stop',     'TRIGGER STOP RPM',     'rpm',  Theme.DANGER,
     'รอบที่หยุดบันทึกอัตโนมัติ'),
]


class DynoSettingsPopup(ModalView):
    def __init__(self, current_values: dict, on_save, **kw):
        kw.setdefault('size_hint', (0.78, 0.88))
        kw.setdefault('background_color', (0, 0, 0, 0.75))
        kw.setdefault('background', '')
        super().__init__(**kw)
        self.on_save = on_save
        self.inputs = {}

        wrap = BoxLayout(orientation='vertical', padding=(20, 16), spacing=12)
        paint_bg(wrap, Theme.BG_PANEL, border=Theme.PRIMARY, border_width=2)
        self.add_widget(wrap)

        # Header
        wrap.add_widget(Label(
            text='[size=22][b][color=00d4ff]'
                 'D Y N O   S E T T I N G S'
                 '[/color][/b][/size]',
            markup=True, size_hint=(1, None), height=42,
            halign='center', valign='middle'))
        wrap.add_widget(Label(
            text='[size=14][color=99aabb]'
                 'ตั้งค่ากราฟและจุด trigger ของ Dyno'
                 '[/color][/size]',
            markup=True, size_hint=(1, None), height=24,
            halign='center', valign='middle'))

        # Rows
        for key, label, units, color, hint in _FIELDS:
            row = self._make_row(key, label, units, color, hint,
                                  current_values.get(key, 0))
            wrap.add_widget(row)

        # Actions
        actions = BoxLayout(orientation='horizontal', size_hint=(1, None),
                             height=60, spacing=10)
        btn_cancel = RacingButton('cancel', danger=True, font_size=18,
                                    size_hint=(0.4, 1))
        btn_cancel.bind(on_release=lambda *a: self.dismiss())
        actions.add_widget(btn_cancel)
        btn_save = RacingButton('apply', primary=True, font_size=20,
                                  size_hint=(0.6, 1))
        btn_save.bind(on_release=lambda *a: self._on_save())
        actions.add_widget(btn_save)
        wrap.add_widget(actions)

    def _make_row(self, key, label, units, color, hint, current):
        row = BoxLayout(orientation='vertical', size_hint=(1, None),
                         height=82, spacing=4, padding=(12, 6))
        paint_bg(row, Theme.BG_DARK, border=Theme.GRID)

        head = BoxLayout(orientation='horizontal', size_hint=(1, None),
                          height=26)
        lbl = Label(
            text=f'[size=16][b]{"  ".join(label)}[/b][/size]   '
                 f'[size=13][color=99aabb]{units}[/color][/size]',
            markup=True, color=color,
            size_hint=(0.7, 1), halign='left', valign='middle')
        lbl.bind(size=lambda l, s: setattr(l, 'text_size', s))
        head.add_widget(lbl)
        row.add_widget(head)

        body = BoxLayout(orientation='horizontal', size_hint=(1, None),
                          height=44, spacing=8)
        # Allow blank for redline (means disabled).  All others numeric.
        is_redline = (key == 'redline')
        display = '' if (is_redline and not current) else f'{int(current)}'
        inp = TextInput(
            text=display, size_hint=(0.35, 1),
            background_color=Theme.BG_PANEL,
            foreground_color=color, cursor_color=color,
            font_size=20, halign='center', multiline=False,
            hint_text='—' if is_redline else '')
        body.add_widget(inp)
        self.inputs[key] = inp

        h = Label(
            text=f'[size=13][color=778899]{hint}[/color][/size]',
            markup=True, size_hint=(0.65, 1),
            halign='left', valign='middle')
        h.bind(size=lambda l, s: setattr(l, 'text_size', s))
        body.add_widget(h)
        row.add_widget(body)

        return row

    def _on_save(self):
        out = {}
        for key, inp in self.inputs.items():
            txt = (inp.text or '').strip()
            if key == 'redline' and not txt:
                out[key] = 0
                continue
            try:
                out[key] = float(txt)
            except ValueError:
                continue
        try:
            self.on_save(out)
        except Exception as e:
            print(f'[dyno settings save] {e}')
        self.dismiss()
