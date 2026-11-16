use std::ffi::CStr;
use std::os::raw::{c_char, c_int};

#[derive(Debug, Clone)]
struct SubtitleCue {
    start_ms: i64,
    end_ms: i64,
    text: String,
}

fn parse_timestamp(s: &str) -> Option<i64> {
    let s = s.trim().replace(',', ".");
    let parts: Vec<&str> = s.split(':').collect();
    if parts.len() == 3 {
        let hours: i64 = parts[0].trim().parse().ok()?;
        let minutes: i64 = parts[1].trim().parse().ok()?;
        let sec_parts: Vec<&str> = parts[2].split('.').collect();
        let seconds: i64 = sec_parts[0].trim().parse().ok()?;
        let millis: i64 = if sec_parts.len() > 1 {
            let mut ms_str = sec_parts[1].trim().to_string();
            while ms_str.len() < 3 { ms_str.push('0'); }
            ms_str.truncate(3);
            ms_str.parse().unwrap_or(0)
        } else {
            0
        };
        Some(hours * 3_600_000 + minutes * 60_000 + seconds * 1_000 + millis)
    } else if parts.len() == 2 {
        let minutes: i64 = parts[0].trim().parse().ok()?;
        let sec_parts: Vec<&str> = parts[1].split('.').collect();
        let seconds: i64 = sec_parts[0].trim().parse().ok()?;
        let millis: i64 = if sec_parts.len() > 1 {
            let mut ms_str = sec_parts[1].trim().to_string();
            while ms_str.len() < 3 { ms_str.push('0'); }
            ms_str.truncate(3);
            ms_str.parse().unwrap_or(0)
        } else {
            0
        };
        Some(minutes * 60_000 + seconds * 1_000 + millis)
    } else {
        None
    }
}

fn parse_srt(content: &str) -> Vec<SubtitleCue> {
    let mut cues = Vec::new();
    let normalized = content.replace("\r\n", "\n").replace('\r', "\n");
    let blocks: Vec<&str> = normalized.split("\n\n").collect();

    for block in blocks {
        let lines: Vec<&str> = block.lines().map(|l| l.trim()).filter(|l| !l.is_empty()).collect();
        if lines.len() < 2 {
            continue;
        }

        // Line 0 is cue index or time; find the line with "-->"
        let mut time_idx = None;
        for (i, line) in lines.iter().enumerate() {
            if line.contains("-->") {
                time_idx = Some(i);
                break;
            }
        }

        if let Some(ti) = time_idx {
            let arrow_parts: Vec<&str> = lines[ti].split("-->").collect();
            if arrow_parts.len() == 2 {
                if let (Some(start), Some(end)) = (parse_timestamp(arrow_parts[0]), parse_timestamp(arrow_parts[1])) {
                    let text = lines[ti + 1..].join("\n");
                    cues.push(SubtitleCue {
                        start_ms: start,
                        end_ms: end,
                        text,
                    });
                }
            }
        }
    }

    cues.sort_by_key(|c| c.start_ms);
    cues
}

fn fuzzy_score(pattern: &str, text: &str) -> Option<i32> {
    let p_chars: Vec<char> = pattern.to_lowercase().chars().collect();
    let t_chars: Vec<char> = text.to_lowercase().chars().collect();

    if p_chars.is_empty() {
        return Some(0);
    }

    let mut p_idx = 0;
    let mut score = 0;
    let mut consecutive = 0;

    for (t_idx, &tc) in t_chars.iter().enumerate() {
        if tc == p_chars[p_idx] {
            score += 10;
            if consecutive > 0 {
                score += consecutive * 5;
            }
            if t_idx == 0 || !t_chars[t_idx - 1].is_alphanumeric() {
                score += 8; // Word boundary bonus
            }
            consecutive += 1;
            p_idx += 1;
            if p_idx == p_chars.len() {
                // Matched all
                return Some(score);
            }
        } else {
            consecutive = 0;
        }
    }

    None
}

// ----------------- C-ABI EXPORTS -----------------

#[no_mangle]
pub unsafe extern "C" fn ox_parse_srt_count(content_ptr: *const c_char) -> c_int {
    if content_ptr.is_null() {
        return 0;
    }
    let c_str = CStr::from_ptr(content_ptr);
    if let Ok(content) = c_str.to_str() {
        parse_srt(content).len() as c_int
    } else {
        0
    }
}

#[no_mangle]
pub unsafe extern "C" fn ox_find_subtitle(
    content_ptr: *const c_char,
    target_ms: i64,
    out_buf: *mut c_char,
    max_len: c_int,
) -> c_int {
    if content_ptr.is_null() || out_buf.is_null() || max_len <= 1 {
        return -1;
    }

    let c_str = CStr::from_ptr(content_ptr);
    let content = match c_str.to_str() {
        Ok(c) => c,
        Err(_) => return -1,
    };

    let cues = parse_srt(content);
    // Find matching cue: start_ms <= target_ms <= end_ms
    let matched = cues.iter().find(|c| c.start_ms <= target_ms && target_ms <= c.end_ms);

    if let Some(cue) = matched {
        let bytes = cue.text.as_bytes();
        let copy_len = std::cmp::min(bytes.len(), (max_len - 1) as usize);
        std::ptr::copy_nonoverlapping(bytes.as_ptr() as *const c_char, out_buf, copy_len);
        *out_buf.add(copy_len) = 0;
        copy_len as c_int
    } else {
        *out_buf = 0;
        0
    }
}

#[no_mangle]
pub unsafe extern "C" fn ox_fuzzy_search(
    query_ptr: *const c_char,
    candidates_nl_ptr: *const c_char,
    out_buf: *mut c_char,
    max_len: c_int,
) -> c_int {
    if query_ptr.is_null() || candidates_nl_ptr.is_null() || out_buf.is_null() || max_len <= 1 {
        return -1;
    }

    let q_str = match CStr::from_ptr(query_ptr).to_str() {
        Ok(s) => s.trim(),
        Err(_) => return -1,
    };

    let c_str = match CStr::from_ptr(candidates_nl_ptr).to_str() {
        Ok(s) => s,
        Err(_) => return -1,
    };

    let mut matches = Vec::new();
    for (idx, line) in c_str.lines().enumerate() {
        let line = line.trim();
        if line.is_empty() { continue; }
        if let Some(score) = fuzzy_score(q_str, line) {
            matches.push((idx, score, line));
        }
    }

    matches.sort_by(|a, b| b.1.cmp(&a.1));

    // Serialize to JSON-like string: [{"idx":0,"score":50,"text":"..."},...]
    let mut json = String::from("[");
    for (i, (idx, score, text)) in matches.iter().take(50).enumerate() {
        if i > 0 { json.push(','); }
        json.push_str(&format!(
            "{{\"index\":{},\"score\":{},\"title\":\"{}\"}}",
            idx, score, text.replace('"', "\\\"")
        ));
    }
    json.push(']');

    let bytes = json.as_bytes();
    let copy_len = std::cmp::min(bytes.len(), (max_len - 1) as usize);
    std::ptr::copy_nonoverlapping(bytes.as_ptr() as *const c_char, out_buf, copy_len);
    *out_buf.add(copy_len) = 0;
    copy_len as c_int
}

#[no_mangle]
pub unsafe extern "C" fn ox_format_ms(
    ms: i64,
    out_buf: *mut c_char,
    max_len: c_int,
) -> c_int {
    if out_buf.is_null() || max_len < 12 {
        return -1;
    }

    let total_sec = ms / 1000;
    let millis = ms % 1000;
    let sec = total_sec % 60;
    let min = (total_sec / 60) % 60;
    let hour = total_sec / 3600;

    let formatted = if hour > 0 {
        format!("{:02}:{:02}:{:02}.{:03}", hour, min, sec, millis)
    } else {
        format!("{:02}:{:02}.{:03}", min, sec, millis)
    };

    let bytes = formatted.as_bytes();
    let copy_len = std::cmp::min(bytes.len(), (max_len - 1) as usize);
    std::ptr::copy_nonoverlapping(bytes.as_ptr() as *const c_char, out_buf, copy_len);
    *out_buf.add(copy_len) = 0;
    copy_len as c_int
}
