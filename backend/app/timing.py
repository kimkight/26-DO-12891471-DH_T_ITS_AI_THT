"""Where a request's time actually went, recorded as it goes (NFR-1).

**This module exists because the number the response used to call `elapsed_ms`
was not elapsed.** It was measured inside `app.verify.verify_photos`, which
starts after the multipart form has been parsed, after the uploaded files have
been classified, and after the COLA document has been read. On the
application-document path those three steps are most of the request. Measured at
the deployed v1.1.0 build on 2026-08-30 with the author's own mezcal COLA PDF,
`elapsed_ms` and `ocr_ms` came back within 2 ms of each other on all three runs:
the field was reporting the label-side OCR span and calling itself the request.

The interface then made it worse. It printed the browser's wall clock,
subtracted the server's figure, and told the agent the remainder was "sending
the image and receiving the answer". A control POST of the same 382 KB file to a
path that processes nothing crossed the wire in 68 to 111 ms. So about three and
a half seconds of real server work per request was both missing from the
instrumentation and actively mislabelled as network time.

**The rule this module enforces: measure everything, attribute it honestly, and
never infer a phase by subtraction.** A number nobody measured is not evidence,
and the next person optimising this path deserves figures rather than a guess.

## How it works

A request opens one `recording()`. Everything inside it that takes real time
opens a `phase(name)`, and the elapsed wall time lands in that bucket. The
buckets are **disjoint by construction**: no phase is opened inside another, so
they sum to the work that was accounted for, and `total_ms` minus that sum is
the part that was not, which is reported as its own line rather than assigned to
something it might not be.

A `ContextVar` rather than a parameter threaded through eight call sites,
because the OCR calls being measured sit four frames below the route and two
frames below code that has no business knowing about instrumentation. The
default is None, so anything running outside a recording records nothing and
costs one attribute lookup.

**Threads do not inherit it, and that is what the batch path wants.**
`ThreadPoolExecutor.submit` does not copy the caller's context, so a batch
worker sees the default. Each row opens its own recording, which is right: a
batch line reports the time that row took, not a share of the batch's.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

# The phases, in the order they happen on the slowest path. Named here so that a
# reader can see the shape of a request without reading the route, and so that a
# typo in a `phase()` call is a name this list does not carry rather than a
# silent extra bucket.
#
# `classify_ocr` and `document_ocr` are OCR of an *image* submitted as one side
# or the other; `page_ocr` is OCR of PDF pages rendered because the file carried
# no text layer; `artwork_ocr` is OCR of pictures lifted out of a PDF. They are
# separate because an operator looking at a slow request needs to know which of
# those four a given second was spent in, and they are four different documents
# arriving.
PHASES = (
    "classify_ocr",
    "document_pdfium",
    "document_ocr",
    "page_ocr",
    "artwork_ocr",
    "label_ocr",
    "compare",
)

# Which phases are Tesseract. Summed into the `ocr_ms` the response has always
# carried, so that field keeps meaning what it says while gaining the passes it
# used to miss.
OCR_PHASES = ("classify_ocr", "document_ocr", "page_ocr", "artwork_ocr", "label_ocr")


@dataclass
class Recording:
    """One request's phase totals, in milliseconds, plus how many spans each had.

    The counts are reported alongside the durations because they are the half
    that makes a duration diagnosable. "OCR took 3.3 seconds" is a fact about
    the machine; "OCR took 3.3 seconds over three passes" is a fact about the
    code, and it is the one that led to this change.
    """

    ms: dict[str, float] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    started: float = field(default_factory=time.perf_counter)

    def add(self, name: str, elapsed_ms: float) -> None:
        self.ms[name] = self.ms.get(name, 0.0) + elapsed_ms
        self.counts[name] = self.counts.get(name, 0) + 1

    def get(self, name: str) -> float:
        return round(self.ms.get(name, 0.0), 1)

    def count(self, name: str) -> int:
        return self.counts.get(name, 0)

    @property
    def total_ms(self) -> float:
        """Wall time since the recording opened."""
        return round((time.perf_counter() - self.started) * 1000, 1)

    @property
    def ocr_ms(self) -> float:
        return round(sum(self.ms.get(name, 0.0) for name in OCR_PHASES), 1)

    @property
    def ocr_passes(self) -> int:
        return sum(self.counts.get(name, 0) for name in OCR_PHASES)

    @property
    def accounted_ms(self) -> float:
        """Everything that landed in a named phase."""
        return round(sum(self.ms.get(name, 0.0) for name in PHASES), 1)


_CURRENT: ContextVar[Recording | None] = ContextVar("ttb_timing", default=None)


@contextmanager
def recording() -> Iterator[Recording]:
    """Open a recording for one request, or one batch row."""
    current = Recording()
    token = _CURRENT.set(current)
    try:
        yield current
    finally:
        _CURRENT.reset(token)


@contextmanager
def phase(name: str) -> Iterator[None]:
    """Attribute the wall time of this block to one phase.

    A no-op outside a recording, which is what keeps every unit test and
    ``scripts/measure.py`` working without opening one.
    """
    current = _CURRENT.get()
    if current is None:
        yield
        return
    started = time.perf_counter()
    try:
        yield
    finally:
        current.add(name, (time.perf_counter() - started) * 1000)


def current() -> Recording | None:
    """The recording this request is using, or None outside one."""
    return _CURRENT.get()
