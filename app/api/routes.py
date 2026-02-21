"""
API routes for request ingestion, processing trigger, and status retrieval.

This layer is responsible only for HTTP orchestration:
- Delegates persistence to the repository.
- Delegates business workflow to the orchestration service.
- Keeps endpoints thin and side‑effect boundaries explicit.
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException, Response

from api.schemas import RequestCreate, ResponseCreate, ResponseStatus
from core.repository import InMemoryRepository
from core.state import RequestStatus
from services.orchestration import process_request

# Router instance grouping all request-related endpoints.
router = APIRouter()

# Application-scoped in-memory repository.
# Acts as a lightweight persistence layer for the lifetime of the process.
repository = InMemoryRepository()


# Create a new request in "queued" state.
# Only stores the raw user input; processing is triggered separately.
@router.post("/v1/requests", status_code=201, response_model=ResponseCreate)
async def create_request(body: RequestCreate) -> ResponseCreate:
    # Persist the request and return its generated identifier.
    req_id = await repository.create(body.user_input)
    return ResponseCreate(id=req_id)


# Trigger asynchronous processing of an existing request.
# Returns:
# - 202 if processing has been scheduled
# - 200 if already processed or in progress
# - 404 if the request does not exist
@router.post("/v1/requests/{req_id}/process")
async def trigger_processing(
    req_id: str,
    background_tasks: BackgroundTasks,
) -> Response:

    # Retrieve current request state.
    entry = repository.get(req_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Request not found")

    status = entry["status"]

    # Idempotency guard: avoid re-processing requests
    # that are already terminal or currently running.
    if status in (
        RequestStatus.PROCESSING,
        RequestStatus.SENT,
        RequestStatus.FAILED,
    ):
        return Response(status_code=200)

    # Transition to PROCESSING synchronously to ensure
    # consistent state visibility before background execution starts.
    await repository.update_status(req_id, RequestStatus.PROCESSING)

    # Delegate heavy work to background task to keep
    # HTTP response latency minimal and non-blocking.
    background_tasks.add_task(process_request, repository, req_id)

    return Response(status_code=202)


# Retrieve the current status of a request.
@router.get("/v1/requests/{req_id}", response_model=ResponseStatus)
def get_status(req_id: str) -> ResponseStatus:
    # Fetch stored request entry.
    entry = repository.get(req_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Request not found")

    status_value = entry["status"]
    # Normalize enum to its string value for API response compatibility.
    if isinstance(status_value, RequestStatus):
        status_value = status_value.value

    return ResponseStatus(
        id=req_id,
        status=status_value,
    )