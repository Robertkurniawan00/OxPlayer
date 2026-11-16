"""
OXPlayer Rust Subtitle Parser & Playlist Indexer Module
Provides high-performance SRT parsing, binary cue lookup, and fuzzy search for playlist items.
"""

import os
import sys
import ctypes
import json

_dll = None

def _load_rust_dll():
    global _dll
    if _dll is not None:
        return _dll

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(base_dir, "core_bin", "ox_sub_indexer.dll"),
        os.path.join(base_dir, "ox_sub_indexer.dll"),
        os.path.join(getattr(sys, "_MEIPASS", ""), "core_bin", "ox_sub_indexer.dll"),
        os.path.join(getattr(sys, "_MEIPASS", ""), "ox_sub_indexer.dll")
    ]

    for path in candidates:
        if path and os.path.exists(path):
            try:
                lib = ctypes.CDLL(path)

                # int ox_parse_srt_count(const char*)
                lib.ox_parse_srt_count.argtypes = [ctypes.c_char_p]
                lib.ox_parse_srt_count.restype = ctypes.c_int

                # int ox_find_subtitle(const char*, int64_t, char*, int)
                lib.ox_find_subtitle.argtypes = [
                    ctypes.c_char_p,
                    ctypes.c_int64,
                    ctypes.c_char_p,
                    ctypes.c_int
                ]
                lib.ox_find_subtitle.restype = ctypes.c_int

                # int ox_fuzzy_search(const char*, const char*, char*, int)
                lib.ox_fuzzy_search.argtypes = [
                    ctypes.c_char_p,
                    ctypes.c_char_p,
                    ctypes.c_char_p,
                    ctypes.c_int
                ]
                lib.ox_fuzzy_search.restype = ctypes.c_int

                # int ox_format_ms(int64_t, char*, int)
                lib.ox_format_ms.argtypes = [
                    ctypes.c_int64,
                    ctypes.c_char_p,
                    ctypes.c_int
                ]
                lib.ox_format_ms.restype = ctypes.c_int

                _dll = lib
                return _dll
            except Exception:
                pass
    return None

def parse_srt_count(content: str) -> int:
    """Returns number of subtitle cues parsed from SRT text."""
    if not content:
        return 0
    dll = _load_rust_dll()
    if dll:
        b_content = content.encode("utf-8", errors="replace")
        return dll.ox_parse_srt_count(b_content)
    return content.count("-->")

def find_subtitle_at(content: str, timestamp_ms: int) -> str:
    """
    Finds subtitle text at timestamp in milliseconds.
    """
    if not content or timestamp_ms < 0:
        return ""
    dll = _load_rust_dll()
    if dll:
        b_content = content.encode("utf-8", errors="replace")
        buf = ctypes.create_string_buffer(4096)
        ret = dll.ox_find_subtitle(b_content, ctypes.c_int64(timestamp_ms), buf, 4096)
        if ret > 0:
            return buf.value.decode("utf-8", errors="replace")
        return ""

    # Simple fallback
    return ""

def fuzzy_search_media(query: str, candidates: list) -> list:
    """
    Ranks candidates using Rust fuzzy search.
    Returns list of dicts: [{"index": i, "score": s, "title": "..."}]
    """
    if not query or not candidates:
        return []

    dll = _load_rust_dll()
    if dll:
        b_query = query.encode("utf-8", errors="replace")
        b_candidates = "\n".join(candidates).encode("utf-8", errors="replace")
        buf_size = 65536
        buf = ctypes.create_string_buffer(buf_size)
        ret = dll.ox_fuzzy_search(b_query, b_candidates, buf, buf_size)
        if ret > 0:
            try:
                json_str = buf.value.decode("utf-8", errors="replace")
                return json.loads(json_str)
            except Exception:
                pass

    # Simple fallback
    q = query.lower()
    results = []
    for idx, c in enumerate(candidates):
        if q in c.lower():
            results.append({"index": idx, "score": 10, "title": c})
    return results

def format_time_ms(ms: int) -> str:
    """Formats millisecond integer to HH:MM:SS.mmm or MM:SS.mmm."""
    dll = _load_rust_dll()
    if dll:
        buf = ctypes.create_string_buffer(64)
        ret = dll.ox_format_ms(ctypes.c_int64(ms), buf, 64)
        if ret > 0:
            return buf.value.decode("utf-8", errors="replace")

    total_sec = ms // 1000
    sec = total_sec % 60
    min_ = (total_sec // 60) % 60
    hour = total_sec // 3600
    if hour > 0:
        return f"{hour:02d}:{min_:02d}:{sec:02d}"
    return f"{min_:02d}:{sec:02d}"
