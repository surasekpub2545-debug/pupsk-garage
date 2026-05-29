"""
Road Dyno Calculator
====================
Estimate engine horsepower and torque from logged RPM data, vehicle physics,
and a simplified acceleration model.

This is NOT an actual dynamometer — it's a *road dyno* / *virtual dyno*
that derives power from the bike's own acceleration. Numbers are
approximate (typically within ±10% on a smooth full-throttle run on flat
road, in a single gear, with stable wind/temperature).

Physics
-------
Going faster requires kinetic energy:
    KE = 0.5 × m × v²
Power applied by engine =  d(KE)/dt = m × v × a
where m = mass (kg), v = velocity (m/s), a = acceleration (m/s²).

Add rolling resistance + aerodynamic drag for a more realistic load:
    P_road     = m × g × C_r × v          (rolling)
    P_aero     = 0.5 × ρ × C_d × A × v³   (aerodynamic)
    P_wheel    = m × v × a + P_road + P_aero

Engine HP at flywheel ≈ P_wheel × (1 + driveline_loss)
                     ≈ P_wheel × 1.10–1.15 for chain-drive motorcycles.

Then torque (Nm) = P_engine / ω_engine  (ω in rad/s)
"""
import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional


# ── Default vehicle parameters (Honda Wave 110i — tweak in UI) ──────────────
@dataclass
class VehicleSpec:
    name:               str   = 'Honda Wave 110i (default)'
    mass_kg:            float = 195.0   # bike (100kg) + rider (65kg) + fuel etc.
    wheel_circ_m:       float = 1.745   # 70/90-17 tyre circumference
    overall_gear_ratio: float = 11.5    # engine_rpm / wheel_rpm in active gear
                                          # (gear × primary × final). For Wave 110i 4th
                                          # gear: 1.0 × 3.214 × 3.571 ≈ 11.48
    driveline_loss:     float = 0.12    # 12% loss chain + gearbox + tyre
    rolling_coef:       float = 0.018   # tyre rolling-resistance
    air_density:        float = 1.20    # kg/m³ @ sea level, 25 °C
    drag_coef:          float = 0.95    # bike + rider sitting upright
    frontal_area_m2:    float = 0.55    # rider + small fairing


def rpm_to_speed(rpm: float, spec: VehicleSpec) -> float:
    """Engine RPM → vehicle speed in m/s (assuming `spec.overall_gear_ratio`)"""
    wheel_rps = rpm / 60.0 / spec.overall_gear_ratio
    return wheel_rps * spec.wheel_circ_m


def speed_to_rpm(v_mps: float, spec: VehicleSpec) -> float:
    wheel_rps = v_mps / spec.wheel_circ_m
    return wheel_rps * 60.0 * spec.overall_gear_ratio


def smooth(series: List[float], win: int = 5) -> List[float]:
    """Simple moving-average smoothing"""
    if win <= 1 or len(series) < win: return list(series)
    n = len(series)
    out = [0.0] * n
    half = win // 2
    for i in range(n):
        s = max(0, i - half); e = min(n, i + half + 1)
        out[i] = sum(series[s:e]) / (e - s)
    return out


@dataclass
class DynoSample:
    t:        float    # seconds
    rpm:      float
    speed:    float    # m/s
    accel:    float    # m/s²
    power_w:  float    # watts (engine, after compensating for losses)
    hp:       float    # imperial horsepower
    torque_nm: float


def compute_run(times: List[float], rpms: List[float],
                spec: VehicleSpec,
                smooth_win: int = 7) -> List[DynoSample]:
    """Process raw (time, RPM) samples into a full dyno run.

    Returns a list of DynoSample. Caller is responsible for trimming
    to the part of the trace that represents a real pull (i.e. monotonically
    rising RPM at full throttle in one gear).
    """
    if len(times) < 3: return []
    n = len(times)

    # smooth RPM
    rpm_s = smooth(rpms, smooth_win)
    # speed (m/s)
    v = [rpm_to_speed(r, spec) for r in rpm_s]

    # acceleration (central difference)
    a = [0.0] * n
    for i in range(n):
        i0 = max(0, i-1); i1 = min(n-1, i+1)
        dt = times[i1] - times[i0]
        a[i] = (v[i1] - v[i0]) / dt if dt > 0 else 0
    a = smooth(a, smooth_win)

    g = 9.81
    samples: List[DynoSample] = []
    for i in range(n):
        # power required to accelerate the mass at this instant
        p_acc   = spec.mass_kg * v[i] * a[i]
        # rolling resistance
        p_roll  = spec.rolling_coef * spec.mass_kg * g * v[i]
        # aerodynamic drag
        p_aero  = 0.5 * spec.air_density * spec.drag_coef * \
                  spec.frontal_area_m2 * (v[i] ** 3)
        # wheel power
        p_wheel = p_acc + p_roll + p_aero
        # engine power (compensate for driveline loss)
        p_engine = p_wheel / max(0.1, 1.0 - spec.driveline_loss)
        hp = p_engine / 745.7
        omega = rpm_s[i] * 2 * math.pi / 60.0
        tq = p_engine / omega if omega > 1 else 0
        samples.append(DynoSample(
            t=times[i], rpm=rpm_s[i], speed=v[i], accel=a[i],
            power_w=p_engine, hp=hp, torque_nm=tq))
    return samples


def best_run_window(samples: List[DynoSample],
                     min_accel: float = 0.5) -> Tuple[int, int]:
    """Find the longest contiguous slice of monotonically rising RPM with
    decent acceleration — that's the 'pull' we want to graph."""
    if len(samples) < 5: return (0, len(samples))
    best_s, best_e, best_len = 0, 0, 0
    s = 0
    while s < len(samples):
        e = s + 1
        while e < len(samples) and \
              samples[e].rpm >= samples[e-1].rpm - 50 and \
              samples[e].accel > min_accel:
            e += 1
        if e - s > best_len:
            best_len = e - s; best_s = s; best_e = e
        s = max(e, s + 1)
    if best_len < 5:
        return (0, len(samples))   # fall back to whole run
    return (best_s, best_e)


def peaks(samples: List[DynoSample]) -> Tuple[Optional[DynoSample], Optional[DynoSample]]:
    """Return (peak_hp_sample, peak_torque_sample)."""
    if not samples: return None, None
    peak_hp = max(samples, key=lambda s: s.hp)
    peak_tq = max(samples, key=lambda s: s.torque_nm)
    return peak_hp, peak_tq
