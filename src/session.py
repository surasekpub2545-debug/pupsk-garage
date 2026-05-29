"""
Session recorder + player.

Recorder captures every live-data packet to memory; save() writes a JSON
file.  Player loads a saved file and ticks samples back through a callback
that drives the same UI dispatch path used by live BLE data.
"""
import os
import json
import time
from collections import namedtuple
from kivy.clock import Clock


PlaybackSample = namedtuple(
    'PlaybackSample',
    't rpm tps_deg ect_c iat_c spd injector ig_deg map_kpa afr valid')


class SessionRecorder:
    """Captures live-data samples in memory; save to JSON on stop."""

    def __init__(self):
        self.samples = []
        self._t0 = None
        self.is_active = False

    def start(self):
        self.samples = []
        self._t0 = time.time()
        self.is_active = True

    def stop(self):
        self.is_active = False

    def append(self, ld):
        if not self.is_active or self._t0 is None:
            return
        t = time.time() - self._t0
        self.samples.append({
            't':         round(t, 3),
            'rpm':       getattr(ld, 'rpm', 0),
            'tps_deg':   getattr(ld, 'tps_deg', 0),
            'ect_c':     getattr(ld, 'ect_c', 0),
            'iat_c':     getattr(ld, 'iat_c', 0),
            'spd':       getattr(ld, 'spd', 0),
            'injector':  getattr(ld, 'injector', 0),
            'ig_deg':    getattr(ld, 'ig_deg', 0),
            'map_kpa':   getattr(ld, 'map_kpa', 0),
            'afr':       getattr(ld, 'afr', 0),
        })

    def save(self, path, label=''):
        data = {
            'version': 1,
            'created': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'label':   label,
            'samples': self.samples,
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        return path

    @property
    def elapsed(self) -> float:
        if self._t0 is None or not self.is_active:
            return 0.0
        return time.time() - self._t0


class SessionPlayer:
    """Replays a saved session via a Clock-driven tick."""

    def __init__(self, on_sample):
        self.on_sample = on_sample
        self.samples = []
        self.duration = 0.0
        self.t = 0.0
        self.speed = 1.0
        self.is_playing = False
        self.is_loaded = False
        self._event = None
        self._idx = 0

    # ── Load / close ────────────────────────────────────────
    def load(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.samples = data.get('samples', [])
        self.duration = self.samples[-1]['t'] if self.samples else 0
        self.is_loaded = True
        self.t = 0.0
        self._idx = 0
        # Emit first sample so UI shows something
        if self.samples:
            self.on_sample(self._sample_to_ld(self.samples[0]))

    def close(self):
        self.pause()
        self.samples = []
        self.duration = 0
        self.t = 0.0
        self.is_loaded = False
        self._idx = 0

    # ── Transport ───────────────────────────────────────────
    def play(self):
        if not self.is_loaded or self.is_playing:
            return
        if self.t >= self.duration:
            self.seek(0)
        self.is_playing = True
        if self._event is None:
            self._event = Clock.schedule_interval(self._tick, 1/30.0)

    def pause(self):
        self.is_playing = False
        if self._event:
            self._event.cancel()
            self._event = None

    def toggle(self):
        if self.is_playing: self.pause()
        else: self.play()

    def seek(self, t):
        if not self.is_loaded: return
        self.t = max(0, min(self.duration, t))
        # Find current sample index for this time
        self._idx = 0
        for i, s in enumerate(self.samples):
            if s['t'] > self.t:
                break
            self._idx = i
        if self._idx < len(self.samples):
            self.on_sample(self._sample_to_ld(self.samples[self._idx]))

    def set_speed(self, speed: float):
        self.speed = max(0.1, min(8.0, speed))

    # ── Internal ─────────────────────────────────────────────
    def _tick(self, dt):
        if not self.is_playing:
            return
        self.t += dt * self.speed
        if self.t >= self.duration:
            self.t = self.duration
            self.pause()
            if self.samples:
                self.on_sample(self._sample_to_ld(self.samples[-1]))
            return
        while self._idx + 1 < len(self.samples) and \
              self.samples[self._idx + 1]['t'] <= self.t:
            self._idx += 1
            self.on_sample(self._sample_to_ld(self.samples[self._idx]))

    @staticmethod
    def _sample_to_ld(s):
        return PlaybackSample(
            t=s.get('t', 0),
            rpm=s.get('rpm', 0),       tps_deg=s.get('tps_deg', 0),
            ect_c=s.get('ect_c', 0),   iat_c=s.get('iat_c', 0),
            spd=s.get('spd', 0),       injector=s.get('injector', 0),
            ig_deg=s.get('ig_deg', 0), map_kpa=s.get('map_kpa', 0),
            afr=s.get('afr', 0),       valid=True)
