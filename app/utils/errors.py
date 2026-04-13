class CompLaiError(Exception):
    """Base exception for CompLai."""
    pass


class ScraperError(CompLaiError):
    """Raised when a scraper fails."""
    pass


class ExtractionError(CompLaiError):
    """Raised when OCR/extraction fails."""
    pass


class ClassificationError(CompLaiError):
    """Raised when classification fails."""
    pass


class AuthorizationError(CompLaiError):
    """Raised on authorization failure."""
    pass
