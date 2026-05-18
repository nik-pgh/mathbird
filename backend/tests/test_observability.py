from __future__ import annotations

import os
import sys
from types import SimpleNamespace

from app import observability


class _Instrumentor:
    def __init__(self) -> None:
        self.instrumented = False

    def instrument(self, *, tracer_provider) -> None:  # noqa: ANN001
        self.instrumented = tracer_provider is not None


def test_setup_phoenix_uses_phoenix_otel_env_vars(
    monkeypatch,
) -> None:
    calls: list[dict] = []

    def fake_register(**kwargs):
        calls.append(kwargs)
        return object()

    monkeypatch.setattr(observability, "_initialized", False)
    monkeypatch.setattr(
        observability,
        "get_settings",
        lambda: SimpleNamespace(
            phoenix_enabled=True,
            phoenix_project="mathbird-test",
            phoenix_endpoint="https://app.phoenix.arize.com/s/test-space",
            phoenix_api_key="test-api-key",
        ),
    )
    monkeypatch.delenv("PHOENIX_PROJECT_NAME", raising=False)
    monkeypatch.delenv("PHOENIX_COLLECTOR_ENDPOINT", raising=False)
    monkeypatch.delenv("PHOENIX_API_KEY", raising=False)

    monkeypatch.setitem(
        sys.modules,
        "openinference.instrumentation.openai",
        SimpleNamespace(OpenAIInstrumentor=_Instrumentor),
    )
    monkeypatch.setitem(
        sys.modules,
        "openinference.instrumentation.llama_index",
        SimpleNamespace(LlamaIndexInstrumentor=_Instrumentor),
    )
    monkeypatch.setitem(sys.modules, "phoenix.otel", SimpleNamespace(register=fake_register))

    observability.setup_phoenix()

    assert calls == [
        {
            "project_name": "mathbird-test",
            "auto_instrument": False,
            "batch": True,
        }
    ]
    assert "endpoint" not in calls[0]
    assert "api_key" not in calls[0]
    assert "headers" not in calls[0]
    assert calls[0]["project_name"] == "mathbird-test"
    assert observability._initialized is True

    assert os.environ["PHOENIX_PROJECT_NAME"] == "mathbird-test"
    assert os.environ["PHOENIX_COLLECTOR_ENDPOINT"] == "https://app.phoenix.arize.com/s/test-space"
    assert os.environ["PHOENIX_API_KEY"] == "test-api-key"
    assert sys.modules["phoenix.otel"].register is fake_register
    assert observability.get_settings().phoenix_project == "mathbird-test"
