"""
Pydantic schemas defining the public HTTP contract.

These models:
- Validate incoming payloads.
- Define structured API responses.
- Provide explicit typing for OpenAPI generation.
"""
from typing import Literal
from pydantic import BaseModel, Field


# Payload used to create a new request.
# Contains the raw natural language input provided by the user.
class RequestCreate(BaseModel):
    user_input: str = Field(
        ...,
        json_schema_extra={
            "example": "Manda un sms a +1234567890 diciendo 'Hola, ¿cómo estás?'"
        },
    )


# Response returned after request creation.
# Exposes only the generated identifier.
class ResponseCreate(BaseModel):
    id: str = Field(
        ...,
        json_schema_extra={
            "example": "786fty6-e29b-41d4-a716-875435426614"
        },
    )


# Explicit set of allowed status values exposed via the API.
# Keeps the HTTP layer decoupled from internal enum implementations.
RequestStatusLiteral = Literal["queued", "processing", "sent", "failed"]


# Response model for retrieving request processing status.
class ResponseStatus(BaseModel):
    id: str
    status: RequestStatusLiteral