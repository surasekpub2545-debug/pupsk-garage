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
        """Try to start GPS. Returns True if started, False if unavailable.

        On Android, the LocationListener fires from a Java thread; pyjnius
        invokes the Python callback through a JNI proxy.  If anything in
        that chain raises (typical on emulators without a real GPS provider
        like BlueStacks), the process is killed with SIGABRT.  We treat
        every exception as "no GPS available" so the rest of the app keeps
        running and the cockpit falls back to ECU speed.
        """
        if self._active: return True
        try:
            from plyer import gps  # type: ignore
        except Exception:
            self._impl = None; self._active = False
            return False
        try:
            gps.configure(on_location=self._on_location,
                          on_status=self._on_status)
        except Exception as e:
            print(f'[gps] configure failed: {e}')
            self._impl = None; self._active = False
            return False
        try:
            gps.start(minTime=200, minDistance=0)   # 5 Hz, every meter
        except Exception as e:
            print(f'[gps] start failed: {e}')
            self._impl = None; self._active = False
            return False
        self._impl = gps
        self._active = True
        return True

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
        # plyer GPS sends speed in m/s.
        # Runs on the Java LocationListener thread via a JNI proxy; any
        # exception that escapes here can abort the process, so swallow
        # everything.
        try:
            speed_ms = kw.get('speed', 0) or 0
            kmh = float(speed_ms) * 3.6
            with self._lock:
                self.current_kmh = kmh
            if self._cb:
                self._cb(kmh)
        except Exception as e:
            try: print(f'[gps] on_location err: {e}')
            except Exception: pass

    def _on_status(self, stype, status):
        pass
