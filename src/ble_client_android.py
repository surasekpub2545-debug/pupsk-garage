"""
pyjnius-backed BLE client for Android.

Mirrors the bleak-based BleClient API used on desktop:
    set_data_callback(cb)
    async scan(timeout) → list of {address, name, rssi, relevant, service_uuids}
    async connect(address) → bool
    async disconnect()
    async write(bytes)
    connected (property)

Java callbacks run on JNI threads.  Async functions wait on asyncio futures
that callbacks resolve via call_soon_threadsafe.
"""
import asyncio
import threading
from typing import Callable, Optional

from jnius import PythonJavaClass, java_method

# Java classes are loaded lazily on first use, NOT at module import.
# Importing them at module load can race the JNI bootstrap and crash
# the whole app before Kivy is on screen.
BluetoothAdapter            = None
BluetoothGatt               = None
BluetoothGattCharacteristic = None
BluetoothGattDescriptor     = None
UUID                        = None
PythonActivity              = None


BleGattHelper = None  # com.surasek.pupsk.BleGattHelper — our Java wrapper


def _ensure_java():
    """Load the Android Java classes the first time we need them."""
    global BluetoothAdapter, BluetoothGatt, BluetoothGattCharacteristic
    global BluetoothGattDescriptor, UUID, PythonActivity, BleGattHelper
    if BluetoothAdapter is not None:
        return
    from jnius import autoclass
    BluetoothAdapter            = autoclass('android.bluetooth.BluetoothAdapter')
    BluetoothGatt               = autoclass('android.bluetooth.BluetoothGatt')
    BluetoothGattCharacteristic = autoclass('android.bluetooth.BluetoothGattCharacteristic')
    BluetoothGattDescriptor     = autoclass('android.bluetooth.BluetoothGattDescriptor')
    UUID                        = autoclass('java.util.UUID')
    PythonActivity              = autoclass('org.kivy.android.PythonActivity')
    try:
        BleGattHelper = autoclass('com.surasek.pupsk.BleGattHelper')
    except Exception as e:
        print(f'[ble-android] BleGattHelper unavailable: {e}')
        BleGattHelper = None

# Super Connext UUIDs (short forms — match on substring of 128-bit form)
HM10_SERVICE_UUID = 'ffe0'
HM10_CHAR_UUID    = 'ffe1'
BLE5_SERVICE_UUID = 'fff0'
BLE5_NOTIFY_UUID  = 'fff1'
BLE5_WRITE_UUID   = 'fff2'
CCCD_UUID         = '00002902-0000-1000-8000-00805f9b34fb'


# ── LeScanCallback (legacy interface — pyjnius can implement) ────────
# The modern android.bluetooth.le.ScanCallback is an abstract CLASS,
# which pyjnius's PythonJavaClass refuses with
#   "ScanCallback is not an interface" / IllegalArgumentException.
# BluetoothAdapter.LeScanCallback is the legacy interface that we CAN
# implement directly. Deprecated since API 21 but still functional.
class _ScanCB(PythonJavaClass):
    __javainterfaces__ = [
        'android/bluetooth/BluetoothAdapter$LeScanCallback']
    __javacontext__ = 'app'

    def __init__(self, on_result):
        super().__init__()
        self._on_result = on_result

    @java_method('(Landroid/bluetooth/BluetoothDevice;I[B)V')
    def onLeScan(self, device, rssi, scanRecord):
        try:
            self._on_result(device, rssi, scanRecord)
        except Exception as e:
            print(f'[ble-android] LeScan cb err: {e}')


# ── BleGattHelper.Listener (Java interface — pyjnius can implement) ──
# Implements the wrapper interface defined in our Java helper
# (com.surasek.pupsk.BleGattHelper.Listener) so we can hand it to a
# Java-side BluetoothGattCallback subclass without pyjnius needing to
# subclass an abstract Java class itself.
class _GattCB(PythonJavaClass):
    __javainterfaces__ = ['com/surasek/pupsk/BleGattHelper$Listener']
    __javacontext__    = 'app'

    def __init__(self, client):
        super().__init__()
        self.client = client

    @java_method('(Landroid/bluetooth/BluetoothGatt;II)V')
    def onConnState(self, gatt, status, newState):
        self.client._log(f'onConnState status={status} state={newState}')
        if newState == 2:                  # STATE_CONNECTED
            try:
                ok = gatt.discoverServices()
                self.client._log(f'discoverServices()={ok}')
            except Exception as e:
                self.client._log(f'discoverServices err: {e}')
        else:
            self.client._on_disconnected()

    @java_method('(Landroid/bluetooth/BluetoothGatt;I)V')
    def onServicesDiscovered(self, gatt, status):
        self.client._on_services_discovered(gatt, status)

    @java_method('(Ljava/lang/String;)V')
    def onCharChangedValue(self, latin1):
        # Java sends the notification payload as an ISO-8859-1 string so
        # getValue() (null on API 33+) is never needed. Re-encode 1:1.
        try:
            if latin1:
                self.client._on_notify_bytes(latin1.encode('latin-1'))
        except Exception as e:
            print(f'[ble-android] notify decode err: {e}')

    @java_method('(Landroid/bluetooth/BluetoothGatt;Landroid/bluetooth/BluetoothGattCharacteristic;I)V')
    def onCharWrite(self, gatt, ch, status):
        pass

    @java_method('(Landroid/bluetooth/BluetoothGatt;Landroid/bluetooth/BluetoothGattDescriptor;I)V')
    def onDescriptorWrite(self, gatt, desc, status):
        pass


# ── Public client ───────────────────────────────────────────────────
class AndroidBleClient:
    def __init__(self):
        _ensure_java()
        try:
            self.adapter = BluetoothAdapter.getDefaultAdapter()
        except Exception as e:
            print(f'[ble-android] getDefaultAdapter err: {e}')
            self.adapter = None
        self._scan_cb       = None
        self._scan_results  = {}
        self._scan_lock     = threading.Lock()
        self._gatt          = None
        self._gatt_cb       = None
        self._notify_char   = None
        self._write_char    = None
        self._connected     = False
        self._connect_future: Optional[asyncio.Future] = None
        self._connect_loop: Optional[asyncio.AbstractEventLoop] = None
        self._on_packet: Optional[Callable[[str], None]] = None
        self._rx_buf        = bytearray()
        self.last_diag      = ''
        self.rx_bytes       = 0
        self.rx_packets     = 0
        self.log_lines      = []   # on-screen diagnostic log

    def _log(self, msg):
        """Record a diagnostic line (also printed to logcat) so the
        connect screen can show what's happening without adb."""
        try:
            print(f'[ble-android] {msg}')
            self.log_lines.append(msg)
            # keep last 25 lines
            if len(self.log_lines) > 25:
                self.log_lines = self.log_lines[-25:]
        except Exception:
            pass

    # ── Callbacks ──────────────────────────────────────────
    def set_data_callback(self, cb):
        self._on_packet = cb

    @property
    def connected(self) -> bool:
        return self._connected

    # ── Scan (legacy BluetoothAdapter.startLeScan) ─────────
    async def scan(self, timeout: float = 6.0):
        if self.adapter is None:
            return []
        self._scan_results = {}
        self._scan_cb = _ScanCB(self._on_scan_result)
        try:
            ok = bool(self.adapter.startLeScan(self._scan_cb))
            if not ok:
                print('[ble-android] startLeScan returned false')
                return []
        except Exception as e:
            print(f'[ble-android] startLeScan err: {e}')
            return []
        await asyncio.sleep(timeout)
        try: self.adapter.stopLeScan(self._scan_cb)
        except Exception: pass

        out = []
        with self._scan_lock:
            for addr, info in self._scan_results.items():
                name = info.get('name', '') or ''
                uuids = info.get('uuids', [])
                relevant = (
                    any(HM10_SERVICE_UUID in u for u in uuids) or
                    any(BLE5_SERVICE_UUID in u for u in uuids) or
                    any(kw in name.lower()
                        for kw in ('scnext', 'connext', 'ecu',
                                    'hm-10', 'hm10', 'bt05')))
                out.append({
                    'address':       addr,
                    'name':          name or '(unnamed)',
                    'rssi':          info.get('rssi'),
                    'relevant':      relevant,
                    'service_uuids': uuids,
                })
        out.sort(key=lambda d: (not d['relevant'], -(d.get('rssi') or -100)))
        return out

    def _on_scan_result(self, device, rssi, scan_record):
        try:
            addr = device.getAddress()
            name = ''
            try: name = device.getName() or ''
            except Exception: pass
            # Parse 128-bit service UUIDs out of the raw scan record bytes.
            # Type 0x06 = incomplete list of 128-bit UUIDs,
            # type 0x07 = complete list. Each UUID is 16 bytes,
            # little-endian.
            uuids = []
            try:
                if scan_record is not None:
                    raw = bytes(scan_record)
                    i = 0
                    while i < len(raw):
                        length = raw[i]
                        if length == 0 or i + length >= len(raw): break
                        t = raw[i + 1]
                        body = raw[i + 2 : i + 1 + length]
                        if t in (0x06, 0x07):    # 128-bit UUIDs
                            n = len(body) // 16
                            for j in range(n):
                                u = body[j*16:(j+1)*16][::-1].hex()
                                uuids.append(
                                    f'{u[:8]}-{u[8:12]}-{u[12:16]}-'
                                    f'{u[16:20]}-{u[20:]}')
                        elif t in (0x02, 0x03):  # 16-bit UUIDs
                            for j in range(0, len(body), 2):
                                if j + 2 <= len(body):
                                    short = int.from_bytes(
                                        body[j:j+2], 'little')
                                    uuids.append(f'{short:04x}')
                        elif t in (0x08, 0x09) and not name:
                            # 0x08 = shortened name, 0x09 = complete name.
                            # Decode strictly and drop non-printable bytes
                            # so a corrupt advert doesn't show as garbage.
                            try:
                                nm = body.decode('utf-8', 'ignore')
                                nm = ''.join(ch for ch in nm if ch.isprintable())
                                if nm.strip():
                                    name = nm.strip()
                            except Exception: pass
                        i += length + 1
            except Exception as e:
                print(f'[ble-android] parse scanRecord err: {e}')
            # Final sanitize on whatever getName() / advert gave us
            try:
                name = ''.join(ch for ch in name if ch.isprintable()).strip()
            except Exception:
                name = ''
            with self._scan_lock:
                self._scan_results[addr] = {
                    'name': name, 'rssi': rssi, 'uuids': uuids}
        except Exception as e:
            print(f'[ble-android] _on_scan_result err: {e}')

    # ── Connect / disconnect ───────────────────────────────
    async def connect(self, address: str) -> bool:
        self.log_lines = []
        self._log(f'connect {address}')
        if self.adapter is None:
            self._log('adapter is None'); return False
        try:
            dev = self.adapter.getRemoteDevice(address)
        except Exception as e:
            self._log(f'getRemoteDevice err: {e}'); return False
        if dev is None:
            self._log('remote device None'); return False
        loop = asyncio.get_running_loop()
        self._connect_loop = loop
        self._connect_future = loop.create_future()
        if BleGattHelper is None:
            self._log('BleGattHelper Java class MISSING'); return False
        self._log('BleGattHelper OK')
        self._gatt_listener = _GattCB(self)
        self._gatt_cb = BleGattHelper(self._gatt_listener)
        try:
            ctx = PythonActivity.mActivity.getApplicationContext()
            try:
                self._gatt = dev.connectGatt(ctx, False, self._gatt_cb, 2)
            except Exception:
                self._gatt = dev.connectGatt(ctx, False, self._gatt_cb)
            self._log('connectGatt called')
        except Exception as e:
            self._log(f'connectGatt err: {e}'); return False
        try:
            ok = await asyncio.wait_for(self._connect_future, timeout=20.0)
        except asyncio.TimeoutError:
            self._log('TIMEOUT (20s) — no callback fired')
            ok = False
        return ok

    # BluetoothGattCharacteristic property bit flags
    PROP_WRITE_NO_RESP = 0x04
    PROP_WRITE         = 0x08
    PROP_NOTIFY        = 0x10
    PROP_INDICATE      = 0x20

    def _on_services_discovered(self, gatt, status):
        if status != 0:
            self._log(f'discovery status={status}')
            self._resolve_connect(False); return

        notify_ch = None
        write_ch  = None
        notify_is_indicate = False
        diag_lines = []

        try:
            services = gatt.getServices()
        except Exception as e:
            self._log(f'getServices err: {e}')
            self._resolve_connect(False); return

        for i in range(services.size()):
            svc = services.get(i)
            su = svc.getUuid().toString().lower()
            # Skip the two generic services to keep the diagnostic short
            if su.startswith('00001800') or su.startswith('00001801'):
                continue
            diag_lines.append(f'SVC {su[:8]}')
            try:
                chars = svc.getCharacteristics()
            except Exception:
                continue
            for j in range(chars.size()):
                ch = chars.get(j)
                cu = ch.getUuid().toString().lower()
                props = ch.getProperties()
                flags = ''
                if props & self.PROP_NOTIFY:        flags += 'N'
                if props & self.PROP_INDICATE:      flags += 'I'
                if props & self.PROP_WRITE:         flags += 'W'
                if props & self.PROP_WRITE_NO_RESP: flags += 'w'
                diag_lines.append(f'  {cu[:8]} [{flags}]')

                # Notify/indicate characteristic — first one wins, but a
                # known UUID (fff1/ffe1) is preferred.
                if (props & (self.PROP_NOTIFY | self.PROP_INDICATE)):
                    prefer = (BLE5_NOTIFY_UUID in cu or HM10_CHAR_UUID in cu)
                    if notify_ch is None or prefer:
                        notify_ch = ch
                        notify_is_indicate = bool(
                            props & self.PROP_INDICATE and
                            not props & self.PROP_NOTIFY)
                # Write characteristic
                if (props & (self.PROP_WRITE | self.PROP_WRITE_NO_RESP)):
                    prefer = (BLE5_WRITE_UUID in cu or HM10_CHAR_UUID in cu)
                    if write_ch is None or prefer:
                        write_ch = ch

        self.last_diag = '\n'.join(diag_lines) or '(no custom services)'
        for dl in diag_lines:
            self._log(dl)

        if notify_ch is None:
            self._log('NO notify/indicate char found')
            self._resolve_connect(False); return
        # If no dedicated write char, reuse the notify char (HM-10 style)
        if write_ch is None:
            write_ch = notify_ch

        self._notify_char = notify_ch
        self._write_char  = write_ch

        # Enable notifications / indications + write the CCCD
        try:
            gatt.setCharacteristicNotification(self._notify_char, True)
            cccd = self._notify_char.getDescriptor(
                UUID.fromString(CCCD_UUID))
            if cccd is not None:
                if notify_is_indicate:
                    cccd.setValue(
                        BluetoothGattDescriptor.ENABLE_INDICATION_VALUE)
                else:
                    cccd.setValue(
                        BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)
                wd = gatt.writeDescriptor(cccd)
                self._log(f'notify enabled, CCCD write={wd}')
            else:
                self._log('CCCD descriptor missing')
        except Exception as e:
            self._log(f'enable notify err: {e}')

        self._connected = True
        self._resolve_connect(True)

    def _resolve_connect(self, ok: bool):
        f = self._connect_future
        loop = self._connect_loop
        if f is None or loop is None or f.done():
            return
        loop.call_soon_threadsafe(f.set_result, ok)

    def _on_disconnected(self):
        self._connected = False
        # Fail any pending connect attempt
        self._resolve_connect(False)

    def _on_notify_bytes(self, data: bytes):
        # Diagnostic counter — surfaced on the connect screen so we can
        # tell "no notifications at all" apart from "data arrives but
        # doesn't parse".
        try:
            self.rx_bytes = getattr(self, 'rx_bytes', 0) + len(data)
            self.rx_packets = getattr(self, 'rx_packets', 0)
        except Exception: pass
        self._rx_buf.extend(data)
        while True:
            try: lf = self._rx_buf.index(0x0A)
            except ValueError: return
            line = bytes(self._rx_buf[:lf])
            del self._rx_buf[:lf + 1]
            try:
                text = line.decode('utf-8', errors='replace').strip('\r')
            except Exception: continue
            try: self.rx_packets = getattr(self, 'rx_packets', 0) + 1
            except Exception: pass
            if self._on_packet:
                try: self._on_packet(text)
                except Exception: pass

    async def disconnect(self):
        if self._gatt is not None:
            try: self._gatt.disconnect()
            except Exception: pass
            try: self._gatt.close()
            except Exception: pass
        self._gatt        = None
        self._notify_char = None
        self._write_char  = None
        self._connected   = False

    # ── Write ──────────────────────────────────────────────
    async def write(self, data: bytes):
        if self._gatt is None or self._write_char is None:
            return
        try:
            self._write_char.setValue(bytearray(data))
            self._write_char.setWriteType(
                BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE)
            self._gatt.writeCharacteristic(self._write_char)
        except Exception as e:
            print(f'[ble-android] write err: {e}')
