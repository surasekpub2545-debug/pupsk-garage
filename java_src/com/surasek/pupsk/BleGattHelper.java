package com.surasek.pupsk;

import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;

/**
 * BluetoothGattCallback is an abstract class.  pyjnius's PythonJavaClass
 * proxy can only implement interfaces, not abstract classes, so we make
 * a thin Java subclass that forwards every event to a pure-Java interface
 * (Listener).  The Python side then implements that interface.
 */
public class BleGattHelper extends BluetoothGattCallback {

    public interface Listener {
        void onConnState(BluetoothGatt gatt, int status, int newState);
        void onServicesDiscovered(BluetoothGatt gatt, int status);
        // Notification payload is passed as a String (Latin-1 of the raw
        // bytes) so the Python side gets the data directly instead of
        // calling getValue(), which returns null on API 33+.
        void onCharChangedValue(String latin1);
        void onCharWrite(BluetoothGatt gatt, BluetoothGattCharacteristic ch, int status);
        void onDescriptorWrite(BluetoothGatt gatt, BluetoothGattDescriptor desc, int status);
    }

    private final Listener listener;

    public BleGattHelper(Listener listener) {
        this.listener = listener;
    }

    private void emit(byte[] value) {
        if (listener == null || value == null) return;
        // Latin-1 keeps every byte 1:1 so Python can re-encode losslessly.
        try {
            listener.onCharChangedValue(new String(value, "ISO-8859-1"));
        } catch (Exception e) {
            // ignore
        }
    }

    @Override
    public void onConnectionStateChange(BluetoothGatt gatt, int status, int newState) {
        if (listener != null) listener.onConnState(gatt, status, newState);
    }

    @Override
    public void onServicesDiscovered(BluetoothGatt gatt, int status) {
        if (listener != null) listener.onServicesDiscovered(gatt, status);
    }

    // Legacy callback (API ≤ 32) — read value off the characteristic.
    @Override
    public void onCharacteristicChanged(BluetoothGatt gatt, BluetoothGattCharacteristic ch) {
        if (ch != null) emit(ch.getValue());
    }

    // API 33+ callback — value supplied directly, getValue() may be null.
    @Override
    public void onCharacteristicChanged(BluetoothGatt gatt, BluetoothGattCharacteristic ch, byte[] value) {
        emit(value);
    }

    @Override
    public void onCharacteristicWrite(BluetoothGatt gatt, BluetoothGattCharacteristic ch, int status) {
        if (listener != null) listener.onCharWrite(gatt, ch, status);
    }

    @Override
    public void onDescriptorWrite(BluetoothGatt gatt, BluetoothGattDescriptor desc, int status) {
        if (listener != null) listener.onDescriptorWrite(gatt, desc, status);
    }
}
