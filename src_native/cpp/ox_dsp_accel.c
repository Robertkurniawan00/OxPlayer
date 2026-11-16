#include "ox_dsp_accel.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

// Fast in-place Radix-2 Cooley-Tukey FFT in pure C
static void fft_radix2_c(float* real, float* imag, int n) {
    if (n <= 1) return;

    // Bit reversal permutation
    for (int i = 1, j = 0; i < n; i++) {
        int bit = n >> 1;
        for (; j & bit; bit >>= 1) {
            j ^= bit;
        }
        j ^= bit;
        if (i < j) {
            float temp_r = real[i];
            real[i] = real[j];
            real[j] = temp_r;

            float temp_i = imag[i];
            imag[i] = imag[j];
            imag[j] = temp_i;
        }
    }

    // Butterfly computations
    for (int len = 2; len <= n; len <<= 1) {
        float angle = -2.0f * (float)M_PI / (float)len;
        float wlen_r = cosf(angle);
        float wlen_i = sinf(angle);

        for (int i = 0; i < n; i += len) {
            float w_r = 1.0f;
            float w_i = 0.0f;
            for (int j = 0; j < len / 2; j++) {
                int u_idx = i + j;
                int v_idx = i + j + len / 2;

                float u_r = real[u_idx];
                float u_i = imag[u_idx];

                float v_r = real[v_idx] * w_r - imag[v_idx] * w_i;
                float v_i = real[v_idx] * w_i + imag[v_idx] * w_r;

                real[u_idx] = u_r + v_r;
                imag[u_idx] = u_i + v_i;

                real[v_idx] = u_r - v_r;
                imag[v_idx] = u_i - v_i;

                float next_w_r = w_r * wlen_r - w_i * wlen_i;
                float next_w_i = w_r * wlen_i + w_i * wlen_r;
                w_r = next_w_r;
                w_i = next_w_i;
            }
        }
    }
}

int compute_fft_bands(
    const float* input_samples,
    int sample_count,
    float* out_bands,
    int num_bands
) {
    if (!input_samples || !out_bands || sample_count < 16 || num_bands <= 0) {
        return -1;
    }

    int n = 1;
    while (n * 2 <= sample_count) {
        n *= 2;
    }
    if (n > 4096) n = 4096;

    float* real = (float*)malloc(n * sizeof(float));
    float* imag = (float*)calloc(n, sizeof(float));
    if (!real || !imag) {
        if (real) free(real);
        if (imag) free(imag);
        return -1;
    }

    // Apply Hanning Window to reduce spectral leakage
    for (int i = 0; i < n; i++) {
        float window = 0.5f * (1.0f - cosf(2.0f * (float)M_PI * (float)i / (float)(n - 1)));
        real[i] = input_samples[i] * window;
    }

    // Execute FFT
    fft_radix2_c(real, imag, n);

    // Compute magnitudes for positive frequencies (0 to n/2)
    int half_n = n / 2;
    float* magnitudes = (float*)malloc(half_n * sizeof(float));
    if (!magnitudes) {
        free(real);
        free(imag);
        return -1;
    }

    for (int i = 0; i < half_n; i++) {
        magnitudes[i] = sqrtf(real[i] * real[i] + imag[i] * imag[i]) / (float)n;
    }

    // Map magnitudes onto logarithmic frequency bands
    for (int b = 0; b < num_bands; b++) {
        float start_ratio = powf((float)b / (float)num_bands, 2.0f);
        float end_ratio = powf((float)(b + 1) / (float)num_bands, 2.0f);

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
        float avg = (count > 0) ? (sum / (float)count) : 0.0f;

        float db = 20.0f * log10f(avg + 1e-6f);
        float normalized = (db + 60.0f) / 60.0f;
        if (normalized < 0.0f) normalized = 0.0f;
        if (normalized > 1.0f) normalized = 1.0f;

        out_bands[b] = normalized;
    }

    free(real);
    free(imag);
    free(magnitudes);
    return 0;
}

float calculate_audio_levels(
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
        float val = fabsf(samples[i]);
        if (val > peak) peak = val;
        sum_sq += val * val;
    }

    if (out_peak) {
        *out_peak = (peak > 1.0f) ? 1.0f : peak;
    }

    float rms = sqrtf(sum_sq / (float)sample_count);
    return (rms > 1.0f) ? 1.0f : rms;
}

typedef struct {
    float b0, b1, b2, a1, a2;
} BiquadCoeffs;

static BiquadCoeffs calc_peaking_eq(float center_freq, float gain_db, float q, float sample_rate) {
    BiquadCoeffs c;
    float A = powf(10.0f, gain_db / 40.0f);
    float w0 = 2.0f * (float)M_PI * center_freq / sample_rate;
    float alpha = sinf(w0) / (2.0f * q);

    float a0 = 1.0f + alpha / A;
    c.b0 = (1.0f + alpha * A) / a0;
    c.b1 = (-2.0f * cosf(w0)) / a0;
    c.b2 = (1.0f - alpha * A) / a0;
    c.a1 = (-2.0f * cosf(w0)) / a0;
    c.a2 = (1.0f - alpha / A) / a0;
    return c;
}

int apply_equalizer_10band(
    float* in_out_samples,
    int sample_count,
    const float* gains_db,
    int sample_rate
) {
    if (!in_out_samples || !gains_db || sample_count <= 0 || sample_rate <= 0) {
        return -1;
    }

    static const float center_freqs[10] = {
        31.0f, 62.0f, 125.0f, 250.0f, 500.0f, 1000.0f, 2000.0f, 4000.0f, 8000.0f, 16000.0f
    };

    for (int b = 0; b < 10; b++) {
        float gain = gains_db[b];
        if (fabsf(gain) < 0.1f) continue;

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

int apply_soft_limiter(
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
        float abs_x = fabsf(x);

        if (abs_x > threshold) {
            float excess = abs_x - threshold;
            float headroom = 1.0f - threshold;
            float compressed = threshold + headroom * tanhf(excess / headroom);
            in_out_samples[i] = sign * ((compressed > ceiling) ? ceiling : compressed);
        }
    }

    return 0;
}
