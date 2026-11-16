"""
OXPlayer DSP Accelerator Module
Provides C++ accelerated Audio FFT, 10-Band Biquad Equalizer, RMS Leveling, and Soft Limiter.
"""

import os
import sys
import ctypes
import math

_dll = None

def _load_dsp_dll():
    global _dll
    if _dll is not None:
        return _dll

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(base_dir, "core_bin", "ox_dsp_accel.dll"),
        os.path.join(base_dir, "ox_dsp_accel.dll"),
        os.path.join(getattr(sys, "_MEIPASS", ""), "core_bin", "ox_dsp_accel.dll"),
        os.path.join(getattr(sys, "_MEIPASS", ""), "ox_dsp_accel.dll")
    ]

    for path in candidates:
        if path and os.path.exists(path):
            try:
                lib = ctypes.CDLL(path)
                
                # int compute_fft_bands(const float*, int, float*, int)
                lib.compute_fft_bands.argtypes = [
                    ctypes.POINTER(ctypes.c_float),
                    ctypes.c_int,
                    ctypes.POINTER(ctypes.c_float),
                    ctypes.c_int
                ]
                lib.compute_fft_bands.restype = ctypes.c_int

                # float calculate_audio_levels(const float*, int, float*)
                lib.calculate_audio_levels.argtypes = [
                    ctypes.POINTER(ctypes.c_float),
                    ctypes.c_int,
                    ctypes.POINTER(ctypes.c_float)
                ]
                lib.calculate_audio_levels.restype = ctypes.c_float

                # int apply_equalizer_10band(float*, int, const float*, int)
                lib.apply_equalizer_10band.argtypes = [
                    ctypes.POINTER(ctypes.c_float),
                    ctypes.c_int,
                    ctypes.POINTER(ctypes.c_float),
                    ctypes.c_int
                ]
                lib.apply_equalizer_10band.restype = ctypes.c_int

                # int apply_soft_limiter(float*, int, float, float)
                lib.apply_soft_limiter.argtypes = [
                    ctypes.POINTER(ctypes.c_float),
                    ctypes.c_int,
                    ctypes.c_float,
                    ctypes.c_float
                ]
                lib.apply_soft_limiter.restype = ctypes.c_int

                _dll = lib
                return _dll
            except Exception:
                pass
    return None

def compute_fft_bands(samples, num_bands=32):
    """
    Computes magnitude frequency bands (0.0 to 1.0) from audio float samples.
    """
    if not samples:
        return [0.0] * num_bands

    dll = _load_dsp_dll()
    if dll:
        n = len(samples)
        in_arr = (ctypes.c_float * n)(*samples)
        out_arr = (ctypes.c_float * num_bands)()
        ret = dll.compute_fft_bands(in_arr, n, out_arr, num_bands)
        if ret == 0:
            return list(out_arr)

    # Pure Python fallback
    bands = [0.0] * num_bands
    chunk = len(samples) // num_bands
    if chunk <= 0:
        chunk = 1
    for i in range(num_bands):
        sl = samples[i * chunk : (i + 1) * chunk]
        if sl:
            avg = sum(abs(x) for x in sl) / len(sl)
            bands[i] = min(1.0, avg * 2.0)
    return bands

def calculate_audio_levels(samples):
    """
    Returns (rms_level, peak_level) both between 0.0 and 1.0.
    """
    if not samples:
        return 0.0, 0.0

    dll = _load_dsp_dll()
    if dll:
        n = len(samples)
        in_arr = (ctypes.c_float * n)(*samples)
        peak_val = ctypes.c_float(0.0)
        rms = dll.calculate_audio_levels(in_arr, n, ctypes.byref(peak_val))
        return float(rms), float(peak_val.value)

    # Fallback
    peak = max(abs(x) for x in samples)
    rms = math.sqrt(sum(x * x for x in samples) / len(samples))
    return min(1.0, rms), min(1.0, peak)

def apply_equalizer_10band(samples, gains_db, sample_rate=44100):
    """
    Applies 10-band equalizer to audio samples.
    gains_db is a list/tuple of 10 float values in dB (-12.0 to +12.0).
    """
    if not samples or len(gains_db) != 10:
        return samples

    dll = _load_dsp_dll()
    if dll:
        n = len(samples)
        in_out_arr = (ctypes.c_float * n)(*samples)
        gains_arr = (ctypes.c_float * 10)(*gains_db)
        ret = dll.apply_equalizer_10band(in_out_arr, n, gains_arr, sample_rate)
        if ret == 0:
            return list(in_out_arr)

    return samples

def apply_soft_limiter(samples, threshold=0.8, ceiling=0.99):
    """
    Applies soft clipping limiter to prevent audio harshness.
    """
    if not samples:
        return samples

    dll = _load_dsp_dll()
    if dll:
        n = len(samples)
        in_out_arr = (ctypes.c_float * n)(*samples)
        ret = dll.apply_soft_limiter(in_out_arr, n, ctypes.c_float(threshold), ctypes.c_float(ceiling))
        if ret == 0:
            return list(in_out_arr)

    return samples
