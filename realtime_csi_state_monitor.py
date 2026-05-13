#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Real-time CSI state monitor.

It reads CSI_DATA lines from the receiver serial port, builds amplitude windows,
extracts the same features used during training, and prints predicted states.
"""

import argparse
import time
from collections import Counter, deque
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from build_csi_features import WINDOW_SIZE, STEP_SIZE, extract_window_features
from csi_receiver_collector import CSIReceiverCollector


DEFAULT_MODEL = Path("data/multi_group/models/csi_state_classifier.joblib")


def format_probs(labels, probs) -> str:
    return ", ".join(f"{label}:{prob:.2f}" for label, prob in zip(labels, probs))


def majority_vote(values: deque[str]) -> str:
    if not values:
        return ""
    return Counter(values).most_common(1)[0][0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Real-time CSI state monitor")
    parser.add_argument("--port", required=True, help="Receiver serial port, for example COM13")
    parser.add_argument("--baudrate", type=int, default=921600)
    parser.add_argument("--model", default=str(DEFAULT_MODEL), help="Saved model path")
    parser.add_argument("--duration", type=int, default=0, help="Run seconds, 0 means until Ctrl+C")
    parser.add_argument("--window", type=int, default=WINDOW_SIZE, help="Window packet count")
    parser.add_argument("--step", type=int, default=STEP_SIZE, help="Prediction step packet count")
    parser.add_argument("--smooth", type=int, default=5, help="Majority vote length")
    parser.add_argument("--min_confidence", type=float, default=0.60, help="Output unknown below this confidence")
    args = parser.parse_args()

    bundle = joblib.load(args.model)
    model = bundle["model"]
    feature_cols = bundle["feature_cols"]
    labels = list(model.classes_)

    collector = CSIReceiverCollector(port=args.port, baudrate=args.baudrate, timeout=1.0)
    if not collector.connect():
        raise SystemExit("Serial connection failed.")

    amp_buffer: deque[list[float]] = deque(maxlen=args.window)
    votes: deque[str] = deque(maxlen=args.smooth)
    valid_packets = 0
    next_predict_at = args.window
    start_time = time.time()

    print("CSI real-time monitor started.")
    print(f"port={args.port}, window={args.window}, step={args.step}, model={args.model}")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            if args.duration > 0 and time.time() - start_time >= args.duration:
                break

            raw = collector.serial_conn.readline()
            if not raw:
                continue

            try:
                line = raw.decode("utf-8", errors="ignore").strip()
            except UnicodeDecodeError:
                continue

            parsed = collector.parse_csi_line(line)
            if not parsed or not collector.validate_csi_data(parsed):
                continue

            amp = parsed.get("amplitude_array", [])
            if len(amp) != 192:
                continue

            amp_buffer.append(amp)
            valid_packets += 1

            if len(amp_buffer) < args.window or valid_packets < next_predict_at:
                continue

            window = np.asarray(amp_buffer, dtype=float)
            features = extract_window_features(window)
            x = pd.DataFrame([[features[col] for col in feature_cols]], columns=feature_cols)
            probs = model.predict_proba(x)[0]
            raw_pred = str(model.classes_[int(np.argmax(probs))])
            pred = raw_pred if float(np.max(probs)) >= args.min_confidence else "不确定"
            votes.append(pred)
            stable = majority_vote(votes)

            elapsed = time.time() - start_time
            print(
                f"[{elapsed:6.1f}s] packets={valid_packets:5d} "
                f"pred={pred} stable={stable} probs=({format_probs(labels, probs)})"
            )
            next_predict_at += args.step

    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        collector.disconnect()


if __name__ == "__main__":
    main()
