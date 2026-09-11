"""Safe error responses for unexpected exceptions (P1-13).

Route handlers that catch bare `Exception` and do `HTTPException(500, str(exc))`
leak database/library internals (table names, columns, constraint names, and
sometimes parameter values) straight to the client. This helper logs the full
exception server-side with a correlation id and returns only that id to the
caller, so support can find the real error in logs without exposing it.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException

logger = logging.getLogger("opsmind.api.errors")


def safe_internal_error(exc: Exception, *, context: str, status_code: int = 500) -> HTTPException:
    """Log `exc` with a correlation id and return a generic HTTPException.

    Usage:
        except Exception as exc:
            raise safe_internal_error(exc, context="sql_run") from exc
    """
    request_id = uuid.uuid4().hex[:12]
    logger.exception("internal_error context=%s request_id=%s", context, request_id)
    return HTTPException(
        status_code=status_code,
        detail={"error": "internal_error", "request_id": request_id},
    )
