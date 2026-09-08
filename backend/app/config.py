"""Runtime configuration, sourced entirely from environment variables.

No secrets are stored in the repository. See .env.example for the shape of the
environment and docs/05_ARCHITECTURE.md for how configuration is injected.

Governing requirements: NFR-11 (configuration through environment variables),
NFR-3 (no outbound calls on the default path), NFR-7 (input validation),
FR-3 and FR-7 (the thresholds and the ABV tolerance the comparison rules read).
"""

from __future__ import annotations

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Defaults are chosen so that a fresh checkout runs with no network egress.
    There is no setting that opens one: the vision-model fallback ADR 0003
    describes was designed and never built, and the three settings that once
    promised it were removed in v1.2.1 rather than left to imply otherwise.
    """

    model_config = SettingsConfigDict(env_prefix="TTB_", env_file=None, extra="ignore")

    app_name: str = "TTB Label Verifier"
    environment: str = "local"
    log_level: str = "INFO"

    # Upload guards. Enforced before any image is decoded.
    max_upload_bytes: int = 10 * 1024 * 1024
    max_batch_files: int = 300

    # How many photographs of one label the single-label path accepts
    # (ADR 0007). Three because a label wraps a round bottle and no single
    # photograph shows all of it flat: front, back and the seam between them is
    # the most a submission needs, and no source asks for more. The batch path
    # stays one photograph per row.
    max_label_photos: int = 3
    allowed_mime_types: tuple[str, ...] = ("image/jpeg", "image/png", "image/webp", "image/tiff")

    # How many pages of an uploaded COLA document are read (ADR 0008, FR-11).
    # The application side of TTB F 5100.31 is page 1; the rest of the file is
    # instructions and the allowable-revisions table, which carry no applicant
    # values. A Public COLA Registry printout runs to one or two. Three is one
    # more than either needs, and it bounds what a 400-page PDF can cost when
    # the OCR fallback runs: that path reads each page the way it reads a label
    # photograph, so the page count is a latency limit as much as a parsing one.
    max_document_pages: int = 3

    # The embedded label artwork inside a COLA document (ADR 0010, FR-11).
    #
    # An applicant affixes the label artwork to the application, so a filed PDF
    # carries pictures of the labels alongside the typed items. Three of the
    # five values this tool compares are not items on the form at all (A-17),
    # and on the author's own document they were sitting in those pictures. Each
    # embedded raster image at or above the floor below is read through the same
    # OCR pipeline label artwork goes through.
    #
    # **The floor is an area, and it is the signature discriminator.** A filed
    # TTB F 5100.31 carries the applicant's handwritten signature as an embedded
    # picture, and nothing read out of a signature may fill a compliance field.
    # What separates it from a label panel, on the two real filings the author
    # has measured, is absolute area and nothing else. The signature on the
    # author's own filing is 687 by 195, which is 133,965 pixels, and this floor
    # excludes it. The smallest label panel on the second filing, a bourbon
    # measured on 2026-09-03, is a 187 by 1697 side band, which is 317,339
    # pixels, and this floor admits it. 250,000 sits between the two with a
    # margin on each side. A 772 by 194 picture on the same filing, 149,768
    # pixels, is excluded; it is small enough to be a neck band or a strip, and
    # a rejection is reported with its dimensions and the reason rather than
    # being silent, so an agent can see that it happened.
    #
    # **There is no shape rule any more, and the second filing is why.** Until
    # v1.5.0 two more tests had to be met: a shortest edge of at least 400
    # pixels, and a long-to-short edge ratio no greater than 3.0, chosen so that
    # a signature scanned at a higher resolution would still be excluded by its
    # shape. Both were set from one example document whose artwork is one flat
    # 1750 by 1150 sheet. The bourbon filing carries its labels as separate
    # panels at 1350 by 300, 1103 by 340, 1050 by 309 and 187 by 1697: ratios
    # of 4.50, 3.24, 3.40 and 9.07, short edges of 300, 340, 309 and 187. Every
    # one of them failed both shape tests, and five of that document's six
    # pictures were discarded before anything was read. A wrap-around spirits
    # label at four and a half to one is ordinary. No ratio ceiling and no edge
    # floor separates those panels from a signature strip at 687 by 195 (a
    # ratio of 3.52, a short edge of 195), so neither test can be set to a
    # value that admits real panels and excludes it; the area floor does both.
    # ADR 0010 as amended records the measurement.
    #
    # What the area floor gives up: a signature scanned large enough to clear
    # 250,000 pixels is read. On the synthetic strip in
    # tests/test_embedded_artwork.py that read yields a three-letter misread at
    # a mean word confidence of 34 and no label value, and every value taken
    # off the artwork is taken from the panel that read it most confidently,
    # so it fills nothing. It is reported as a panel that was read, with its
    # size and its confidence, where an agent can see it.
    #
    # A setting, because the floor is a judgement about what a filing looks
    # like, now made against two filings rather than one (NFR-11, OQ-24).
    min_artwork_pixels: int = 250_000

    # The ceiling on how many surviving embedded images are read on one
    # document. It is a ceiling on the worst case, and nothing else: it no
    # longer decides whether a value is found.
    #
    # Panels are read largest first, and reading stops as soon as the panels
    # read so far carry all five values the check needs (the declared brand and
    # class or type found by the check's own search, the alcohol content and
    # the net contents by pattern, the government warning by its prefix). A
    # one-sheet filing therefore costs one read whatever this number is, and a
    # filing whose values are spread across panels costs as many reads as it
    # takes to find them, and no more. The only document that reads this many
    # is one whose values genuinely are not all present, and that is the case
    # where the sweep is doing real work: the response reports each panel as
    # read, with its confidence, so an absent value can be traced to the
    # pictures that were looked at (docs/09 section 9, ADR 0010 as amended).
    #
    # Eight, because the bourbon filing measured on 2026-09-03 carries five
    # pictures above the floor and the setting used to be four, which left the
    # fifth, a 187 by 1697 side strip, listed as not read and never looked at.
    # The two smaller panels it did read came back at 86.8 and 89.9 against
    # the 45.3 of the largest, so neither size nor shape says which panel
    # carries a value, and a ceiling that sits inside the count a real filing
    # carries is a ceiling that decides correctness. Twice the most any
    # measured filing embeds keeps it out of that position; an operator with
    # slower hardware can lower it, and the panels it cuts are listed as
    # not_read rather than dropped.
    max_artwork_images: int = 8

    # The ceiling on how many Tesseract invocations reading one document may
    # cost, its rendered pages and its embedded pictures together (NFR-1).
    #
    # **Why a second ceiling, when the count above already bounds the
    # pictures.** A count of pictures bounds nothing about what each one costs.
    # One picture is one to eight engine invocations: the orientation call, up
    # to four more where the orientation check runs and has to be repeated at
    # full resolution, and one per arm compared. The bourbon filing in
    # samples/real/, measured 2026-09-08 on a session container, cost 19 reads
    # over its five panels, 3 to 5 each, for 6.7 seconds of artwork OCR; on the
    # deployed v1.5.0 build the same document measured 8064 ms end to end, of
    # which 7679 ms was artwork OCR. NFR-1 is about five seconds. A document
    # that carried the eight pictures the count admits, each costing what the
    # worst of these five cost, would run to 40 reads and well past fifteen
    # seconds with nothing stopping it. This is the stop.
    #
    # **Reads, not milliseconds, and the choice is deliberate.** A budget in
    # milliseconds would make NFR-1 true by construction and it would make the
    # answer depend on the host: the same filing would be read in full on a
    # fast task and cut short on a slow one, or on the same task while a batch
    # is saturating its one vCPU, and no test could pin which pictures get
    # read. A budget in reads gives the same document the same answer on every
    # machine, is asserted exactly in tests, and only approximates the time: a
    # read measured between 117 ms (a 187 by 1697 strip) and 1485 ms (a 1750
    # by 1150 sheet at full resolution) on the same container, so the bound
    # this puts on the clock is loose by that ratio. The alternative is
    # recorded in ADR 0023 with what would change the choice.
    #
    # **Twenty-four**, which is the picture count above times the least a
    # picture costs when its first read does not settle it: the orientation
    # call, the preprocessed arm and the plain arm. It admits both real filings
    # in full, the bourbon's 19 with one worst-case panel of margin, and cuts
    # the runaway case from 40 to 24. At the bourbon's measured 404 ms per
    # read that is about ten seconds of OCR, which is over NFR-1 and is said
    # so: this ceiling does not make the bourbon meet the target, it stops a
    # document that carries more than the bourbon from running away. An
    # operator can lower it; the budget is checked before each picture and each
    # page, never in the middle of one, and what it cuts is listed as
    # `not_reached` in the response rather than dropped.
    max_document_reads: int = 24

    # Matching thresholds. See docs/adr/0004-fuzzy-matching-with-review-band.md.
    match_threshold: int = 95
    review_threshold: int = 80

    # How many single-character edits between the government warning as printed
    # and 27 CFR 16.21 are treated as a near miss rather than as a mismatch
    # (FR-5, ADR 0012). A near miss is routed to human review with the exact
    # character-level difference shown; it is never passed.
    #
    # Two, and the reasoning is in ADR 0012. The short version: the author's own
    # COLA artwork OCRs the statement with exactly one character wrong, so one
    # is the observed case and two is one character of headroom for the double
    # substitutions OCR also produces. Neither outcome passes, so the cost of
    # this number being slightly wrong is which sentence an agent reads, not
    # whether a defective label ships. Raising it much further would start to
    # admit substituted short words, which is where the wording of the sentence
    # begins to change rather than its rendering.
    warning_near_miss_edits: int = 2

    # Below this mean word confidence, a line of the government warning that
    # differs from 27 CFR 16.21 is taken to have been read badly rather than
    # printed wrongly (FR-5, ADR 0022). Where every differing line is below it
    # the row reports the statement as present and not certified, a failing
    # outcome that asks a person to look; where any differing line is at or
    # above it the difference is the label's and the row is a mismatch.
    #
    # Eighty, from one measurement: on the real filing whose warning panel is
    # overprinted with registration marks, the lines that read correctly read
    # at 91 to 96 and the two damaged lines at 64 and 69, and on the twelve
    # synthetic labels a compliant statement reads above 90 throughout. An
    # altered word set in clean type reads in the nineties, so it stays a
    # mismatch. Zero means no reading happened and is never below the floor.
    warning_legible_confidence: float = 80.0

    # Allowed difference between the label ABV and the application ABV, in
    # percentage points. 0.0 is a compliance position rather than a tuning
    # starting point: the regulatory tolerances in 27 CFR 5.65, 4.36 and 7.65
    # govern actual against labeled content, and this tool compares two values
    # the applicant declared. See assumption A-12 in docs/ASSUMPTIONS.md.
    abv_tolerance: float = 0.0

    # Image preprocessing. The long edge the image is scaled to before OCR.
    # See docs/07_TEST_STRATEGY.md section 4 for the latency budget this feeds.
    ocr_long_edge_px: int = 1600

    # Turn a sideways photograph upright before reading it, using Tesseract's
    # orientation and script detection. On by default because the first real
    # photograph submitted to the deployed prototype was sideways and the engine
    # found none of its five fields.
    #
    # It is a setting rather than a constant because it is not free: the OSD
    # pass costs roughly as much again as the read it precedes, which matters
    # most on the batch path where that cost is paid once per image. The
    # measured figures are in docs/07_TEST_STRATEGY.md section 4.
    correct_orientation: bool = True

    # Batch execution. See docs/adr/0006-batch-execution-model.md.
    #
    # 0 means "derive it", because both values follow from figures already set
    # rather than from a number invented here. A derived default is visible in
    # the response and overridable by environment (NFR-11); a hardcoded one
    # would look like a measurement.
    batch_workers: int = 0
    max_batch_bytes: int = 0

    @property
    def effective_batch_workers(self) -> int:
        """How many images are decoded and read at once.

        ADR 0006 bounds concurrency by CPU rather than by network wait, because
        OCR runs in-process and is CPU bound (ADR 0003). The bound exists so
        that 300 simultaneous Tesseract invocations do not exhaust memory, not
        to hit a throughput figure: no source states a batch latency target
        (OQ-6).

        ``sched_getaffinity`` reports the cores this process may actually use,
        which is what a container CPU limit constrains; ``os.cpu_count``
        reports the host's. On a task pinned to a subset of the host's cores
        the two differ, and the smaller is the honest one. It is Linux only, so
        ``os.cpu_count`` is the fallback, and the floor of 1 keeps a
        single-core runner making progress. ``os.process_cpu_count`` would say
        this in one call but arrived in Python 3.13, and this project targets
        3.11.
        """
        if self.batch_workers > 0:
            return self.batch_workers
        if hasattr(os, "sched_getaffinity"):
            available = len(os.sched_getaffinity(0))
        else:
            available = os.cpu_count() or 1
        return max(1, available)

    @property
    def allowed_document_mime_types(self) -> tuple[str, ...]:
        """What an uploaded COLA document may be (FR-11, NFR-7).

        A PDF is what COLAs Online and the Public COLA Registry produce. The
        image types are the ones already accepted for label artwork, because a
        scan or a phone photograph of a printed form is the other way the
        document reaches an agent, and there is no reason for the two lists to
        drift apart.
        """
        return ("application/pdf", *self.allowed_mime_types)

    @property
    def effective_max_verify_bytes(self) -> int:
        """The largest single-label request body accepted, in bytes.

        ``(max_label_photos + 1) * max_upload_bytes``, for the same reason the
        batch envelope is derived rather than set: that product is the largest
        submission the stated limits already permit, and a smaller figure here
        would be a further limit no source asks for. The plus one is the
        optional COLA document (FR-11, ADR 0008), which is an upload in its own
        right and is bounded by the same per-file limit. Without it a submission
        of three photographs plus the application would be refused for being one
        file larger than the photographs alone.

        Each file is still checked exactly against ``max_upload_bytes`` after
        parsing, so this loosens only what the Content-Length guard rejects
        before reading, not what is accepted.
        """
        return (self.max_label_photos + 1) * self.max_upload_bytes

    @property
    def effective_max_batch_bytes(self) -> int:
        """The largest batch envelope accepted, in bytes.

        Derived as ``2 * max_batch_files * max_upload_bytes`` rather than set to
        a figure of its own, because that product is the largest batch the
        stated limits already permit, and inventing a smaller number here would
        impose a further limit no source asks for. The factor of two is
        ADR 0009: a batch carries one label image and one COLA document per
        label, and each of the two is an upload bounded by
        ``max_upload_bytes``. Before ADR 0009 the application side of a whole
        batch was one CSV of a few kilobytes, and the factor was one.

        Read the arithmetic before deploying: at the defaults this is 600 files
        times 10 MB, about 6 GiB, and FastAPI has the whole envelope parsed
        before the route runs. That is a task sizing input, not a memory
        guarantee, and it is twice what it was. It interacts with OQ-13 item 6
        and is recorded there.
        """
        if self.max_batch_bytes > 0:
            return self.max_batch_bytes
        return 2 * self.max_batch_files * self.max_upload_bytes


settings = Settings()
