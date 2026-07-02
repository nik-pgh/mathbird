"""Document listing and storage helpers shared by the HTTP API and local console."""

from app.documents.access import (
    assert_doc_access,
    filter_summaries_for_user,
    guest_can_access_doc,
    read_document_meta,
    resolve_token_doc_id,
    user_can_access_doc,
)
from app.documents.catalog import (
    SIDECAR_NAME,
    SYLLABUS_NAME,
    DocumentSummary,
    filename_from_storage_key,
    list_document_summaries,
    sidecar_key,
)

__all__ = [
    "SIDECAR_NAME",
    "SYLLABUS_NAME",
    "DocumentSummary",
    "assert_doc_access",
    "filter_summaries_for_user",
    "filename_from_storage_key",
    "guest_can_access_doc",
    "list_document_summaries",
    "read_document_meta",
    "resolve_token_doc_id",
    "sidecar_key",
    "user_can_access_doc",
]
