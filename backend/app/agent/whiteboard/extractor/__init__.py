"""Board extractor seam — see ``base.py`` for the Protocol."""

from .base import BoardExtractor
from .factory import get_board_extractor

__all__ = ["BoardExtractor", "get_board_extractor"]
