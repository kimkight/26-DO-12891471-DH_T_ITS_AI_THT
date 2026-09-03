"""The single-label check runs off the event loop, and the loop keeps answering.

Code review finding 8 (#107): every Tesseract pass on `POST /api/verify` ran on
the only event loop thread, so `GET /api/health` waited for the whole request.
Measured in the review session at 3.34 s of waiting for a 3.35 s request, and
7.8 s on the deployed target against a 5 s health-check timeout that stops the
task after three misses.

The assertion is on ordering, not on a millisecond figure (code review
finding 23): with a check in flight, the health probe is answered before the
check finishes. The check itself is stubbed with a blocking sleep, which is
exactly the shape Tesseract has from the loop's point of view, so the test
needs no engine and cannot pass by being fast.

Both requests go through one event loop, which is the whole point: a second
`TestClient` would bring its own loop and prove nothing.
"""

from __future__ import annotations

import threading
import time

import anyio
import httpx
import pytest

from app import api, batch
from app.config import settings
from app.main import app
from app.schemas import ErrorDetail
from app.verify import VerificationError

pytestmark = pytest.mark.anyio


async def test_health_is_answered_while_a_label_is_being_read(monkeypatch):
    order: list[str] = []
    reading = threading.Event()

    # The stub takes whatever the route passes, so that a new argument on the
    # real function (v1.3.0 added `cleared_fields`) cannot turn this test into
    # a stub that raises before it signals, which is a hang rather than a
    # failure; the bounded wait below is the second half of the same guard.
    def slow_check(submitted, application_values, *rest, **named):
        reading.set()
        time.sleep(0.5)  # Tesseract, from the loop's point of view
        order.append("check")
        raise VerificationError(code="no_label_to_check", message="stubbed")

    monkeypatch.setattr(api, "_check_one_label", slow_check)

    transport = httpx.ASGITransport(app=app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as client,
        anyio.create_task_group() as tasks,
    ):

        async def check():
            response = await client.post(
                "/api/verify", files={"files": ("label.png", b"pixels", "image/png")}
            )
            assert response.status_code == 422
            order.append("check returned")

        tasks.start_soon(check)
        # Wait until the stub is actually running in its worker thread. If the
        # check were on the loop, the loop would be blocked here and the probe
        # below could not run until the check had finished. Bounded, so that a
        # stub that never runs fails the test instead of parking it forever.
        started = await anyio.to_thread.run_sync(reading.wait, 10)
        assert started, "the stubbed check never started"

        response = await client.get("/api/health")
        assert response.status_code == 200
        order.append("health")

    assert order == ["health", "check", "check returned"]


async def test_health_is_answered_while_a_batch_is_streaming(monkeypatch):
    """The batch path never had finding 8's problem, and v1.4.0 keeps it that
    way: the stream is a synchronous generator Starlette iterates in a worker
    thread, and each row runs in the pool. The same ordering assertion as
    above, with the row check stubbed to a blocking sleep."""
    order: list[str] = []
    reading = threading.Event()

    def slow_row(item):
        reading.set()
        time.sleep(0.5)
        order.append("row")
        return batch.RowOutcome(
            item=item,
            name=item.files[0].filename,
            error=ErrorDetail(code="verification_failed", message="stubbed"),
        )

    monkeypatch.setattr(batch, "check_item", slow_row)

    transport = httpx.ASGITransport(app=app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as client,
        anyio.create_task_group() as tasks,
    ):

        async def run_batch():
            response = await client.post(
                "/api/verify-batch",
                files=[("files", ("label.png", b"pixels", "image/png"))],
            )
            assert response.status_code == 200
            assert '"verification_failed"' in response.text
            order.append("batch returned")

        tasks.start_soon(run_batch)
        started = await anyio.to_thread.run_sync(reading.wait, 10)
        assert started, "the stubbed row never started"

        response = await client.get("/api/health")
        assert response.status_code == 200
        order.append("health")

    assert order == ["health", "row", "batch returned"]


async def test_the_limiter_is_sized_from_the_batch_pool_setting():
    """Bounded, not merely off the loop: anyio's default pool is forty threads."""
    assert api._limiter().total_tokens == settings.effective_batch_workers


async def test_the_timing_recording_follows_the_check_into_its_thread(monkeypatch):
    """`run_sync` copies the context, so the phases land in the route's recording."""
    from app import timing

    seen: list[timing.Recording | None] = []

    def check(submitted, application_values, *rest, **named):
        seen.append(timing.current())
        raise VerificationError(code="no_label_to_check", message="stubbed")

    monkeypatch.setattr(api, "_check_one_label", check)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/verify", files={"files": ("label.png", b"pixels", "image/png")})

    assert seen
    assert seen[0] is not None
