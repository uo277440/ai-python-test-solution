"""
HTTP client adapter for communicating with the external AI and notification provider.

Responsibilities:
- Manage a shared AsyncClient with connection pooling.
- Apply retry policies for transient failures.
- Encapsulate provider-specific endpoints.
"""

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

# Provider configuration (base URL and authentication key).
# In a production setup, these would come from environment variables.
PROVIDER_BASE_URL = "http://localhost:3001"
API_KEY = "test-dev-2026"

# Default headers applied to every outbound request.
_HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
}

# Lazily initialized shared AsyncClient instance.
# Reused across calls to leverage connection pooling.
_client: httpx.AsyncClient | None = None


# Return a shared AsyncClient instance.
# Initializes the client on first access (lazy singleton pattern).
def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        # Configure timeouts and connection pool limits
        # to remain stable under concurrent load.
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                timeout=10.0,
                connect=3.0,
                read=10.0,
                write=10.0,
                pool=5.0,
            ),
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=40,
            ),
        )
    return _client


# Gracefully close the shared HTTP client during application shutdown.
async def close_client() -> None:
    global _client
    if _client:
        await _client.aclose()
        _client = None


# Determine whether an exception represents a transient condition
# that is safe to retry (rate limiting, server errors, transport issues).
def _is_transient_error(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    if isinstance(exc, httpx.TransportError):
        return True
    return False


# Call the AI extraction endpoint with retry logic applied.
# Retries are triggered only for transient failures.
@retry(
    retry=retry_if_exception(_is_transient_error),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=8),
)
async def call_ai_extract(system_prompt: str, user_input: str) -> str:
    # Structured message format expected by the provider.
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]
    }

    client = _get_client()

    response = await client.post(
        f"{PROVIDER_BASE_URL}/v1/ai/extract",
        json=payload,
        headers=_HEADERS,
    )

    response.raise_for_status()

    data = response.json()
    choices = data.get("choices", [])
    if not choices:
        return ""

    return choices[0].get("message", {}).get("content", "")


# Send a notification through the provider with retry protection.
# Raises after retries are exhausted for non-transient failures.
@retry(
    retry=retry_if_exception(_is_transient_error),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=8),
)
async def send_notification(to: str, message: str, type_: str) -> None:
    # Provider notification contract.
    payload = {
        "to": to,
        "message": message,
        "type": type_,
    }

    client = _get_client()

    response = await client.post(
        f"{PROVIDER_BASE_URL}/v1/notify",
        json=payload,
        headers=_HEADERS,
    )

    response.raise_for_status()