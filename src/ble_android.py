"""
Android-native BLE backend (pyjnius).

Used INSIDE the Android APK because bleak doesn't work natively there.
On desktop, `ble_client.py` (bleak) is used. The interface mirrors BleClient
so cockpit/connect screens don't need to know which backend is active.

To use:
    from src.ble_android import AndroidBleClient as BleClient
"""
import threading

try:
    from jnius import autoclass, cast, PythonJavaClass, java_method
    from android.runnable import run_on_ui_thread
    ANDROID = True
except Exception:
    ANDROID = False


# Lazy imports — only when actually on Android
def _import_classes():
    BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
    BluetoothManager = autoclass('android.bluetooth.BluetoothManager')
    BluetoothGatt    = autoclass('android.bluetooth.BluetoothGatt')
    BluetoothGattCharacteristic = autoclass('android.bluetooth.BluetoothGattCharacteristic')
    BluetoothGattDescriptor     = autoclass('android.bluetooth.BluetoothGattDescriptor')
    PythonActivity   = autoclass('org.kivy.android.PythonActivity')
    Context          = autoclass('android.content.Context')
    UUID             = autoclass('java.util.UUID')
    return locals()


# Stub for desktop testing
class AndroidBleClient:
    def __init__(self):
        if not ANDROID:
            raise RuntimeError('AndroidBleClient only works on Android. '
                                'Use BleClient from ble_client.py for desktop.')
        # TODO: implement on-device scan via BluetoothLeScanner
        # TODO: implement connect via BluetoothDevice.connectGatt
        # TODO: implement write via writeCharacteristic
        # TODO: implement notifications via setCharacteristicNotification + descriptor write
        raise NotImplementedError(
            'Android BLE backend stub. '
            'Will be implemented in Sprint 2 after desktop flow works.')
