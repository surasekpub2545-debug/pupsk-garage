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
        void onCharChanged(BluetoothGatt gatt, BluetoothGattCharacteristic ch);
        void onCharWrite(BluetoothGatt gatt, BluetoothGattCharacteristic ch, int status);
        void onDescriptorWrite(BluetoothGatt gatt, BluetoothGattDescriptor desc, int status);
    }

    private final Listener listener;

    public BleGattHelper(Listener listener) {
        this.listener = listener;
    }

    @Override
    public void onConnectionStateChange(BluetoothGatt gatt, int status, int newState) {
        if (listener != null) listener.onConnState(gatt, status, newState);
    }

    @Override
    public void onServicesDiscovered(BluetoothGatt gatt, int status) {
        if (listener != null) listener.onServicesDiscovered(gatt, status);
    }

    @Override
    public void onCharacteristicChanged(BluetoothGatt gatt, BluetoothGattCharacteristic ch) {
        if (listener != null) listener.onCharChanged(gatt, ch);
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
