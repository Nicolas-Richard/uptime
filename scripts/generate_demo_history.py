"""Backfill synthetic uptime check results into DynamoDB for demo purposes.

No Django dependency — boto3 + stdlib only.

Usage:
    python scripts/generate_demo_history.py [--days 14]

Respects DYNAMODB_ENDPOINT_URL and AWS_REGION env vars.
"""

import argparse
import os
import random
import re
import sys
from datetime import datetime, timedelta, timezone

import boto3


def _get_dynamodb_client():
    endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL")
    kwargs = {"region_name": os.environ.get("AWS_REGION", "us-east-1")}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
        kwargs["aws_access_key_id"] = os.environ.get("AWS_ACCESS_KEY_ID", "local")
        kwargs["aws_secret_access_key"] = os.environ.get("AWS_SECRET_ACCESS_KEY", "local")
    return boto3.client("dynamodb", **kwargs)


def _load_active_checks(ddb):
    checks = []
    params = {
        "TableName": "checks",
        "IndexName": "is_active-tenant_id",
        "KeyConditionExpression": "is_active = :active",
        "ExpressionAttributeValues": {":active": {"S": "true"}},
    }
    while True:
        response = ddb.query(**params)
        for item in response.get("Items", []):
            checks.append({
                "tenant_id": item["tenant_id"]["S"],
                "check_id": item["check_id"]["S"],
                "url": item["url"]["S"],
            })
        if "LastEvaluatedKey" not in response:
            break
        params["ExclusiveStartKey"] = response["LastEvaluatedKey"]
    return checks


def _is_always_failing(url: str) -> bool:
    """Return True for URLs that always return 5xx (e.g. httpbin /status/503)."""
    return bool(re.search(r"/status/[5]\d{2}", url))


def _base_response_ms(check_id: str) -> int:
    """Stable base response time for a check, 50-500ms, derived from check_id."""
    return random.Random(check_id + ":base_ms").randint(50, 500)


def _simulate_minutes(num_minutes: int, rng: random.Random, base_ms: int, always_failing: bool):
    """
    Generate (status, response_ms) for each minute.

    Uptime model:
    - Always-failing checks: always down
    - Normal checks: ~99.5% uptime, outages cluster 10-25 consecutive minutes,
      ~2-3 outages/week; spike probability 3%
    """
    in_outage = False
    outage_remaining = 0

    for _ in range(num_minutes):
        if always_failing:
            yield "down", 0
            continue

        if in_outage:
            outage_remaining -= 1
            if outage_remaining <= 0:
                in_outage = False
            yield "down", 0
            continue

        # ~2.5 outages/week of ~20min each → 0.5% downtime → 0.00025 trigger prob/min
        if rng.random() < 0.00025:
            in_outage = True
            outage_remaining = rng.randint(10, 25) - 1
            yield "down", 0
            continue

        # Normal "up" result with gaussian noise and occasional spike
        noise = rng.gauss(0, base_ms * 0.2)
        if rng.random() < 0.03:
            response_ms = max(1, int(base_ms * rng.uniform(2, 5) + noise))
        else:
            response_ms = max(1, int(base_ms + noise))
        yield "up", response_ms


def main():
    parser = argparse.ArgumentParser(
        description="Backfill synthetic uptime history into DynamoDB"
    )
    parser.add_argument(
        "--days", type=int, default=14, help="Days of history to backfill (default: 14)"
    )
    args = parser.parse_args()

    ddb = _get_dynamodb_client()
    checks = _load_active_checks(ddb)

    if not checks:
        print("No active checks found. Run seed_demo.py first.")
        sys.exit(1)

    print(f"Found {len(checks)} active check(s). Generating {args.days} days of history...")

    num_minutes = args.days * 24 * 60
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start = now - timedelta(days=args.days)

    total_written = 0

    for idx, check in enumerate(checks, 1):
        check_id = check["check_id"]
        url = check["url"]
        always_failing = _is_always_failing(url)
        base_ms = _base_response_ms(check_id)

        # Deterministic seed: same results on every run (idempotent)
        rng = random.Random(check_id + ":history")

        minutes = list(_simulate_minutes(num_minutes, rng, base_ms, always_failing))
        up_count = sum(1 for s, _ in minutes if s == "up")
        uptime_pct = up_count / num_minutes * 100

        label = "(always-down)" if always_failing else f"{uptime_pct:.1f}% uptime"
        print(
            f"  [{idx}/{len(checks)}] {url[:55]:<55} {label} — writing {num_minutes:,} results...",
            end="",
            flush=True,
        )

        for minute_offset, (status, response_ms) in enumerate(minutes):
            ts = (start + timedelta(minutes=minute_offset)).isoformat()
            item = {
                "check_id": {"S": check_id},
                "timestamp": {"S": ts},
                "tenant_id": {"S": check["tenant_id"]},
                "status": {"S": status},
                "response_time_ms": {"N": str(response_ms)},
            }
            if status == "up":
                item["status_code"] = {"N": "200"}
            else:
                item["status_code"] = {"N": "503"}
                item["error_message"] = {"S": "simulated outage"}

            ddb.put_item(TableName="results", Item=item)
            total_written += 1

        print(" done", flush=True)

    print(f"\nWrote {total_written:,} results across {len(checks)} check(s).")


if __name__ == "__main__":
    main()
