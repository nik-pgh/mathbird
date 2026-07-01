"""Student-model grader seam — see ``base.py`` for the Protocol."""

from .base import Grader, GradeResult, NodeUpdate
from .factory import get_grader

__all__ = ["GradeResult", "Grader", "NodeUpdate", "get_grader"]
