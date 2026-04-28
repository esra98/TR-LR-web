"""
Recompute WER values in result.txt with Turkish case-sensitive comparison
(no case folding, preserves I / ı / İ / i as distinct characters).

Writes result_improved.txt (does NOT modify result.txt) and data.json
(an index of all videos for the web UI).
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "result.txt"
DST = ROOT / "result_improved.txt"
DATA = ROOT / "data.json"


def levenshtein(ref, hyp):
    n, m = len(ref), len(hyp)
    if n == 0:
        return m
    if m == 0:
        return n
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        cur = [i] + [0] * m
        for j in range(1, m + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[m]


def wer(real: str, forecast: str) -> float:
    # Turkish case-sensitive: do NOT lowercase. Preserve I, ı, İ, i as-is.
    ref = real.split()
    hyp = forecast.split()
    if not ref:
        return 0.0 if not hyp else 100.0
    return levenshtein(ref, hyp) / len(ref) * 100.0


def main():
    text = SRC.read_text(encoding="utf-8")
    lines = text.splitlines()
    out = []
    entries = []

    i = 0
    total = 0.0
    count = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^Video (\d+) \((\d+)\)\s*$", line)
        if not m:
            out.append(line)
            i += 1
            continue

        vid_num = int(m.group(1))
        vid_id = m.group(2)
        forecast = ""
        real = ""
        forecast_line_idx = real_line_idx = wer_line_idx = -1

        block_lines = [line]
        j = i + 1
        # consume block until blank line or next Video header or EOF
        while j < len(lines) and lines[j].strip() != "" and not re.match(
            r"^Video \d+ \(\d+\)\s*$", lines[j]
        ):
            block_lines.append(lines[j])
            if lines[j].lstrip().startswith("Forecast:"):
                forecast = lines[j].split("Forecast:", 1)[1].strip()
                forecast_line_idx = len(block_lines) - 1
            elif lines[j].lstrip().startswith("Real:"):
                real = lines[j].split("Real:", 1)[1].strip()
                real_line_idx = len(block_lines) - 1
            elif lines[j].lstrip().startswith("WER:"):
                wer_line_idx = len(block_lines) - 1
            j += 1

        new_wer = wer(real, forecast)
        total += new_wer
        count += 1

        if wer_line_idx >= 0:
            block_lines[wer_line_idx] = f"  WER:      {new_wer:.1f}%"
        else:
            block_lines.append(f"  WER:      {new_wer:.1f}%")

        out.extend(block_lines)
        entries.append({
            "n": vid_num,
            "id": vid_id,
            "real": real,
            "forecast": forecast,
            "wer": round(new_wer, 2),
        })

        i = j

    # rewrite the average WER summary if present
    avg = total / count if count else 0.0
    final = []
    avg_pat = re.compile(r"Average WER \(\d+ videos\):")
    for ln in out:
        if avg_pat.search(ln):
            final.append(f"Average WER ({count} videos): {avg:.2f}%")
        else:
            final.append(ln)

    DST.write_text("\n".join(final) + "\n", encoding="utf-8")
    payload = {"avg_wer": round(avg, 2), "items": entries}
    DATA.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    # Also emit a JS wrapper so the page works from file:// (GitHub Pages too).
    (ROOT / "data.js").write_text(
        "window.DATA = " + json.dumps(payload, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {DST.name}: {count} videos, avg WER (TR case-sensitive) = {avg:.2f}%")
    print(f"Wrote {DATA.name} + data.js: {len(entries)} entries")


if __name__ == "__main__":
    main()
