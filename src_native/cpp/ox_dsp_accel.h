#pragma once

#ifdef _WIN32
    #define OX_DSP_EXPORT __declspec(dllexport)
#else
    #define OX_DSP_EXPORT __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

// Fast FFT & Band Magnitude Extractor for Spectrum Visualizers
// input_samples: array of float samples (must be power of 2 length, e.g. 512, 1024, 2048)
// sample_count: size of input_samples
// out_bands: array of size num_bands to receive 0.0 - 1.0 magnitude values
// num_bands: number of visualizer bars (e.g. 16, 32, 64)
OX_DSP_EXPORT int compute_fft_bands(
    const float* input_samples,
    int sample_count,
    float* out_bands,
    int num_bands
);

// Fast RMS (Root Mean Square) and Peak Amplitude calculation
// Returns RMS level (0.0 to 1.0) and writes peak value to out_peak
OX_DSP_EXPORT float calculate_audio_levels(
    const float* samples,
    int sample_count,
    float* out_peak
);

// Fast Biquad 10-band Equalizer filter
// gains_db: array of 10 float values in dB (-12.0 to +12.0)
// sample_rate: e.g. 44100 or 48000
OX_DSP_EXPORT int apply_equalizer_10band(
    float* in_out_samples,
    int sample_count,
    const float* gains_db,
    int sample_rate
);

// Fast in-place Soft Limiter / Normalizer to prevent clipping distortion
OX_DSP_EXPORT int apply_soft_limiter(
    float* in_out_samples,
    int sample_count,
    float threshold,
    float ceiling
);

#ifdef __cplusplus
}
#endif
