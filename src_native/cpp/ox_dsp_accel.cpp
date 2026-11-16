#include "ox_dsp_accel.h"
#include <cmath>
#include <vector>
#include <complex>
#include <algorithm>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

// Fast in-place Radix-2 Cooley-Tukey FFT
static void fft_radix2(std::vector<std::complex<float>>& a) {
    size_t n = a.size();
    if (n <= 1) return;

    // Bit reversal permutation
    for (size_t i = 1, j = 0; i < n; i++) {
        size_t bit = n >> 1;
        for (; j & bit; bit >>= 1) {
            j ^= bit;
        }
        j ^= bit;
        if (i < j) {
            std::swap(a[i], a[j]);
        }
    }

    // Butterfly computations
    for (size_t len = 2; len <= n; len <<= 1) {
        float angle = -2.0f * (float)M_PI / (float)len;
        std::complex<float> wlen(std::cos(angle), std::sin(angle));
        for (size_t i = 0; i < n; i += len) {
            std::complex<float> w(1.0f, 0.0f);
            for (size_t j = 0; j < len / 2; j++) {
                std::complex<float> u = a[i + j];
                std::complex<float> v = a[i + j + len / 2] * w;
                a[i + j] = u + v;
                a[i + j + len / 2] = u - v;
                w *= wlen;
            }
        }
    }
}

extern "C" {

OX_DSP_EXPORT int compute_fft_bands(
    const float* input_samples,
    int sample_count,
    float* out_bands,
    int num_bands
) {
    if (!input_samples || !out_bands || sample_count < 16 || num_bands <= 0) {
        return -1;
    }

    // Ensure power of 2
    int n = 1;
    while (n * 2 <= sample_count) {
        n *= 2;
    }
    if (n > 4096) n = 4096;

    std::vector<std::complex<float>> buffer(n);
    // Apply Hanning Window to reduce spectral leakage
    for (int i = 0; i < n; i++) {
        float window = 0.5f * (1.0f - std::cos(2.0f * (float)M_PI * i / (n - 1)));
        buffer[i] = std::complex<float>(input_samples[i] * window, 0.0f);
    }

    // Execute FFT
    fft_radix2(buffer);

    // Compute magnitudes for positive frequencies (0 to n/2)
    int half_n = n / 2;
    std::vector<float> magnitudes(half_n);
    for (int i = 0; i < half_n; i++) {
        magnitudes[i] = std::abs(buffer[i]) / (float)n;
    }

    // Map magnitudes onto logarithmic frequency bands
    for (int b = 0; b < num_bands; b++) {
        // Logarithmic distribution across frequencies
        float start_ratio = std::pow((float)b / (float)num_bands, 2.0f);
        float end_ratio = std::pow((float)(b + 1) / (float)num_bands, 2.0f);

        int start_idx = (int)(start_ratio * half_n);
        int end_idx = (int)(end_ratio * half_n);
        if (end_idx <= start_idx) end_idx = start_idx + 1;
        if (end_idx > half_n) end_idx = half_n;

        float sum = 0.0f;
        int count = 0;
        for (int i = start_idx; i < end_idx; i++) {
            sum += magnitudes[i];
            count++;
        }
        float avg = (count > 0) ? (sum / count) : 0.0f;

        // Scale and clamp magnitude between 0.0 and 1.0
        float db = 20.0f * std::log10(avg + 1e-6f); // roughly -120 dB to 0 dB
        float normalized = (db + 60.0f) / 60.0f;     // Map -60dB..0dB to 0..1
        if (normalized < 0.0f) normalized = 0.0f;
        if (normalized > 1.0f) normalized = 1.0f;

        out_bands[b] = normalized;
    }

    return 0;
}

OX_DSP_EXPORT float calculate_audio_levels(
    const float* samples,
    int sample_count,
    float* out_peak
) {
    if (!samples || sample_count <= 0) {
        if (out_peak) *out_peak = 0.0f;
        return 0.0f;
    }

    float sum_sq = 0.0f;
    float peak = 0.0f;

    for (int i = 0; i < sample_count; i++) {
        float val = std::abs(samples[i]);
        if (val > peak) peak = val;
        sum_sq += val * val;
    }

    if (out_peak) {
        *out_peak = (peak > 1.0f) ? 1.0f : peak;
    }

    float rms = std::sqrt(sum_sq / (float)sample_count);
    return (rms > 1.0f) ? 1.0f : rms;
}

// Biquad peaking filter coefficient calculation
struct BiquadCoeffs {
    float b0, b1, b2, a1, a2;
};

static BiquadCoeffs calc_peaking_eq(float center_freq, float gain_db, float q, float sample_rate) {
    BiquadCoeffs c;
    float A = std::pow(10.0f, gain_db / 40.0f);
    float w0 = 2.0f * (float)M_PI * center_freq / sample_rate;
    float alpha = std::sin(w0) / (2.0f * q);

    float a0 = 1.0f + alpha / A;
    c.b0 = (1.0f + alpha * A) / a0;
    c.b1 = (-2.0f * std::cos(w0)) / a0;
    c.b2 = (1.0f - alpha * A) / a0;
    c.a1 = (-2.0f * std::cos(w0)) / a0;
    c.a2 = (1.0f - alpha / A) / a0;
    return c;
}

OX_DSP_EXPORT int apply_equalizer_10band(
    float* in_out_samples,
    int sample_count,
    const float* gains_db,
    int sample_rate
) {
    if (!in_out_samples || !gains_db || sample_count <= 0 || sample_rate <= 0) {
        return -1;
    }

    // Standard 10-Band EQ Frequencies (Hz)
    static const float center_freqs[10] = {
        31.0f, 62.0f, 125.0f, 250.0f, 500.0f, 1000.0f, 2000.0f, 4000.0f, 8000.0f, 16000.0f
    };

    for (int b = 0; b < 10; b++) {
        float gain = gains_db[b];
        if (std::abs(gain) < 0.1f) continue; // Skip neutral bands

        BiquadCoeffs c = calc_peaking_eq(center_freqs[b], gain, 1.414f, (float)sample_rate);
        float x1 = 0.0f, x2 = 0.0f, y1 = 0.0f, y2 = 0.0f;

        for (int i = 0; i < sample_count; i++) {
            float x0 = in_out_samples[i];
            float y0 = c.b0 * x0 + c.b1 * x1 + c.b2 * x2 - c.a1 * y1 - c.a2 * y2;
            x2 = x1;
            x1 = x0;
            y2 = y1;
            y1 = y0;
            in_out_samples[i] = y0;
        }
    }

    return 0;
}

OX_DSP_EXPORT int apply_soft_limiter(
    float* in_out_samples,
    int sample_count,
    float threshold,
    float ceiling
) {
    if (!in_out_samples || sample_count <= 0) return -1;
    if (threshold <= 0.0f) threshold = 0.8f;
    if (ceiling <= 0.0f) ceiling = 0.99f;

    for (int i = 0; i < sample_count; i++) {
        float x = in_out_samples[i];
        float sign = (x < 0.0f) ? -1.0f : 1.0f;
        float abs_x = std::abs(x);

        if (abs_x > threshold) {
            // Soft cubic compression above threshold
            float excess = abs_x - threshold;
            float headroom = 1.0f - threshold;
            float compressed = threshold + headroom * std::tanh(excess / headroom);
            in_out_samples[i] = sign * std::min(compressed, ceiling);
        }
    }

    return 0;
}

} // extern "C"
