import time

import aiohttp


async def run_http_check(
    url: str, timeout_seconds: float = 30
) -> tuple[str, int | None, int, str | None]:
    """Run a single HTTP check and return (status, status_code, response_time_ms, error_message)."""
    try:
        timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        start = time.monotonic()
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                elapsed_ms = round((time.monotonic() - start) * 1000)
                if response.status >= 500:
                    return ("down", response.status, elapsed_ms, None)
                return ("up", response.status, elapsed_ms, None)
    except Exception as e:
        return ("down", None, 0, str(e))
