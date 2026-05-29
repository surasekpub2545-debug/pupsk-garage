"""
GPS speed provider — wraps plyer.gps for Android, falls back gracefully
on desktop.

The speed value is updated by the system and accessible via `current_kmh`.
Subscribe via `set_speed_callback(cb)` for push updates.

Usage:
    gps = GpsProvider()
    gps.start()
    gps.set_speed_callback(lambda kmh: print(kmh))
    ...
    gps.stop()
"""
import threading


class GpsProvider:
    def __init__(self):
        self.current_kmh = 0.0
        self._cb = None
        self._active = False
        self._impl = None
        self._lock = threading.Lock()

    def set_speed_callback(self, cb):
        self._cb = cb

    # ── Lifecycle ────────────────────────────────────────────────────
    def start(self) -> bool:
        """Try to start GPS. Returns True if started, False if unavailable."""
        if self._active: return True
        try:
            from plyer import gps  # type: ignore
            self._impl = gps
            gps.configure(on_location=self._on_location,
                          on_status=self._on_status)
            gps.start(minTime=200, minDistance=0)   # 5 Hz, every meter
            self._active = True
            return True
        except (ImportError, NotImplementedError, Exception) as e:
            # Desktop / unsupported platform — no GPS
            self._impl = None
            self._active = False
            return False

    def stop(self):
        if not self._active or self._impl is None: return
        try: self._impl.stop()
        except Exception: pass
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    # ── Plyer callbacks ────────────────────────────────────────────────
    def _on_location(self, **kw):
        # plyer GPS sends speed in m/s
        speed_ms = kw.get('speed', 0) or 0
        try: kmh = float(speed_ms) * 3.6
        except Exception: kmh = 0.0
        with self._lock:
            self.current_kmh = kmh
        if self._cb:
            try: self._cb(kmh)
            except Exception: pass

    def _on_status(self, stype, status):
        pass
