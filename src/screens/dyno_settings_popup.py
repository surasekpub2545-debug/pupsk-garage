"""
Vehicle settings popup for the Dyno screen.
Lets the user edit all vehicle spec fields (mass, gear, tire, loss
coefficients, aerodynamics) plus auto-trigger RPM thresholds.
"""
import math
from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.graphics import Color, Rectangle, Line

from src.widgets import theme as Theme
from src.widgets.racing_ui import paint_bg, RacingButton


# All editable fields:
#   (key, label, units, default, color, tooltip)
SPEC_FIELDS = [
    ('tire',         'Tire size',          '(e.g. 70/90-17)', '70/90-17', Theme.WARNING,
     'ขนาดยางหลัง — จะคำนวณเส้นรอบวงให้เอง'),
    ('mass',         'Mass',               'kg',         '195',      Theme.PRIMARY,
     'น้ำหนักรวม รถ + คนขับ + น้ำมัน'),
    ('gear',         'Gear ratio',         'eng:wheel',  '11.5',     Theme.PRIMARY,
     'อัตราทดรวม (เกียร์ที่ใช้ทำดยโน × primary × final)'),
    ('driveline',    'Driveline loss',     '0-1',        '0.12',     Theme.ACCENT,
     'อัตราการสูญเสียในระบบส่งกำลัง 0.10-0.15'),
    ('rolling',      'Rolling coef',       'Cr',         '0.018',    Theme.ACCENT,
     'สัมประสิทธิ์แรงต้านยาง 0.012-0.025'),
    ('drag',         'Drag coef',          'Cd',         '0.95',     Theme.ACCENT,
     'สัมประสิทธิ์แรงต้านอากาศ 0.85-1.10'),
    ('air_density',  'Air density',        'kg/m³',      '1.20',     Theme.ACCENT,
     'ความหนาแน่นอากาศ (ที่ราบ ~1.20)'),
    ('frontal_area', 'Frontal area',       'm²',         '0.55',     Theme.ACCENT,
     'พื้นที่หน้าตัดรถ + คน 0.5-0.7'),
]


def _parse_tire(s):
    """Parse '70/90-17' → wheel circumference in meters."""
    import re
    m = re.match(r'^\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*[-Rr/]\s*(\d+(?:\.\d+)?)\s*$', s)
    if not m: return None
    W = float(m.group(1)); A = float(m.group(2)); R = float(m.group(3))
    d_mm = R * 25.4 + 2 * (W * A / 100.0)
    return math.pi * d_mm / 1000.0


class VehicleSettingsPopup(ModalView):
    """Modal popup for editing all vehicle spec values."""
    def __init__(self, current_values: dict, on_save, **kw):
        kw.setdefault('size_hint', (0.85, 0.92))
        kw.setdefault('background_color', (0, 0, 0, 0.75))
        kw.setdefault('background', '')
        super().__init__(**kw)
        self.on_save = on_save
        self.inputs = {}

        # Container with racing panel background
        wrap = BoxLayout(orientation='vertical', padding=(18, 14),
                          spacing=10)
        paint_bg(wrap, Theme.BG_PANEL, border=Theme.PRIMARY, border_width=2)
        self.add_widget(wrap)

        # Header
        wrap.add_widget(Label(
            text='[size=24][b][color=00d4ff]V E H I C L E   S E T T I N G S[/color][/b][/size]',
            markup=True, size_hint=(1, None), height=40,
            halign='center', valign='middle'))

        # Sub
        wrap.add_widget(Label(
            text='[size=15][color=99aabb]ตั้งค่าข้อมูลรถสำหรับคำนวณ HP / Nm[/color][/size]',
            markup=True, size_hint=(1, None), height=24,
            halign='center', valign='middle'))

        # Scrollable spec fields
        sv = ScrollView(bar_width=4, bar_color=Theme.PRIMARY)
        grid = GridLayout(cols=1, size_hint_y=None, spacing=8, padding=(4, 4))
        grid.bind(minimum_height=grid.setter('height'))
        sv.add_widget(grid)
        wrap.add_widget(sv)

        for key, label, units, default, color, tip in SPEC_FIELDS:
            row = self._make_row(key, label, units, default, color, tip,
                                  current_values.get(key, default))
            grid.add_widget(row)

        # Bottom action row
        actions = BoxLayout(orientation='horizontal', size_hint=(1, None),
                              height=56, spacing=8)
        btn_cancel = RacingButton('cancel', danger=True, font_size=18,
                                    size_hint=(0.4, 1))
        btn_cancel.bind(on_release=lambda *a: self.dismiss())
        actions.add_widget(btn_cancel)
        btn_save = RacingButton('save', primary=True, font_size=20,
                                  size_hint=(0.6, 1))
        btn_save.bind(on_release=lambda *a: self._on_save())
        actions.add_widget(btn_save)
        wrap.add_widget(actions)

    def _make_row(self, key, label, units, default, color, tip, current):
        """Build a single labelled input row."""
        row_wrap = BoxLayout(orientation='vertical', size_hint=(1, None),
                              height=88, spacing=4, padding=(12, 6))
        paint_bg(row_wrap, Theme.BG_DARK, border=Theme.GRID)

        # Label + units
        head = BoxLayout(orientation='horizontal', size_hint=(1, None),
                          height=26)
        lbl = Label(text=f'[size=16][b]  '
                          + '  '.join(label.upper())
                          + f'  [/b][/size]   '
                          f'[size=14][color=99aabb]{units}[/color][/size]',
                     markup=True, color=color,
                     size_hint=(0.7, 1),
                     halign='left', valign='middle')
        lbl.bind(size=lambda l, s: setattr(l, 'text_size', s))
        head.add_widget(lbl)
        row_wrap.add_widget(head)

        # Input + hint
        body = BoxLayout(orientation='horizontal', size_hint=(1, None),
                          height=44, spacing=8)
        inp = TextInput(
            text=str(current), size_hint=(0.4, 1),
            background_color=Theme.BG_PANEL,
            foreground_color=color, cursor_color=color,
            font_size=20, halign='center', multiline=False)
        body.add_widget(inp)
        self.inputs[key] = inp

        hint = Label(
            text=f'[size=14][color=778899]{tip}[/color][/size]',
            markup=True, size_hint=(0.6, 1),
            halign='left', valign='middle')
        hint.bind(size=lambda l, s: setattr(l, 'text_size', s))
        body.add_widget(hint)
        row_wrap.add_widget(body)

        return row_wrap

    def _on_save(self):
        values = {}
        for key, inp in self.inputs.items():
            values[key] = inp.text.strip()
        # Convert tire size → wheel_circ if applicable
        circ = _parse_tire(values.get('tire', ''))
        if circ is not None:
            values['wheel_circ_m'] = circ
        try:
            self.on_save(values)
        except Exception as e:
            print(f'[settings save] {e}')
        self.dismiss()
