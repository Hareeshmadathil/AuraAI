"""
Custom exception hierarchy for AuraAI Creator OS.

These exceptions give AuraAI a consistent way to classify failures,
record them in logs, display them in the dashboard, and decide whether
a workflow should retry, stop, or escalate.
"""

from __future__ import annotations

from typing import Any


class AuraAIError(Exception):
    """
    Base exception for expected AuraAI application errors.

    Attributes:
        message:
            Human-readable explanation of the failure.
        error_code:
            Stable machine-readable identifier.
        details:
            Optional structured diagnostic information.
        retryable:
            Whether an automated workflow may safely retry.
    """

    default_error_code = "AURAAI_ERROR"

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)

        self.message = message
        self.error_code = error_code or self.default_error_code
        self.details = dict(details or {})
        self.retryable = retryable

    def __str__(self) -> str:
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the exception into a dashboard/API-friendly dictionary.
        """

        return {
            "exception_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details,
            "retryable": self.retryable,
        }


class ConfigurationError(AuraAIError):
    """Raised when required settings are missing or invalid."""

    default_error_code = "CONFIGURATION_ERROR"


class ValidationError(AuraAIError):
    """Raised when AuraAI receives invalid application data."""

    default_error_code = "VALIDATION_ERROR"


class StorageError(AuraAIError):
    """Raised when a filesystem or database operation fails."""

    default_error_code = "STORAGE_ERROR"


class ProviderError(AuraAIError):
    """Raised when an external AI or service provider fails."""

    default_error_code = "PROVIDER_ERROR"

    def __init__(
        self,
        message: str,
        *,
        provider_name: str | None = None,
        details: dict[str, Any] | None = None,
        retryable: bool = True,
    ) -> None:
        combined_details = dict(details or {})

        if provider_name:
            combined_details["provider_name"] = provider_name

        super().__init__(
            message,
            details=combined_details,
            retryable=retryable,
        )


class AgentError(AuraAIError):
    """Raised when an employee-agent cannot complete assigned work."""

    default_error_code = "AGENT_ERROR"

    def __init__(
        self,
        message: str,
        *,
        agent_name: str | None = None,
        task_id: str | None = None,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        combined_details = dict(details or {})

        if agent_name:
            combined_details["agent_name"] = agent_name

        if task_id:
            combined_details["task_id"] = task_id

        super().__init__(
            message,
            details=combined_details,
            retryable=retryable,
        )


class WorkflowError(AuraAIError):
    """Raised when an AuraAI workflow cannot continue."""

    default_error_code = "WORKFLOW_ERROR"

    def __init__(
        self,
        message: str,
        *,
        workflow_name: str | None = None,
        job_id: str | None = None,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        combined_details = dict(details or {})

        if workflow_name:
            combined_details["workflow_name"] = workflow_name

        if job_id:
            combined_details["job_id"] = job_id

        super().__init__(
            message,
            details=combined_details,
            retryable=retryable,
        )


class TaskCancelledError(AuraAIError):
    """Raised when a user or supervisor cancels active work."""

    default_error_code = "TASK_CANCELLED"


class PermissionDeniedError(AuraAIError):
    """Raised when an agent is not allowed to perform an operation."""

    default_error_code = "PERMISSION_DENIED"


class DependencyUnavailableError(AuraAIError):
    """Raised when a required local tool or external dependency is unavailable."""

    default_error_code = "DEPENDENCY_UNAVAILABLE"

    def __init__(
        self,
        message: str,
        *,
        dependency_name: str | None = None,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        combined_details = dict(details or {})

        if dependency_name:
            combined_details["dependency_name"] = dependency_name

        super().__init__(
            message,
            details=combined_details,
            retryable=retryable,
        )