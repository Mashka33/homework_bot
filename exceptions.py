class APIErrException(Exception):
    """Custom Exception class for handling Practicum.Homeworks API errors."""
    pass


class HTTPStatusError(Exception):
    """Вызывается, когда API вернул код ответа, не равный 200 (не ОК)."""

    pass

class EmptyAPIResponse(Exception):
    """Вызывается, когда API пуст"""
    pass
