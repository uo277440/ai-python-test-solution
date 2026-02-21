"""
Orchestration layer coordinating the end-to-end request lifecycle.

Pipeline responsibilities:
- Acquire controlled concurrency via semaphore.
- Transition request state safely.
- Execute extraction, sanitization and validation.
- Trigger external notification.
- Ensure consistent failure handling.

This module contains no HTTP concerns and no persistence logic,
only workflow coordination.
"""

import asyncio
import httpx

from core.repository import InMemoryRepository
from core.state import RequestStatus
from infra.http_client import call_ai_extract, send_notification
from safety.sanitizer import sanitize_llm_output
from safety.validation import validate_extraction


# System prompt provided to the AI extraction endpoint.
# Defines strict structural constraints to minimize downstream ambiguity.
SYSTEM_PROMPT = """
You are a strict JSON extractor.

Your task is to convert a natural language instruction into a single structured JSON object.

You MUST return exactly one valid JSON object with these keys (and no others):
- "to"
- "message"
- "type"

Output constraints:
1. The response must be valid JSON.
2. Do NOT include markdown or code blocks.
3. Do NOT include explanations, comments, or extra text.
4. Do NOT include additional keys.
5. Keys must be lowercase.
6. Use double quotes for all keys and string values.
7. "type" must be exactly "email" or "sms".

Extraction rules:
- If an email address is present, extract it as "to".
- If a phone number is present, extract it as "to".
- Never invent or fabricate a destination.
- If no valid destination can be confidently extracted, return:
  {"to":"","message":"","type":""}

Type rules:
- If "to" is an email address, "type" must be "email".
- If "to" is a phone number, "type" must be "sms".

Message rules:
- Extract the message text exactly as written by the user.
- Do NOT paraphrase or summarize.
- Trim leading and trailing whitespace.
- If no clear message is present, return an empty string in "message".

Return ONLY the JSON object and nothing else.
"""

# Concurrency limiter for the processing pipeline.
# Prevents excessive simultaneous calls to external services.
_pipeline_semaphore = asyncio.Semaphore(20)

# Execute the full request lifecycle:
# extraction → sanitization → validation → notification.
# All transitions are guarded to maintain state consistency.
async def process_request(repo: InMemoryRepository, req_id: str) -> None:
    # Ensure bounded concurrency across processing tasks.
    async with _pipeline_semaphore:
        # Retrieve stored request data.
        entry = repo.get(req_id)
        if not entry:
            return

        # Attempt atomic transition to PROCESSING.
        # Prevents duplicate or invalid concurrent execution.
        transitioned = await repo.transition(req_id, RequestStatus.PROCESSING)
        if not transitioned:
            return

        user_input = entry.get("user_input", "")

        # Step 1: Call AI extraction service.
        try:
            raw_output = await call_ai_extract(SYSTEM_PROMPT, user_input)
        except httpx.HTTPError:
            await repo.transition(req_id, RequestStatus.FAILED)
            return

        # Step 2: Sanitize raw model output into structured JSON.
        parsed = sanitize_llm_output(raw_output)
        if not parsed:
            await repo.transition(req_id, RequestStatus.FAILED)
            return

        # Step 3: Validate normalized structure and semantic constraints.
        validated = validate_extraction(parsed)
        if not validated:
            await repo.transition(req_id, RequestStatus.FAILED)
            return

        # Step 4: Invoke external notification provider.
        try:
            await send_notification(
                to=validated["to"],
                message=validated["message"],
                type_=validated["type"],
            )
        except httpx.HTTPError:
            await repo.transition(req_id, RequestStatus.FAILED)
            return

        # Finalize request as successfully processed.
        await repo.transition(req_id, RequestStatus.SENT)