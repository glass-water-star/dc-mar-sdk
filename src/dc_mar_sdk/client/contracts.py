"""Exceptions raised when MAR responses violate a typed contract."""

from __future__ import annotations


class ContractValidationError(ValueError):
    """The live API response did not match the selected MAR operation contract."""

    def __init__(self, method: str, operation: str, detail: str) -> None:
        super().__init__(f"Invalid response for {method} {operation}: {detail}")
        self.method = method
        self.operation = operation
        self.detail = detail
