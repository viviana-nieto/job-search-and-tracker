#!/usr/bin/env python3
"""Analyze outreach outcomes to find best-performing message patterns."""

import json
import os
import sys
from collections import defaultdict

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(PROJECT_DIR, "data", "outreach-history.json")


def load_history():
    with open(HISTORY_FILE) as f:
        return json.load(f)


def is_positive(outcome):
    return outcome in ("accepted", "replied", "interview")


def score_messages():
    """Analyze outreach data and print a performance report."""
    history = load_history()
    connections = [c for c in history["connections"] if c.get("direction") == "OUTGOING"]

    total = len(connections)
    if total == 0:
        print("No outreach data to analyze.")
        return

    positive = sum(1 for c in connections if is_positive(c.get("outcome", "")))
    pending = sum(1 for c in connections if c.get("outcome") in ("pending", None))

    print("=" * 60)
    print("  MESSAGE PERFORMANCE REPORT")
    print("=" * 60)
    print(f"\nTotal outreach: {total}")
    print(f"Positive outcomes: {positive} ({positive/total*100:.0f}%)")
    print(f"Pending: {pending}")
    print(f"Applications: {len(history.get('applications', []))}")

    # Break down by dimension
    dimensions = {
        "Message Type": "type",
        "Company Size": "company_size",
        "Recipient Role": "recipient_role",
    }

    for label, key in dimensions.items():
        buckets = defaultdict(lambda: {"total": 0, "positive": 0, "pending": 0, "times": []})

        for c in connections:
            val = c.get(key, "unknown")
            buckets[val]["total"] += 1
            if is_positive(c.get("outcome", "")):
                buckets[val]["positive"] += 1
            if c.get("outcome") in ("pending", None):
                buckets[val]["pending"] += 1
            if c.get("response_time_days") is not None:
                buckets[val]["times"].append(c["response_time_days"])

        if not buckets or all(v["total"] == 0 for v in buckets.values()):
            continue

        print(f"\n--- {label} ---")
        print(f"  {'Category':<25} {'Sent':>5} {'Positive':>10} {'Rate':>8} {'Avg Days':>10}")
        print(f"  {'-'*25} {'-'*5} {'-'*10} {'-'*8} {'-'*10}")

        for cat, data in sorted(buckets.items(), key=lambda x: -x[1]["positive"]):
            rate = (data["positive"] / data["total"] * 100) if data["total"] > 0 else 0
            avg_time = f"{sum(data['times'])/len(data['times']):.1f}" if data["times"] else "-"
            print(f"  {cat:<25} {data['total']:>5} {data['positive']:>10} {rate:>7.0f}% {avg_time:>10}")

    # Message length analysis
    print(f"\n--- Message Length ---")
    short = [c for c in connections if len(c.get("message", "")) <= 300]
    long = [c for c in connections if len(c.get("message", "")) > 300]

    for label, group in [("Short (<=300)", short), ("Long (>300)", long)]:
        if not group:
            continue
        pos = sum(1 for c in group if is_positive(c.get("outcome", "")))
        rate = (pos / len(group) * 100) if group else 0
        print(f"  {label:<25} {len(group):>5} {pos:>10} {rate:>7.0f}%")

    # Top performing messages
    responded = [c for c in connections if is_positive(c.get("outcome", ""))]
    if responded:
        print(f"\n--- Top Performing Messages ---")
        for c in responded[:5]:
            msg_preview = c.get("message", "")[:80] + "..." if len(c.get("message", "")) > 80 else c.get("message", "")
            print(f"\n  [{c.get('outcome')}] {c.get('name')} @ {c.get('company')}")
            print(f"  Type: {c.get('type', 'unknown')} | Size: {c.get('company_size', 'unknown')} | Role: {c.get('recipient_role', 'unknown')}")
            print(f"  \"{msg_preview}\"")

    # Recommendations
    print(f"\n--- Recommendations ---")
    if total < 10:
        print(f"  Need more data. You have {total} outreach entries. Aim for 20+ for meaningful patterns.")
    else:
        # Find best performing dimension values
        for label, key in dimensions.items():
            buckets = defaultdict(lambda: {"total": 0, "positive": 0})
            for c in connections:
                val = c.get(key, "unknown")
                buckets[val]["total"] += 1
                if is_positive(c.get("outcome", "")):
                    buckets[val]["positive"] += 1

            best = max(buckets.items(),
                       key=lambda x: (x[1]["positive"] / x[1]["total"]) if x[1]["total"] >= 3 else 0,
                       default=None)
            if best and best[1]["total"] >= 3:
                rate = best[1]["positive"] / best[1]["total"] * 100
                print(f"  Best {label}: {best[0]} ({rate:.0f}% response rate, n={best[1]['total']})")

    print()


def main():
    score_messages()


if __name__ == "__main__":
    main()
