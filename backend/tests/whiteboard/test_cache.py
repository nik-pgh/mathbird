"""``BoardCache`` is a per-room in-process cache of AiBoard items keyed by id."""

from __future__ import annotations

from app.agent.whiteboard.cache import BoardCache
from app.agent.whiteboard.messages import AiBoardPlot, AiBoardText


def test_new_cache_is_empty() -> None:
    cache = BoardCache()
    assert cache.current_items() == []


def test_apply_adds_new_items() -> None:
    cache = BoardCache()
    item = AiBoardText(kind="text", id="eq1", markdown="$2x + 5 = 10$")

    cache.apply([item])

    assert cache.current_items() == [item]


def test_apply_same_id_twice_keeps_latest() -> None:
    cache = BoardCache()
    first = AiBoardText(kind="text", id="eq1", markdown="$2x = 5$")
    second = AiBoardText(kind="text", id="eq1", markdown="$2x = 6$")

    cache.apply([first])
    cache.apply([second])

    items = cache.current_items()
    assert len(items) == 1
    assert items[0] == second


def test_apply_mixed_kinds() -> None:
    cache = BoardCache()
    text = AiBoardText(kind="text", id="eq1", markdown="$y = x^2$")
    plot = AiBoardPlot(kind="plot", id="p1", expression="x**2")

    cache.apply([text, plot])

    items = cache.current_items()
    assert text in items
    assert plot in items
    assert len(items) == 2


def test_current_items_returns_snapshot() -> None:
    # Verify the returned list is decoupled from the cache so callers
    # can't accidentally mutate internal state.
    cache = BoardCache()
    cache.apply([AiBoardText(kind="text", id="eq1", markdown="$x = 1$")])

    snapshot = cache.current_items()
    snapshot.clear()  # caller mutates the returned list

    # Internal state is unchanged.
    assert len(cache.current_items()) == 1
