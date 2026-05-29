"""Image crop dialog — drag to position, zoom in/out, locked aspect."""
import os
from kivy.app import App
from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, Line

from . import theme as Theme
from .racing_ui import paint_bg, RacingButton


class _CropCanvas(Widget):
    """Image preview with a locked-aspect crop overlay."""

    def __init__(self, image_path, target_aspect, **kw):
        super().__init__(**kw)
        self.image_path = image_path
        self.target_aspect = target_aspect  # width / height
        try:
            self._tex = CoreImage(image_path).texture
            self.iw, self.ih = self._tex.size
        except Exception:
            self._tex = None
            self.iw, self.ih = 1, 1
        # zoom: 1.0 = max-size centered crop; < 1.0 zooms in
        self._scale = 1.0
        self._cx = 0.0
        self._cy = 0.0
        self._init_crop()
        self._drag = None
        self.bind(pos=lambda *a: self._redraw(),
                  size=lambda *a: self._redraw())

    # ── Geometry helpers ────────────────────────────────────────
    def _crop_size(self):
        """Crop w,h in image pixels at current zoom."""
        ia = self.iw / max(1, self.ih)
        if ia > self.target_aspect:
            max_h = self.ih
            max_w = max_h * self.target_aspect
        else:
            max_w = self.iw
            max_h = max_w / self.target_aspect
        return max_w * self._scale, max_h * self._scale

    def _init_crop(self):
        cw, ch = self._crop_size()
        self._cx = (self.iw - cw) / 2
        self._cy = (self.ih - ch) / 2

    def _clamp(self):
        cw, ch = self._crop_size()
        self._cx = max(0, min(self.iw - cw, self._cx))
        self._cy = max(0, min(self.ih - ch, self._cy))

    def _img_rect(self):
        """Image display rect inside widget (contain mode)."""
        ww, wh = max(1, self.width), max(1, self.height)
        ia = self.iw / max(1, self.ih)
        wa = ww / wh
        if ia > wa:
            dw = ww
            dh = ww / ia
        else:
            dh = wh
            dw = wh * ia
        dx = self.x + (ww - dw) / 2
        dy = self.y + (wh - dh) / 2
        return dx, dy, dw, dh, dw / max(1, self.iw)

    # ── Drawing ─────────────────────────────────────────────────
    def _redraw(self):
        self.canvas.clear()
        if self._tex is None:
            return
        dx, dy, dw, dh, s = self._img_rect()
        cw, ch = self._crop_size()
        rx = dx + self._cx * s
        ry = dy + self._cy * s
        rw = cw * s
        rh = ch * s
        with self.canvas:
            Color(0.05, 0.05, 0.07, 1)
            Rectangle(pos=self.pos, size=self.size)
            # Dim full image
            Color(0.40, 0.40, 0.40, 1)
            Rectangle(texture=self._tex, pos=(dx, dy), size=(dw, dh))
            # Bright crop region (use subtexture)
            try:
                sub = self._tex.get_region(self._cx, self._cy, cw, ch)
                Color(1, 1, 1, 1)
                Rectangle(texture=sub, pos=(rx, ry), size=(rw, rh))
            except Exception:
                pass
            # Crop border
            Color(*Theme.PRIMARY)
            Line(rectangle=(rx, ry, rw, rh), width=2)
            # Rule-of-thirds guides
            pc = Theme.PRIMARY
            Color(pc[0], pc[1], pc[2], 0.35)
            for i in (1, 2):
                Line(points=[rx + rw*i/3, ry, rx + rw*i/3, ry + rh], width=1)
                Line(points=[rx, ry + rh*i/3, rx + rw, ry + rh*i/3], width=1)
            # Corner ticks for visual handles
            Color(*Theme.PRIMARY)
            hl = 16
            for x, y, dx_, dy_ in [
                (rx,        ry,        +1, +1),
                (rx + rw,   ry,        -1, +1),
                (rx,        ry + rh,   +1, -1),
                (rx + rw,   ry + rh,   -1, -1),
            ]:
                Line(points=[x, y, x + dx_ * hl, y], width=3)
                Line(points=[x, y, x, y + dy_ * hl], width=3)

    # ── Interactions ─────────────────────────────────────────────
    def zoom(self, delta):
        self._scale = max(0.20, min(1.0, self._scale + delta))
        self._clamp()
        self._redraw()

    def reset(self):
        self._scale = 1.0
        self._init_crop()
        self._redraw()

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        self._drag = (touch.x, touch.y, self._cx, self._cy)
        return True

    def on_touch_move(self, touch):
        if not self._drag:
            return False
        ax, ay, cx0, cy0 = self._drag
        _, _, _, _, s = self._img_rect()
        if s <= 0:
            return True
        self._cx = cx0 + (touch.x - ax) / s
        self._cy = cy0 + (touch.y - ay) / s
        self._clamp()
        self._redraw()
        return True

    def on_touch_up(self, touch):
        if self._drag:
            self._drag = None
            return True
        return False

    # ── Output ───────────────────────────────────────────────────
    def save_cropped(self, out_path):
        """Crop original image using current region; save to out_path."""
        from PIL import Image as PILImage
        img = PILImage.open(self.image_path)
        cw, ch = self._crop_size()
        # PIL uses top-left origin; our crop is bottom-left
        left = int(round(self._cx))
        right = int(round(self._cx + cw))
        upper = int(round(self.ih - self._cy - ch))
        lower = int(round(self.ih - self._cy))
        left = max(0, min(self.iw, left))
        right = max(left + 1, min(self.iw, right))
        upper = max(0, min(self.ih, upper))
        lower = max(upper + 1, min(self.ih, lower))
        cropped = img.crop((left, upper, right, lower))
        # Convert RGBA→RGB for jpg safety; keep PNG for transparency
        if out_path.lower().endswith(('.jpg', '.jpeg')):
            if cropped.mode != 'RGB':
                cropped = cropped.convert('RGB')
        cropped.save(out_path)
        return out_path


class ImageCropDialog(ModalView):
    """Modal that lets the user crop an image to the screen aspect."""

    def __init__(self, image_path, on_apply, target_aspect=None, **kw):
        kw.setdefault('size_hint', (0.95, 0.94))
        kw.setdefault('background_color', (0, 0, 0, 0))
        kw.setdefault('background', '')
        super().__init__(**kw)
        self.on_apply = on_apply
        self.image_path = image_path

        if target_aspect is None or target_aspect <= 0:
            target_aspect = (Window.width / max(1, Window.height))

        root = BoxLayout(orientation='vertical', padding=10, spacing=8)
        paint_bg(root, Theme.BG_DARK, border=Theme.PRIMARY)
        self.add_widget(root)

        # Header
        hdr = BoxLayout(orientation='horizontal',
                         size_hint=(1, None), height=44)
        title = Label(
            text='[size=20][b][color=00d4ff]'
                 'C R O P   B A C K G R O U N D'
                 '[/color][/b][/size]',
            markup=True, halign='left', valign='middle')
        title.bind(size=lambda l, s: setattr(l, 'text_size', s))
        hdr.add_widget(title)
        root.add_widget(hdr)

        # Hint
        hint = Label(
            text=('[size=13][color=99aaccff]'
                  'ลากเพื่อเลื่อนตำแหน่ง  •  ปุ่ม + / − เพื่อซูม  •  '
                  'reset เพื่อกลับค่าเริ่มต้น'
                  '[/color][/size]'),
            markup=True, size_hint=(1, None), height=26,
            halign='left', valign='middle')
        hint.bind(size=lambda l, s: setattr(l, 'text_size', s))
        root.add_widget(hint)

        # Crop canvas
        self.canvas_w = _CropCanvas(image_path, target_aspect,
                                       size_hint=(1, 1))
        root.add_widget(self.canvas_w)

        # Controls
        ctrl = BoxLayout(orientation='horizontal', size_hint=(1, None),
                          height=58, spacing=10)
        b_zin = RacingButton('zoom +', font_size=15, size_hint=(0.18, 1))
        b_zin.bind(on_release=lambda *a: self.canvas_w.zoom(-0.08))
        ctrl.add_widget(b_zin)
        b_zout = RacingButton('zoom -', font_size=15, size_hint=(0.18, 1))
        b_zout.bind(on_release=lambda *a: self.canvas_w.zoom(+0.08))
        ctrl.add_widget(b_zout)
        b_reset = RacingButton('reset', font_size=15, size_hint=(0.18, 1))
        b_reset.bind(on_release=lambda *a: self.canvas_w.reset())
        ctrl.add_widget(b_reset)
        b_cancel = RacingButton('cancel', danger=True, font_size=15,
                                  size_hint=(0.22, 1))
        b_cancel.bind(on_release=lambda *a: self.dismiss())
        ctrl.add_widget(b_cancel)
        b_apply = RacingButton('apply', primary=True, font_size=15,
                                 size_hint=(0.24, 1))
        b_apply.bind(on_release=lambda *a: self._on_apply())
        ctrl.add_widget(b_apply)
        root.add_widget(ctrl)

    def _on_apply(self):
        app = App.get_running_app()
        out_dir = os.path.join(app.user_data_dir, 'bg')
        try:
            os.makedirs(out_dir, exist_ok=True)
        except Exception:
            out_dir = app.user_data_dir
        out_path = os.path.join(out_dir, 'custom_cropped.png')
        try:
            self.canvas_w.save_cropped(out_path)
        except Exception as e:
            print(f'[crop] save failed: {e}')
            self.dismiss()
            return
        self.dismiss()
        if self.on_apply:
            self.on_apply(out_path)
