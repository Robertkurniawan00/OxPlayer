"""
OXPlayer Multi-Language Architecture Verification Suite
Verifies C, C++, C#, and Rust modules and their Python bindings.
"""

import os
import sys
import subprocess
import unittest

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

class TestMultiLanguageModules(unittest.TestCase):

    def test_01_c_launcher(self):
        """Verifies Point 4: C Win32 Native Launcher binary"""
        launcher_exe = os.path.join(PROJECT_DIR, "core_bin", "OXPlayerLauncher.exe")
        self.assertTrue(os.path.isfile(launcher_exe), "OXPlayerLauncher.exe not found in core_bin")
        size = os.path.getsize(launcher_exe)
        self.assertGreater(size, 10000, "Launcher executable size is too small")
        # Verify PE header
        with open(launcher_exe, "rb") as f:
            magic = f.read(2)
            self.assertEqual(magic, b"MZ", "Not a valid Windows PE binary")

    def test_02_cpp_dsp_accelerator(self):
        """Verifies Point 1: C++ Audio DSP & FFT Accelerator DLL"""
        dsp_dll = os.path.join(PROJECT_DIR, "core_bin", "ox_dsp_accel.dll")
        self.assertTrue(os.path.isfile(dsp_dll), "ox_dsp_accel.dll not found in core_bin")

        import src.dsp_accel as dsp

        # 1. Test FFT Bands
        samples = [0.05 * ((i % 16) - 8) for i in range(1024)]
        bands = dsp.compute_fft_bands(samples, 32)
        self.assertEqual(len(bands), 32)
        for val in bands:
            self.assertTrue(0.0 <= val <= 1.0)

        # 2. Test Audio RMS and Peak
        rms, peak = dsp.calculate_audio_levels(samples)
        self.assertGreater(rms, 0.0)
        self.assertGreater(peak, 0.0)
        self.assertLessEqual(peak, 1.0)

        # 3. Test 10-Band Equalizer
        eq_gains = [2.0, 1.5, 0.0, -1.0, -2.0, 0.0, 1.0, 2.0, 3.0, 1.0]
        out_samples = dsp.apply_equalizer_10band(samples, eq_gains)
        self.assertEqual(len(out_samples), len(samples))

        # 4. Test Soft Limiter
        hot_samples = [1.5, -2.0, 0.5, 0.9, -1.2]
        limited = dsp.apply_soft_limiter(hot_samples, threshold=0.8, ceiling=0.99)
        self.assertEqual(len(limited), len(hot_samples))
        for s in limited:
            self.assertLessEqual(abs(s), 0.99 + 1e-4)

    def test_03_csharp_cli(self):
        """Verifies Point 2: C# (.NET) Media CLI Utility"""
        cli_exe = os.path.join(PROJECT_DIR, "core_bin", "OXMediaCLI.exe")
        self.assertTrue(os.path.isfile(cli_exe), "OXMediaCLI.exe not found in core_bin")

        # Test CLI help
        res = subprocess.run([cli_exe, "--help"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0)
        self.assertIn("OXMediaCLI", res.stdout)
        self.assertIn("Commands:", res.stdout)

        # Test CLI scan
        res_scan = subprocess.run([cli_exe, "scan", os.path.join(PROJECT_DIR, "assets")], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res_scan.returncode, 0)
        self.assertIn("Scanning directory", res_scan.stdout)

    def test_04_rust_sub_indexer(self):
        """Verifies Point 3: Rust Subtitle Parser & Playlist Indexer DLL"""
        rust_dll = os.path.join(PROJECT_DIR, "core_bin", "ox_sub_indexer.dll")
        self.assertTrue(os.path.isfile(rust_dll), "ox_sub_indexer.dll not found in core_bin")

        import src.sub_indexer as idx

        srt_data = """1
00:00:01,000 --> 00:00:04,500
Opening Scene: The Journey Begins.

2
00:00:05,000 --> 00:00:09,200
Dialogue: Fast Rust subtitle parser in action!

3
00:00:10,000 --> 00:00:15,000
Closing Credits.
"""
        # Test Cue Count
        count = idx.parse_srt_count(srt_data)
        self.assertEqual(count, 3)

        # Test Cue Lookup at timestamp
        text_2s = idx.find_subtitle_at(srt_data, 2000)
        self.assertIn("Opening Scene", text_2s)

        text_7s = idx.find_subtitle_at(srt_data, 7000)
        self.assertIn("Fast Rust subtitle parser", text_7s)

        text_none = idx.find_subtitle_at(srt_data, 4800)
        self.assertEqual(text_none, "")

        # Test Fuzzy Search
        candidates = [
            "Inception (2010) [1080p].mkv",
            "Interstellar (2014) [4K HDR].mp4",
            "The Dark Knight (2008).avi",
            "Avengers Endgame.mkv"
        ]
        results = idx.fuzzy_search_media("inter", candidates)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["index"], 1)

        # Test Format Time
        formatted = idx.format_time_ms(3665123)
        self.assertEqual(formatted, "01:01:05.123")

if __name__ == "__main__":
    unittest.main()
