"""Publication logic: change detection + coalescing."""
from __future__ import annotations

import asyncio

import pytest


@pytest.mark.asyncio
async def test_first_publish_emitted(monkeypatch):
    from web.services.mqtt import PublishCoalescer
    pc = PublishCoalescer(monotonic=lambda: 0.0)
    sent = []
    async def sink(topic, payload, retain, qos):
        sent.append((topic, payload, retain, qos))
    await pc.consider("a/state", b"42", min_interval=1.0, sink=sink,
                      retain=True, qos=1)
    assert sent == [("a/state", b"42", True, 1)]


@pytest.mark.asyncio
async def test_unchanged_payload_suppressed(monkeypatch):
    from web.services.mqtt import PublishCoalescer
    now = [0.0]
    pc = PublishCoalescer(monotonic=lambda: now[0])
    sent = []
    async def sink(topic, payload, retain, qos):
        sent.append((topic, payload))
    await pc.consider("a/state", b"42", min_interval=0.0,
                      sink=sink, retain=True, qos=1)
    now[0] = 10.0  # well past any interval
    await pc.consider("a/state", b"42", min_interval=0.0,
                      sink=sink, retain=True, qos=1)
    assert sent == [("a/state", b"42")]


@pytest.mark.asyncio
async def test_changed_payload_emitted_after_interval(monkeypatch):
    from web.services.mqtt import PublishCoalescer
    now = [0.0]
    pc = PublishCoalescer(monotonic=lambda: now[0])
    sent = []
    async def sink(topic, payload, retain, qos):
        sent.append((topic, payload))

    await pc.consider("a/state", b"1", min_interval=2.0,
                      sink=sink, retain=True, qos=1)
    now[0] = 0.5
    await pc.consider("a/state", b"2", min_interval=2.0,
                      sink=sink, retain=True, qos=1)
    # Within the interval — should NOT have fired the second publish yet.
    # But the value is now pending.
    assert sent == [("a/state", b"1")]

    # When the interval elapses, the deadline-flush yields the latest value.
    now[0] = 2.5
    await pc.flush_due(sink)
    assert sent == [("a/state", b"1"), ("a/state", b"2")]


@pytest.mark.asyncio
async def test_intermediate_frames_dropped(monkeypatch):
    from web.services.mqtt import PublishCoalescer
    now = [0.0]
    pc = PublishCoalescer(monotonic=lambda: now[0])
    sent = []
    async def sink(topic, payload, retain, qos):
        sent.append(payload)

    await pc.consider("a", b"1", min_interval=5.0,
                      sink=sink, retain=False, qos=1)
    now[0] = 1.0
    await pc.consider("a", b"2", min_interval=5.0,
                      sink=sink, retain=False, qos=1)
    now[0] = 2.0
    await pc.consider("a", b"3", min_interval=5.0,
                      sink=sink, retain=False, qos=1)
    now[0] = 6.0
    await pc.flush_due(sink)
    # Only the first and the final value should have been sent.
    assert sent == [b"1", b"3"]


@pytest.mark.asyncio
async def test_flush_due_does_nothing_when_no_pending(monkeypatch):
    from web.services.mqtt import PublishCoalescer
    pc = PublishCoalescer(monotonic=lambda: 0.0)
    sent = []
    async def sink(*a, **kw):
        sent.append(1)
    await pc.flush_due(sink)
    assert sent == []


@pytest.mark.asyncio
async def test_revert_to_published_value_cancels_pending():
    """If a stashed-pending value is overwritten by the originally-published
    value, the pending entry should be cancelled (no redundant publish on
    flush_due)."""
    from web.services.mqtt import PublishCoalescer
    now = [0.0]
    pc = PublishCoalescer(monotonic=lambda: now[0])
    sent = []
    async def sink(topic, payload, retain, qos):
        sent.append(payload)

    await pc.consider("a", b"1", min_interval=5.0,
                      sink=sink, retain=False, qos=1)
    now[0] = 1.0
    await pc.consider("a", b"2", min_interval=5.0,
                      sink=sink, retain=False, qos=1)
    now[0] = 2.0
    # Revert to the originally-published value while still inside the
    # cooldown — should cancel pending and emit nothing.
    await pc.consider("a", b"1", min_interval=5.0,
                      sink=sink, retain=False, qos=1)
    now[0] = 6.0
    await pc.flush_due(sink)
    assert sent == [b"1"]  # only the original publish
