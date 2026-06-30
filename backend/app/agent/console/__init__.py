"""Local text console and YAML simulation helpers (no LiveKit worker required).

Scripts: ``scripts/agent_console.py``, ``scripts/simulate_conversation.py``.
"""

from app.agent.console.identity import prompt_console_identity
from app.agent.console.runtime import (
    enable_text_only_job,
    local_agent_runtime,
    local_text_job,
)
from app.agent.console.ui import (
    format_run_event,
    print_banner,
    print_dim,
    print_latest_assistant_from_history,
    print_turn_divider,
    print_user_message,
    render_run_events,
)

__all__ = [
    "enable_text_only_job",
    "format_run_event",
    "local_agent_runtime",
    "local_text_job",
    "print_banner",
    "print_dim",
    "print_latest_assistant_from_history",
    "print_turn_divider",
    "print_user_message",
    "prompt_console_identity",
    "render_run_events",
]
