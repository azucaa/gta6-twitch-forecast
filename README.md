# gta6-twitch-forecast

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/azucaa/gta6-twitch-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/azucaa/gta6-twitch-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

**Forecast GTA VI's launch-day Twitch viewers, hour by hour.** A Python program that reads everything recorded up to the end of hour 1 of release day (2026-11-19 UTC) — hour 1's viewer print included — and forecasts the Twitch concurrent viewers of the Grand Theft Auto VI category for each of hours 2–24 as five quantiles (5%, 25%, 50%, 75%, 95%), scored by mean pinball loss on the log scale.

## How it works

The program learns the launch-day shape from the case's own comparables at runtime:

- For every past big launch in the case's `comparables`, it takes that launch's release-day hourly curve (the UTC day starting at its `day_start`) and computes the ratio of each hour's viewers to that launch's hour-1 viewers.
- Launches that had not really unlocked by hour 1 UTC are dropped: a simultaneous global unlock later in the day leaves hour 1 as a pre-launch trickle (release-day peak more than 20× hour 1), a shape that cannot inform a rolling midnight-local console launch like GTA VI, whose first hour is already live across most of the world. The GTA VI category's own pre-release history (a trailer premiere day, not a launch) is excluded for the same reason.
- The pooled ratios give, per hour, empirical quantiles at the five scored levels, shrunk toward the house persistence baseline (`q = p · exp(z · 0.15 · sqrt(h−1))`) with weight `n/(n+6)`, so thin hours stay close to the baseline and rich hours follow the data.
- With no usable comparables it emits the pure baseline shape; with a missing or invalid hour-1 print it uses `p = 1`. Every row is clamped to (0, 1e9] and made non-decreasing, so a well-formed case always yields a valid forecast.

Held-out validation (each comparable launch in turn forecast from the others, scored against its real hours 2–24): on GTA-like launches — rolling midnight unlocks whose hour 1 is already substantial — the model scores a mean log pinball loss of **0.318** against the house baseline's **0.373** on the same launches (all 37 launches pooled: 0.836 vs 0.930, winning 31 of 37).

## Run it

```sh
mkdir -p out
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

This reads every `*.in` case file in the input directory (in name order) and writes one `<id>.out` per case: `{"hours": [{"hour": h, "q": [q05, q25, q50, q75, q95]} × 23]}` for hours 2–24. The entrypoint is standard-library only — no packages to install, no network — runs in about 0.1 s per case, and is byte-for-byte deterministic across runs.

## License

MIT — see [LICENSE](LICENSE).

---

<sub>Entered on [make.fun](https://make.fun/?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
