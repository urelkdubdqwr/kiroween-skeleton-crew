"""
apps/drainwatch/run.py – Flag abnormal on-chain outflows from a JSON event log.

Reads all JSON transfer logs from data_dir, computes per-vault statistics
(mean, stddev), and flags transfers that exceed a configurable sigma threshold
or a hard ETH ceiling.  Prints a JSON summary card to stdout.

Run directly:   python apps/drainwatch/run.py
Or via job:     python -m skeleton_crew run --job drainwatch
"""

from __future__ import annotations

import json
import math
import sys
import tomllib
from pathlib import Path

# ── config ────────────────────────────────────────────────────────────────────

_HERE = Path(__file__).parent
_DEFAULT_CONFIG = _HERE / "config.toml"
_DEFAULT_DATA   = _HERE / "data"


def load_config(config_path: Path = _DEFAULT_CONFIG) -> dict:
    if not config_path.exists():
        return {
            "data_dir":           str(_DEFAULT_DATA),
            "hard_threshold_eth": 50.0,
            "sigma_multiplier":   2.5,
            "alert_levels":       {"critical": 100.0, "high": 50.0, "medium": 20.0},
        }
    with open(config_path, "rb") as fh:
        return tomllib.load(fh)


# ── statistics helpers ────────────────────────────────────────────────────────

def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mu = _mean(values)
    variance = sum((v - mu) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def _alert_level(amount: float, levels: dict) -> str:
    if amount >= levels.get("critical", 100.0):
        return "CRITICAL"
    if amount >= levels.get("high", 50.0):
        return "HIGH"
    if amount >= levels.get("medium", 20.0):
        return "MEDIUM"
    return "LOW"


# ── data loading ──────────────────────────────────────────────────────────────

def load_transfers(data_dir: Path) -> list[dict]:
    """Load all JSON transfer log files from data_dir."""
    transfers: list[dict] = []
    for path in sorted(data_dir.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                transfers.extend(raw)
            elif isinstance(raw, dict):
                transfers.append(raw)
        except (json.JSONDecodeError, OSError) as exc:
            sys.stderr.write(f"[warn] could not load {path}: {exc}\n")
    return transfers


# ── anomaly detection ─────────────────────────────────────────────────────────

def detect_anomalies(
    transfers: list[dict],
    hard_threshold: float,
    sigma_mult: float,
    alert_levels: dict,
) -> dict:
    """Return a dict describing anomalous transfers."""
    if not transfers:
        return {"status": "ok", "total": 0, "anomalies": [], "summary": "no transfers"}

    amounts = [float(t.get("amount_eth", 0)) for t in transfers]
    mu      = _mean(amounts)
    sigma   = _stddev(amounts)
    cutoff  = mu + sigma_mult * sigma

    anomalies: list[dict] = []
    for tx in transfers:
        amount = float(tx.get("amount_eth", 0))
        if amount >= hard_threshold or amount > cutoff:
            level = _alert_level(amount, alert_levels)
            anomalies.append({
                "tx_hash":    tx.get("tx_hash", "?"),
                "from":       tx.get("from", "?"),
                "to":         tx.get("to", "?"),
                "amount_eth": amount,
                "ts":         tx.get("ts", "?"),
                "alert":      level,
                "reason":     (
                    f"{amount:.1f} ETH > hard threshold {hard_threshold} ETH"
                    if amount >= hard_threshold
                    else f"{amount:.1f} ETH > μ+{sigma_mult}σ ({cutoff:.2f} ETH)"
                ),
            })

    anomalies.sort(key=lambda a: a["amount_eth"], reverse=True)

    overall_level = "OK"
    if anomalies:
        # highest alert level across all anomalies
        priority = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "OK": 0}
        overall_level = max(anomalies, key=lambda a: priority.get(a["alert"], 0))["alert"]

    return {
        "status":        "error" if anomalies else "ok",
        "total":         len(transfers),
        "anomaly_count": len(anomalies),
        "mean_eth":      round(mu, 3),
        "stddev_eth":    round(sigma, 3),
        "cutoff_eth":    round(cutoff, 3),
        "alert_level":   overall_level,
        "largest":       (
            f"{anomalies[0]['from']} → {anomalies[0]['to']}  "
            f"{anomalies[0]['amount_eth']:.1f} ETH"
            if anomalies else None
        ),
        "anomalies":     anomalies,
    }


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    cfg = load_config()

    raw_dir = cfg.get("data_dir", str(_DEFAULT_DATA))
    data_dir = Path(raw_dir)
    if not data_dir.is_absolute():
        cwd_rel = Path(raw_dir)
        if cwd_rel.exists():
            data_dir = cwd_rel
        else:
            data_dir = _DEFAULT_DATA

    if not data_dir.is_dir():
        print(json.dumps({"status": "error", "error": f"data_dir not found: {data_dir}"}))
        return 1

    hard_threshold = float(cfg.get("hard_threshold_eth", 50.0))
    sigma_mult     = float(cfg.get("sigma_multiplier", 2.5))
    alert_levels   = cfg.get("alert_levels", {})

    transfers = load_transfers(data_dir)
    result    = detect_anomalies(transfers, hard_threshold, sigma_mult, alert_levels)
    result["event_log"] = str(data_dir)

    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
