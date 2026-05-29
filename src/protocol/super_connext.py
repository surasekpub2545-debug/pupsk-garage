"""
Super Connext BLE box — Honda protocol parser.

Connection: BLE GATT
  HM-10:  service FFE0, char FFE1 (read+write)
  BLE5:   service FFF0, char FFF1 (notify), FFF2 (write)

Commands (ASCII, end with \\r\\n):
  $RDTC          read trouble codes
  $CDTC          clear trouble codes
  $RELAYON{pw}   relay on (antitheft unlock)
  $RELAYOFF{pw}  relay off

Live data is sent continuously by the box (no request needed):
  &M[17 fields × 4 hex digits][4-digit checksum]\\n   (76 chars total)

Other responses:
  &RDTC[count][3 DTC codes 4-hex each]\\n
  &CDTCDONE   clear success
  &INFO...    device info / status
  &ID...      device serial number

The box handles all K-Line timing internally — we just exchange ASCII.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class HondaLiveData:
    """One frame of live ECU data parsed from `&M...`"""
    rpm:           int      # engine RPM
    spd:           int      # speed (km/h)
    tps_deg:       float    # throttle position (degrees, max 100)
    tps_v:         float    # TPS sensor voltage
    ect_c:         float    # engine coolant temp (°C)
    ect_v:         float    # ECT sensor voltage
    iat_c:         float    # intake air temp (°C)
    iat_v:         float    # IAT sensor voltage
    map_kpa:       int      # manifold absolute pressure (kPa)
    map_v:         float    # MAP sensor voltage
    isc:           float    # idle speed control
    injector:      float    # injector duration (ms)
    ig_deg:        float    # ignition timing (°BTDC)
    baro:          int      # barometric pressure (kPa)
    afr:           float    # air-fuel ratio
    trim:          float    # fuel trim (%)
    status:        int      # status flags
    valid:         bool     # checksum OK


def _hex4(s: str, i: int) -> int:
    """Parse 4 hex chars at offset i as integer."""
    return int(s[i:i+4], 16)


def parse_live_data(raw: str, mode: int = 1, fw_major: int = 2) -> Optional[HondaLiveData]:
    """Parse a `&M...` live-data frame from the Super Connext box.

    Args:
        raw:       full text containing `&M` somewhere (no trailing \\n)
        mode:      Honda firmware mode (1 = ECT/IAT raw-40, 2 = raw-80)
        fw_major:  box firmware major version (>=2 uses /10 IAT volt scale)

    Returns:
        HondaLiveData if frame is well-formed, else None.
    """
    if '&M' not in raw:
        return None
    # Find &M position
    idx = raw.find('&M')
    body = raw[idx + 2:]      # skip "&M"

    # Expect 17 fields × 4 hex = 68 chars + 4-char checksum = 72 hex chars
    if len(body) < 72:
        return None
    body = body[:72]

    # Parse 17 raw values + checksum
    try:
        raws = [_hex4(body, i*4) for i in range(17)]
        chksum_recv = int(body[68:72], 16)
    except ValueError:
        return None

    # Checksum: sum of every hex digit in the 17-field payload
    payload_hex = body[:68]
    chksum_calc = sum(int(c, 16) for c in payload_hex) & 0xFFFF
    valid = (chksum_calc == chksum_recv)

    # Apply Honda formulas (from APK analysis)
    rpm        = raws[0]                                  # RPM = raw * 1 (value_rpmx=1 for Honda)
    spd        = raws[1]
    tps_deg    = min(100.0, raws[2] / 2.0)
    tps_v      = raws[3] * 5000.0 / 256.0 / 1000.0
    ect_c      = float(raws[4] - 40 if mode == 1 else raws[4] - 80)
    ect_v      = raws[5] * 5000.0 / 256.0 / 1000.0
    iat_c      = float(raws[6] - 40 if mode == 1 else raws[6] - 80)
    if fw_major >= 2:
        iat_v  = raws[7] / 10.0
    else:
        iat_v  = raws[7] * 5000.0 / 256.0 / 1000.0
    map_kpa    = raws[8]
    map_v      = raws[9] * 5000.0 / 256.0 / 1000.0
    isc        = raws[10] * 5000.0 / 256.0
    injector   = 0.0 if raws[11] == 65535 else raws[11] / 1000.0
    ig_deg     = 0.0 if raws[12] == 0     else raws[12] / 2.0 - 64.0
    baro       = raws[13]
    afr        = raws[14] / 10.0
    trim       = 0.0 if raws[15] == 0     else (raws[15] - 128) * 0.78
    status     = raws[16]

    return HondaLiveData(
        rpm=rpm, spd=spd, tps_deg=tps_deg, tps_v=tps_v,
        ect_c=ect_c, ect_v=ect_v, iat_c=iat_c, iat_v=iat_v,
        map_kpa=map_kpa, map_v=map_v, isc=isc, injector=injector,
        ig_deg=ig_deg, baro=baro, afr=afr, trim=trim, status=status,
        valid=valid,
    )


@dataclass
class DTCResponse:
    """Parsed `&RDTC...` response."""
    count:     int
    codes:     list    # up to 3 4-hex-digit codes


def parse_dtc(raw: str) -> Optional[DTCResponse]:
    """Parse `&RDTC[count][CD1][CD2][CD3]\\n`. Returns None if malformed."""
    idx = raw.find('&RDTC')
    if idx < 0: return None
    body = raw[idx + 5:]      # after "&RDTC"
    if len(body) < 14:        # 2 + 4 + 4 + 4
        return None
    try:
        count = int(body[0:2], 16)
        codes = [body[2:6], body[6:10], body[10:14]]
        codes = [c for c in codes if c not in ('0000', '')]
        return DTCResponse(count=count, codes=codes)
    except ValueError:
        return None


# ── Command builders ─────────────────────────────────────────────────────
CMD_READ_DTC  = b'$RDTC\r\n'
CMD_CLEAR_DTC = b'$CDTC\r\n'

def cmd_relay_on(password: str) -> bytes:
    return f'$RELAYON{password}\r\n'.encode('ascii')

def cmd_relay_off(password: str) -> bytes:
    return f'$RELAYOFF{password}\r\n'.encode('ascii')

def cmd_antitheft_on(password: str) -> bytes:
    return f'$ANTION{password}\r\n'.encode('ascii')

def cmd_antitheft_off(password: str) -> bytes:
    return f'$ANTIOFF{password}\r\n'.encode('ascii')
