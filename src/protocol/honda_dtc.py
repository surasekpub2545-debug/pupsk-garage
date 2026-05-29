"""Honda DTC code lookup — loads honda_dtc_codes.csv at startup."""
import csv, os, sys
from dataclasses import dataclass


@dataclass
class DTCInfo:
    raw_hex:      str    # e.g. '0101'
    display_code: str    # e.g. '01-01'
    english:      str
    thai:         str


_TABLE = {}   # raw_hex → DTCInfo


def _csv_path() -> str:
    """Locate honda_dtc_codes.csv — works in both dev and packaged APK."""
    # Try standard packaging locations first
    for base in [
        os.path.dirname(os.path.abspath(__file__)),
        os.path.dirname(os.path.abspath(__file__)) + '/../../assets',
        os.getcwd() + '/assets',
        os.path.dirname(sys.argv[0]) + '/assets',
    ]:
        p = os.path.join(base, 'honda_dtc_codes.csv')
        if os.path.exists(p):
            return p
    return ''


def load_dtc_table() -> int:
    """Load the CSV into memory. Returns count of entries."""
    path = _csv_path()
    if not path:
        return 0
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                hex_code = row.get('raw_hex', '').strip()
                if not hex_code:
                    continue
                _TABLE[hex_code.upper()] = DTCInfo(
                    raw_hex     = hex_code,
                    display_code= row.get('display_code', '').strip(),
                    english     = row.get('english', '').strip(),
                    thai        = row.get('thai', '').strip(),
                )
        return len(_TABLE)
    except Exception:
        return 0


def lookup(raw_hex: str, lang: str = 'th') -> str:
    """Get a human-readable description for a DTC.
    raw_hex: 4-char hex (e.g. '0101')
    lang:    'th' or 'en'
    """
    info = _TABLE.get(raw_hex.upper())
    if info is None:
        return f'Unknown code {raw_hex}'
    desc = info.thai if lang == 'th' and info.thai else info.english
    if not desc:
        desc = f'(no description)'
    return f'{info.display_code}: {desc}'
