"""Domain-level exceptions, mapped to HTTP responses in main.py."""


class NotFoundError(Exception):
    def __init__(self, message: str):
        self.message = message


class ConflictError(Exception):
    def __init__(self, message: str):
        self.message = message
