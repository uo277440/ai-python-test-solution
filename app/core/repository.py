"""
In-memory repository implementation for request persistence.

Provides:
- Thread-safe creation of requests.
- Controlled state transitions.
- Simple lookup operations.

Intended as a lightweight storage layer for the technical exercise.
"""

import asyncio
import uuid
from typing import Dict, Optional

from .state import RequestStatus, can_transition


# In-memory persistence adapter.
# Encapsulates storage and enforces state transition rules.
class InMemoryRepository:
    # Initialize storage dictionary and async lock
    # to guarantee safe concurrent access.
    def __init__(self) -> None:
        self._data: Dict[str, dict] = {}
        self._lock = asyncio.Lock()

    # Create a new request in QUEUED state and return its id.
    # Operation is protected by a lock to avoid race conditions.
    async def create(self, user_input: str) -> str:
        async with self._lock:
            req_id = str(uuid.uuid4())
            self._data[req_id] = {
                "user_input": user_input,
                "status": RequestStatus.QUEUED,
            }
            return req_id

    # Retrieve stored request entry by id.
    # Returns None if the request does not exist.
    def get(self, req_id: str) -> Optional[dict]:
        return self._data.get(req_id)

    # Perform a validated state transition.
    # Returns True if the transition is applied, False otherwise.
    async def transition(self, req_id: str, new_status: RequestStatus) -> bool:
        async with self._lock:
            entry = self._data.get(req_id)
            if not entry:
                return False

            current_status = entry["status"]

            # Enforce allowed state transitions defined in the state module.
            if not can_transition(current_status, new_status):
                return False

            entry["status"] = new_status
            return True

    async def update_status(self, req_id: str, new_status: RequestStatus) -> None:
        """
        Update request status using validated state transitions.
        Silently ignores invalid transitions or missing ids.
        """
        await self.transition(req_id, new_status)

    # Check whether a request id is present in the repository.
    def exists(self, req_id: str) -> bool:
        return req_id in self._data