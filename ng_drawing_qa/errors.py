from __future__ import annotations


class AutoReviewError(Exception):
    """Base class for friendly AutoReview errors."""

    code = "AUTOREVIEW_ERROR"

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(AutoReviewError):
    code = "VALIDATION_ERROR"


class MissingInputError(ValidationError):
    code = "MISSING_INPUT"


class UnsupportedFileError(ValidationError):
    code = "UNSUPPORTED_FILE"


class ReviewRunError(AutoReviewError):
    code = "REVIEW_RUN_FAILED"
