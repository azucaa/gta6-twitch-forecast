"""Forecast GTA VI launch-day Twitch viewers, hours 2-24, from hour 1.

Model: learn the launch-day shape from the case's own comparables.
For every past big launch in ``comparables`` we take its release-day
hourly curve (the UTC day starting at its ``day_start``), compute the
ratio of each hour's viewers to that launch's hour-1 viewers, and pool
those ratios hour by hour.  The forecast for an hour is hour 1's print
times the empirical quantiles of the pooled ratios at the five scored
levels, shrunk toward the house persistence baseline where the pooled
sample is thin.  The GTA VI category's own pre-release history (its
"day" is a trailer premiere, not a launch) is excluded from the pool.

Fallback: with no usable comparables the program emits exactly the
house baseline shape, q_tau = p * exp(z_tau * 0.15 * sqrt(h - 1)).

Standard library only, no network, fully deterministic.
Reads $MAKEFUN_INPUT_DIR else /input, writes $MAKEFUN_OUTPUT_DIR
else /output, one <id>.out per *.in file found, in name order.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]
BASE_SIGMA = 0.15
# Shrinkage: empirical log-quantiles get weight n / (n + SHRINK_K);
# the rest comes from the baseline log-quantiles around ratio 1.
SHRINK_K = 6.0


def parse_ts(text):
    """Parse an ISO-8601 UTC timestamp to epoch seconds, or None."""
    if not isinstance(text, str):
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def quantile(sorted_vals, tau):
    """Empirical quantile with linear interpolation (numpy 'linear')."""
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    pos = tau * (n - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def round2(x):
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if float(value).is_integer() else value


def baseline_row(p1, h):
    spread = BASE_SIGMA * math.sqrt(h - 1)
    return [p1 * math.exp(z * spread) for z in Z]


def comparable_log_ratios(case):
    """Pool log(viewers_h / viewers_hour1) per hour 2..24 over comparables."""
    pooled = {h: [] for h in range(2, 25)}
    for comp in case.get("comparables") or []:
        name = str(comp.get("name") or "").lower()
        if "before release" in name:
            continue  # GTA VI pre-release history: premiere day, not a launch
        day0 = parse_ts(comp.get("day_start"))
        if day0 is None:
            continue
        by_hour = {}
        for row in comp.get("hourly") or []:
            ts = parse_ts(row.get("from"))
            viewers = row.get("viewers")
            if ts is None or not isinstance(viewers, (int, float)):
                continue
            offset = int(round((ts - day0) / 3600.0))
            if 0 <= offset < 24 and viewers > 0:
                by_hour[offset] = float(viewers)
        first = by_hour.get(0)
        if not first or first <= 0:
            continue
        # Drop launches that had not really unlocked by hour 1 UTC:
        # a simultaneous global unlock later in the day makes hour 1 a
        # pre-launch trickle (peak more than 20x hour 1), and that shape
        # cannot inform a rolling midnight-local console launch, whose
        # first hour is already live across most of the world.  Held-out
        # validation on GTA-like launches: mean log pinball 0.318 with
        # this filter vs 0.362 without (baseline 0.373).
        if by_hour and max(by_hour.values()) / first > 20.0:
            continue
        for h in range(2, 25):
            v = by_hour.get(h - 1)
            if v and v > 0:
                pooled[h].append(math.log(v / first))
    for h in pooled:
        pooled[h].sort()
    return pooled


def forecast_case(case):
    known = case.get("known") or []
    first = next((k for k in known if k.get("hour") == 1), None)
    p1 = 1.0
    if first is not None:
        try:
            p1 = float(first.get("viewers") or 0)
        except (TypeError, ValueError):
            p1 = 1.0
    if not math.isfinite(p1) or p1 < 1:
        p1 = 1.0

    pooled = comparable_log_ratios(case)
    hours_out = []
    for h in range(2, 25):
        base = baseline_row(p1, h)
        logs = pooled.get(h) or []
        if len(logs) >= 4:
            w = len(logs) / (len(logs) + SHRINK_K)
            qs = []
            for i, tau in enumerate(LEVELS):
                emp_log = quantile(logs, tau)
                base_log = math.log(base[i] / p1)
                log_q = w * emp_log + (1.0 - w) * base_log
                qs.append(p1 * math.exp(log_q))
        else:
            qs = list(base)
        # Clamp, enforce non-decreasing, round like the baseline.
        qs = [min(1e9, max(1e-6, q)) for q in qs]
        qs.sort()
        hours_out.append({"hour": h, "q": [round2(q) for q in qs]})
    return {"hours": hours_out}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not INPUT_DIR.is_dir():
        return
    for path in sorted(INPUT_DIR.glob("*.in")):
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
            result = forecast_case(case)
        except Exception:
            # Never crash a case: fall back to a minimal valid-shaped case.
            try:
                case = json.loads(path.read_text(encoding="utf-8"))
                result = forecast_case({"known": case.get("known") or [],
                                         "comparables": []})
            except Exception:
                result = {"hours": [{"hour": h, "q": [1, 1, 1, 1, 1]}
                                    for h in range(2, 25)]}
        text = json.dumps(result, separators=(",", ":")) + "\n"
        (OUTPUT_DIR / f"{path.stem}.out").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
