from __future__ import annotations


class ServiceError(Exception):
    pass


class NotFound(ServiceError):
    pass


class Forbidden(ServiceError):
    pass


class Invalid(ServiceError):
    pass


class Conflict(ServiceError):
    def __init__(self, current=None, message: str = "Version conflict"):
        super().__init__(message)
        self.current = current
