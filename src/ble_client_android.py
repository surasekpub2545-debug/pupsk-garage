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

from jnius import autoclass, cast, PythonJavaClass, java_method

# ── Java classes ────────────────────────────────────────────────────
BluetoothAdapter            = autoclass('android.bluetooth.BluetoothAdapter')
BluetoothGatt               = autoclass('android.bluetooth.BluetoothGatt')
BluetoothGattCharacteristic = autoclass('android.bluetooth.BluetoothGattCharacteristic')
BluetoothGattDescriptor     = autoclass('android.bluetooth.BluetoothGattDescriptor')
UUID                        = autoclass('java.util.UUID')
PythonActivity              = autoclass('org.kivy.android.PythonActivity')

# Super Connext UUIDs (short forms — match on substring of 128-bit form)
HM10_SERVICE_UUID = 'ffe0'
HM10_CHAR_UUID    = 'ffe1'
BLE5_SERVICE_UUID = 'fff0'
BLE5_NOTIFY_UUID  = 'fff1'
BLE5_WRITE_UUID   = 'fff2'
CCCD_UUID         = '00002902-0000-1000-8000-00805f9b34fb'


# ── ScanCallback (Java interface) ───────────────────────────────────
class _ScanCB(PythonJavaClass):
    __javainterfaces__ = ['android/bluetooth/le/ScanCallback']
    __javacontext__    = 'app'

    def __init__(self, on_result):
        super().__init__()
        self._on_result = on_result

    @java_method('(ILandroid/bluetooth/le/ScanResult;)V')
    def onScanResult(self, callback_type, result):
        try:
            self._on_result(result)
        except Exception as e:
            print(f'[ble-android] scan_result err: {e}')

    @java_method('(Ljava/util/List;)V')
    def onBatchScanResults(self, results):
        try:
            for i in range(results.size()):
                self._on_result(results.get(i))
        except Exception as e:
            print(f'[ble-android] batch_results err: {e}')

    @java_method('(I)V')
    def onScanFailed(self, error_code):
        print(f'[ble-android] scan failed: {error_code}')


# ── BluetoothGattCallback (Java abstract class) ─────────────────────
class _GattCB(PythonJavaClass):
    __javainterfaces__ = ['android/bluetooth/BluetoothGattCallback']
    __javacontext__    = 'app'

    def __init__(self, client):
        super().__init__()
        self.client = client

    @java_method('(Landroid/bluetooth/BluetoothGatt;II)V')
    def onConnectionStateChange(self, gatt, status, newState):
        # 2 = STATE_CONNECTED
        if newState == 2:
            try: gatt.discoverServices()
            except Exception: pass
        else:
            self.client._on_disconnected()

    @java_method('(Landroid/bluetooth/BluetoothGatt;I)V')
    def onServicesDiscovered(self, gatt, status):
        self.client._on_services_discovered(gatt, status)

    @java_method('(Landroid/bluetooth/BluetoothGatt;Landroid/bluetooth/BluetoothGattCharacteristic;)V')
    def onCharacteristicChanged(self, gatt, ch):
        try:
            val = ch.getValue()
            if val is not None:
                self.client._on_notify_bytes(bytes(val))
        except Exception: pass

    @java_method('(Landroid/bluetooth/BluetoothGatt;Landroid/bluetooth/BluetoothGattCharacteristic;I)V')
    def onCharacteristicWrite(self, gatt, ch, status):
        pass

    @java_method('(Landroid/bluetooth/BluetoothGatt;Landroid/bluetooth/BluetoothGattDescriptor;I)V')
    def onDescriptorWrite(self, gatt, desc, status):
        pass


# ── Public client ───────────────────────────────────────────────────
class AndroidBleClient:
    def __init__(self):
        self.adapter = BluetoothAdapter.getDefaultAdapter()
        self.scanner = None
        try:
            if self.adapter is not None:
                self.scanner = self.adapter.getBluetoothLeScanner()
        except Exception: pass
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

    # ── Callbacks ──────────────────────────────────────────
    def set_data_callback(self, cb):
        self._on_packet = cb

    @property
    def connected(self) -> bool:
        return self._connected

    # ── Scan ───────────────────────────────────────────────
    async def scan(self, timeout: float = 6.0):
        if self.scanner is None:
            return []
        self._scan_results = {}
        self._scan_cb = _ScanCB(self._on_scan_result)
        try:
            self.scanner.startScan(self._scan_cb)
        except Exception as e:
            print(f'[ble-android] startScan err: {e}')
            return []
        await asyncio.sleep(timeout)
        try: self.scanner.stopScan(self._scan_cb)
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
                        for kw in ('connext', 'ecu', 'hm-10', 'hm10', 'bt05')))
                out.append({
                    'address':       addr,
                    'name':          name or '(unnamed)',
                    'rssi':          info.get('rssi'),
                    'relevant':      relevant,
                    'service_uuids': uuids,
                })
        out.sort(key=lambda d: (not d['relevant'], -(d.get('rssi') or -100)))
        return out

    def _on_scan_result(self, result):
        try:
            dev  = result.getDevice()
            addr = dev.getAddress()
            name = ''
            try: name = dev.getName() or ''
            except Exception: pass
            rssi = result.getRssi()
            uuids = []
            try:
                rec = result.getScanRecord()
                if rec is not None:
                    svc_uuids = rec.getServiceUuids()
                    if svc_uuids is not None:
                        for i in range(svc_uuids.size()):
                            u = svc_uuids.get(i).toString().lower()
                            uuids.append(u)
            except Exception: pass
            with self._scan_lock:
                self._scan_results[addr] = {
                    'name': name, 'rssi': rssi, 'uuids': uuids}
        except Exception as e:
            print(f'[ble-android] _on_scan_result err: {e}')

    # ── Connect / disconnect ───────────────────────────────
    async def connect(self, address: str) -> bool:
        if self.adapter is None:
            return False
        try:
            dev = self.adapter.getRemoteDevice(address)
        except Exception as e:
            print(f'[ble-android] getRemoteDevice err: {e}')
            return False
        if dev is None:
            return False
        loop = asyncio.get_running_loop()
        self._connect_loop = loop
        self._connect_future = loop.create_future()
        self._gatt_cb = _GattCB(self)
        try:
            ctx = PythonActivity.mActivity.getApplicationContext()
            # autoConnect = False, TRANSPORT_LE = 2
            try:
                self._gatt = dev.connectGatt(ctx, False, self._gatt_cb, 2)
            except Exception:
                self._gatt = dev.connectGatt(ctx, False, self._gatt_cb)
        except Exception as e:
            print(f'[ble-android] connectGatt err: {e}')
            return False
        try:
            ok = await asyncio.wait_for(self._connect_future, timeout=20.0)
        except asyncio.TimeoutError:
            ok = False
        return ok

    def _on_services_discovered(self, gatt, status):
        if status != 0:
            self._resolve_connect(False); return
        # Pick the right service / characteristics
        for svc_short in (BLE5_SERVICE_UUID, HM10_SERVICE_UUID):
            svc = self._find_service(gatt, svc_short)
            if svc is None:
                continue
            if svc_short == HM10_SERVICE_UUID:
                ch = self._find_char(svc, HM10_CHAR_UUID)
                if ch:
                    self._notify_char = ch
                    self._write_char  = ch
                    break
            else:
                nc = self._find_char(svc, BLE5_NOTIFY_UUID)
                wc = self._find_char(svc, BLE5_WRITE_UUID)
                if nc and wc:
                    self._notify_char = nc
                    self._write_char  = wc
                    break
        if self._notify_char is None or self._write_char is None:
            self._resolve_connect(False); return

        # Enable notifications
        try:
            gatt.setCharacteristicNotification(self._notify_char, True)
            cccd = self._notify_char.getDescriptor(
                UUID.fromString(CCCD_UUID))
            if cccd is not None:
                cccd.setValue(
                    BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)
                gatt.writeDescriptor(cccd)
        except Exception as e:
            print(f'[ble-android] enable notify err: {e}')

        self._connected = True
        self._resolve_connect(True)

    def _find_service(self, gatt, short_uuid):
        try:
            services = gatt.getServices()
        except Exception:
            return None
        for i in range(services.size()):
            svc = services.get(i)
            if short_uuid in svc.getUuid().toString().lower():
                return svc
        return None

    def _find_char(self, svc, short_uuid):
        try:
            chars = svc.getCharacteristics()
        except Exception:
            return None
        for i in range(chars.size()):
            ch = chars.get(i)
            if short_uuid in ch.getUuid().toString().lower():
                return ch
        return None

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
        self._rx_buf.extend(data)
        while True:
            try: lf = self._rx_buf.index(0x0A)
            except ValueError: return
            line = bytes(self._rx_buf[:lf])
            del self._rx_buf[:lf + 1]
            try:
                text = line.decode('utf-8', errors='replace').strip('\r')
            except Exception: continue
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
