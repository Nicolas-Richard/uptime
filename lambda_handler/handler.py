"""Lambda handler: run all active uptime checks and write results to DynamoDB."""

import asyncio
import logging
import os
from datetime import datetime, timezone

import boto3

from core.uptime_checks import run_http_check

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _get_dynamodb_client():
    """Create a boto3 DynamoDB client, using local endpoint if configured."""
    endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL")
    kwargs = {"region_name": os.environ.get("AWS_REGION", "us-east-1")}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
        kwargs["aws_access_key_id"] = os.environ.get("AWS_ACCESS_KEY_ID", "local")
        kwargs["aws_secret_access_key"] = os.environ.get(
            "AWS_SECRET_ACCESS_KEY", "local"
        )
    return boto3.client("dynamodb", **kwargs)


def _parse_timeout_seconds(item: dict) -> float:
    """Parse timeout_seconds from DynamoDB item; default 30, clamp to 1-300."""
    raw = item.get("timeout_seconds")
    if not raw:
        return 30.0
    val = raw.get("N") if isinstance(raw, dict) else None
    if val is None:
        return 30.0
    try:
        secs = float(val)
    except (TypeError, ValueError):
        return 30.0
    return max(1.0, min(300.0, secs))


def _load_active_checks(ddb):
    """Load all active checks from DynamoDB using the is_active GSI."""
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
            checks.append(
                {
                    "tenant_id": item["tenant_id"]["S"],
                    "check_id": item["check_id"]["S"],
                    "url": item["url"]["S"],
                    "timeout_seconds": _parse_timeout_seconds(item),
                }
            )
        if "LastEvaluatedKey" not in response:
            break
        params["ExclusiveStartKey"] = response["LastEvaluatedKey"]
    return checks


async def _run_single_check(check):
    """Run a single check, catching exceptions so one failure doesn't abort the batch."""
    try:
        status, status_code, response_time_ms, error_message = await run_http_check(
            check["url"], timeout_seconds=check.get("timeout_seconds", 30)
        )
        return {
            "check_id": check["check_id"],
            "tenant_id": check["tenant_id"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "status_code": status_code,
            "response_time_ms": response_time_ms,
            "error_message": error_message,
        }
    except Exception as e:
        logger.error("Check %s failed unexpectedly: %s", check["check_id"], e)
        return {
            "check_id": check["check_id"],
            "tenant_id": check["tenant_id"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "down",
            "status_code": None,
            "response_time_ms": 0,
            "error_message": str(e),
        }


async def run_checks_batch(checks):
    """Run all checks in parallel and return a list of result dicts."""
    tasks = [_run_single_check(check) for check in checks]
    return await asyncio.gather(*tasks)


def _write_results(ddb, results):
    """Write check results to the results DynamoDB table."""
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


def handler(event, context):
    """AWS Lambda entry point. Runs all active checks and writes results."""
    ddb = _get_dynamodb_client()
    checks = _load_active_checks(ddb)
    logger.info("Loaded %d active checks", len(checks))

    if not checks:
        logger.info("No active checks found, exiting")
        return {"statusCode": 200, "body": "No active checks"}

    results = asyncio.run(run_checks_batch(checks))
    _write_results(ddb, results)

    logger.info("Ran %d checks, wrote %d results", len(checks), len(results))
    return {"statusCode": 200, "body": f"Ran {len(checks)} checks"}
