"""
BLE client for Super Connext box.

Uses `bleak` on desktop and the pyjnius-backed AndroidBleClient on Android.
The two implementations share the same public API so the rest of the app
doesn't care which is in play.

Box advertises two possible service layouts:
  HM-10:  service FFE0, char FFE1 (read + write + notify on one char)
  BLE 5:  service FFF0, char FFF1 (notify), FFF2 (write)
We auto-detect which is present after connect.
"""
import asyncio
from typing import Callable, Optional


# Pick the right backend at module load.  On Android, jnius is importable
# and the AndroidBleClient replaces the desktop bleak-based class below.
try:
    import jnius  # noqa: F401
    from src.ble_client_android import AndroidBleClient as BleClient
    _USING_ANDROID = True
except Exception:
    _USING_ANDROID = False

# UUIDs
HM10_SERVICE = '0000ffe0-0000-1000-8000-00805f9b34fb'
HM10_CHAR    = '0000ffe1-0000-1000-8000-00805f9b34fb'
BLE5_SERVICE = '0000fff0-0000-1000-8000-00805f9b34fb'
BLE5_NOTIFY  = '0000fff1-0000-1000-8000-00805f9b34fb'
BLE5_WRITE   = '0000fff2-0000-1000-8000-00805f9b34fb'


if _USING_ANDROID:
    # `BleClient` is already aliased to AndroidBleClient — skip the desktop
    # bleak implementation below.
    pass


class _DesktopBleClient:
    """Async client wrapping bleak.BleakClient with Super Connext semantics.

    Usage:
        client = BleClient()
        await client.scan()                  # → list of (name, address)
        await client.connect(address)
        client.set_data_callback(on_packet)  # called with each \\n-terminated chunk
        await client.write(b'$RDTC\\r\\n')
        await client.disconnect()
    """

    def __init__(self):
        self._client = None              # bleak.BleakClient
        self._notify_char = None
        self._write_char  = None
        self._rx_buf      = bytearray()
        self._on_packet: Optional[Callable[[str], None]] = None
        self._connected   = False

    # ── Scan ─────────────────────────────────────────────────────────────
    async def scan(self, timeout: float = 6.0):
        """Return list of (name, address) for BLE devices that look like
        Super Connext (advertise FFE0 or FFF0 service)."""
        from bleak import BleakScanner
        devices = []
        try:
            found = await BleakScanner.discover(timeout=timeout, return_adv=True)
            # found = {address: (BLEDevice, AdvertisementData)}
            for addr, (dev, adv) in found.items():
                uuids = [u.lower() for u in (adv.service_uuids or [])]
                name = (dev.name or adv.local_name or '').strip()
                # Filter: match service UUID OR name containing common keywords
                relevant = (HM10_SERVICE in uuids or BLE5_SERVICE in uuids or
                            any(kw in name.lower() for kw in
                                ('connext', 'ecu', 'hm-10', 'hm10', 'bt05')))
                devices.append({
                    'address':   addr,
                    'name':      name or '(unnamed)',
                    'rssi':      getattr(adv, 'rssi', None) or getattr(dev, 'rssi', None),
                    'relevant':  relevant,
                    'service_uuids': uuids,
                })
        except Exception as e:
            return []
        # Put relevant ones first
        devices.sort(key=lambda d: (not d['relevant'], -(d.get('rssi') or -100)))
        return devices

    # ── Connect / Disconnect ─────────────────────────────────────────────
    async def connect(self, address: str) -> bool:
        from bleak import BleakClient
        try:
            self._client = BleakClient(address, timeout=15.0)
            await self._client.connect()
            # Wait 700ms (Super Connext APK pattern) for service discovery to settle
            await asyncio.sleep(0.7)
            services = self._client.services
            # Pick characteristics based on what's exposed
            for svc in services:
                if svc.uuid.lower() == BLE5_SERVICE:
                    for ch in svc.characteristics:
                        u = ch.uuid.lower()
                        if u == BLE5_NOTIFY:
                            self._notify_char = ch
                        elif u == BLE5_WRITE:
                            self._write_char = ch
                elif svc.uuid.lower() == HM10_SERVICE:
                    for ch in svc.characteristics:
                        if ch.uuid.lower() == HM10_CHAR:
                            self._notify_char = ch
                            self._write_char  = ch
            if self._notify_char is None or self._write_char is None:
                await self._client.disconnect()
                return False
            await self._client.start_notify(self._notify_char, self._on_notify)
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    async def disconnect(self):
        if self._client is not None:
            try:
                if self._notify_char is not None:
                    await self._client.stop_notify(self._notify_char)
            except Exception: pass
            try:
                await self._client.disconnect()
            except Exception: pass
        self._connected = False
        self._client = None
        self._notify_char = None
        self._write_char  = None

    @property
    def connected(self) -> bool:
        return self._connected

    # ── Write ────────────────────────────────────────────────────────────
    async def write(self, data: bytes):
        if self._client is None or self._write_char is None: return
        await self._client.write_gatt_char(self._write_char, data, response=False)

    # ── Callbacks ────────────────────────────────────────────────────────
    def set_data_callback(self, cb: Callable[[str], None]):
        """Set callback invoked for each LF-terminated text chunk."""
        self._on_packet = cb

    def _on_notify(self, sender, data: bytearray):
        """Internal: accumulate RX bytes and emit complete lines on \\n."""
        self._rx_buf.extend(data)
        while True:
            try:
                lf = self._rx_buf.index(0x0A)
            except ValueError:
                return
            line = bytes(self._rx_buf[:lf])
            del self._rx_buf[:lf + 1]
            try:
                text = line.decode('utf-8', errors='replace').strip('\r')
            except Exception:
                continue
            if self._on_packet:
                try:
                    self._on_packet(text)
                except Exception: pass


# Expose desktop class under the public name when not on Android
if not _USING_ANDROID:
    BleClient = _DesktopBleClient
