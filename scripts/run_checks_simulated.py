"""Live simulation loop: drop-in replacement for run_checks_local.py.

Generates realistic synthetic uptime results every 60 seconds without making
real HTTP requests. Maintains per-check state so outages cluster naturally.

No Django dependency — boto3 + stdlib only.

Usage:
    python scripts/run_checks_simulated.py

Respects DYNAMODB_ENDPOINT_URL and AWS_REGION env vars.
"""

import logging
import os
import random
import re
import time
from datetime import datetime, timezone

import boto3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 60


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


class _CheckState:
    """Per-check simulation state so outages persist across loop iterations."""

    def __init__(self, check_id: str, url: str):
        self.check_id = check_id
        self.always_failing = _is_always_failing(url)
        self.base_ms = _base_response_ms(check_id)
        self.rng = random.Random()
        self.in_outage = False
        self.outage_remaining = 0

    def tick(self) -> tuple[str, int, int | None, str | None]:
        """Return (status, response_ms, status_code, error_message)."""
        if self.always_failing:
            return "down", 0, 503, "simulated always-failing endpoint"

        if self.in_outage:
            self.outage_remaining -= 1
            if self.outage_remaining <= 0:
                self.in_outage = False
            return "down", 0, None, "simulated outage"

        # ~0.00025 probability of starting a 10-25 minute outage
        if self.rng.random() < 0.00025:
            self.in_outage = True
            self.outage_remaining = self.rng.randint(10, 25) - 1
            return "down", 0, None, "simulated outage"

        noise = self.rng.gauss(0, self.base_ms * 0.2)
        if self.rng.random() < 0.03:
            response_ms = max(1, int(self.base_ms * self.rng.uniform(2, 5) + noise))
        else:
            response_ms = max(1, int(self.base_ms + noise))
        return "up", response_ms, 200, None


def _write_results(ddb, results: list[dict]) -> None:
    for result in results:
        item = {
            "check_id": {"S": result["check_id"]},
            "timestamp": {"S": result["timestamp"]},
            "tenant_id": {"S": result["tenant_id"]},
            "status": {"S": result["status"]},
            "response_time_ms": {"N": str(result["response_time_ms"])},
        }
        if result["status_code"] is not None:
            item["status_code"] = {"N": str(result["status_code"])}
        if result["error_message"] is not None:
            item["error_message"] = {"S": result["error_message"]}
        ddb.put_item(TableName="results", Item=item)


def main():
    logger.info("Starting simulated uptime check runner (interval=%ds)", INTERVAL_SECONDS)

    # State persists across loop iterations for outage clustering
    states: dict[str, _CheckState] = {}

    while True:
        try:
            ddb = _get_dynamodb_client()
            checks = _load_active_checks(ddb)

            if not checks:
                logger.info("No active checks found")
            else:
                # Init state for any newly discovered checks
                for check in checks:
                    if check["check_id"] not in states:
                        states[check["check_id"]] = _CheckState(
                            check["check_id"], check["url"]
                        )

                timestamp = datetime.now(timezone.utc).isoformat()
                results = []
                for check in checks:
                    state = states[check["check_id"]]
                    status, response_ms, status_code, error_message = state.tick()
                    results.append(
                        {
                            "check_id": check["check_id"],
                            "tenant_id": check["tenant_id"],
                            "timestamp": timestamp,
                            "status": status,
                            "response_time_ms": response_ms,
                            "status_code": status_code,
                            "error_message": error_message,
                        }
                    )

                _write_results(ddb, results)
                up = sum(1 for r in results if r["status"] == "up")
                logger.info(
                    "Simulated %d checks: %d up, %d down",
                    len(results),
                    up,
                    len(results) - up,
                )

        except Exception:
            logger.exception("Error during check cycle")

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
