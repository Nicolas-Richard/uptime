"""Local runner: poll active checks and run them in a loop (no Lambda/EventBridge)."""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path so lambda_handler and core are importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lambda_handler.handler import (
    _get_dynamodb_client,
    _load_active_checks,
    _write_results,
    run_checks_batch,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 60


def main():
    logger.info("Starting local uptime check runner (interval=%ds)", INTERVAL_SECONDS)
    while True:
        try:
            ddb = _get_dynamodb_client()
            checks = _load_active_checks(ddb)

            if checks:
                results = asyncio.run(run_checks_batch(checks))
                _write_results(ddb, results)
                logger.info("Ran %d checks", len(checks))
            else:
                logger.info("No active checks found")

        except Exception:
            logger.exception("Error during check cycle")

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
