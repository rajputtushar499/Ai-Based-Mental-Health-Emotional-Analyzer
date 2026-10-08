"""Shared error helpers."""
from flask import jsonify


class AnalysisError(Exception):
    """An expected, user-presentable error raised by the analysis services."""

    def __init__(self, message: str, status: int = 400, code: str = "analysis_error"):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


class InvalidAudioError(AnalysisError):
    def __init__(self, message: str = "The audio file could not be read."):
        super().__init__(message, 422, "invalid_audio")


class ModelUnavailableError(AnalysisError):
    def __init__(self, message: str = "The AI model is not available."):
        super().__init__(message, 503, "model_unavailable")


def json_error(status: int, message: str, code: str = "error"):
    """Consistent JSON error body used by every API endpoint."""
    response = jsonify({"error": message, "code": code})
    response.status_code = status
    return response
