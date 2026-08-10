"""SportsDataIO-specific exceptions."""


class SportsDataIOError(RuntimeError):
    """Base exception for SportsDataIO integration."""


class TrialDataWarning(UserWarning):
    """Raised when trial/scrambled data is being ingested."""


class RateLimitError(SportsDataIOError):
    """API rate limit exceeded."""


class AuthenticationError(SportsDataIOError):
    """Invalid or expired API key."""


class EndpointNotFoundError(SportsDataIOError):
    """Requested SportsDataIO endpoint does not exist."""