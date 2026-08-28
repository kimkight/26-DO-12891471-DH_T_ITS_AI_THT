#!/usr/bin/env python3
"""Render the twelve synthetic sample labels and write the ground truth CSVs.

Run from the repository root:

    python samples/generate_samples.py

Writes ``samples/images/*.png`` (git-ignored), ``samples/expected.csv`` (ground
truth, committed), ``samples/applications/applications.csv`` (the application
side of each case, committed) and ``samples/applications/documents/*.pdf``
(git-ignored), one synthetic Public COLA Registry printout per label.

The documents are what a batch submission is made of now: label images plus COLA
documents paired by filename stem, so ``01-spirits-clean.png`` is submitted
alongside ``01-spirits-clean.pdf``
([ADR 0009](../docs/adr/0009-batch-cola-documents.md)). ``applications.csv`` is
no longer an input to any API. It stays because it is the application side of
the accuracy tier, which runs the engine in process, and because it is the file
the documents are written from.

Images are regenerated rather than committed because label artwork can carry
third-party trade dress and the assignment grants no rights to redistribute real
labels; samples/README.md records the reasoning. Regenerating from a fixed set
of specifications is what keeps the accuracy numbers reproducible without
committing binaries.

The set covers the seven cases samples/README.md lists, the three beverage
classes, and the image defects Jenny Park describes. See samples/specs.py.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from samples.formmaker import (  # noqa: E402
    ApplicationSpec,
    as_pdf_bytes,
    registry_printout_lines,
)
from samples.labelmaker import render  # noqa: E402
from samples.specs import SPECS  # noqa: E402

IMAGES_DIR = REPO_ROOT / "samples" / "images"
APPLICATIONS_DIR = REPO_ROOT / "samples" / "applications"
DOCUMENTS_DIR = APPLICATIONS_DIR / "documents"
EXPECTED_CSV = REPO_ROOT / "samples" / "expected.csv"
APPLICATIONS_CSV = APPLICATIONS_DIR / "applications.csv"

# Ground truth. The first six columns and the last are the set samples/README.md
# planned. `government_warning` is added because a boolean cannot serve as
# ground truth for FR-5: scoring a warning comparison needs the statement as
# printed, not just whether one is present.
EXPECTED_COLUMNS = [
    "image_filename",
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "government_warning_present",
    "government_warning",
    "notes",
]

# The application side of each case. Keyed on `filename`, where expected.csv
# keys on `image_filename`. This was the batch API's CSV contract under
# assumption A-14; ADR 0009 supersedes that, and the file is now the accuracy
# tier's application data and the source the sample COLA documents below are
# written from.
APPLICATION_COLUMNS = [
    "filename",
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "beverage_type",
]


def write_images() -> list[Path]:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for spec in SPECS:
        path = IMAGES_DIR / spec.filename
        render(spec).save(path, format="PNG")
        written.append(path)
    return written


def write_expected() -> None:
    with EXPECTED_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPECTED_COLUMNS)
        writer.writeheader()
        for spec in SPECS:
            writer.writerow(
                {
                    "image_filename": spec.filename,
                    "brand_name": spec.brand_name,
                    "class_type": spec.class_type,
                    "alcohol_content": spec.alcohol_content,
                    "net_contents": spec.net_contents or "",
                    "government_warning_present": "yes" if spec.warning else "no",
                    "government_warning": spec.warning or "",
                    "notes": spec.notes,
                }
            )


def write_applications() -> None:
    APPLICATIONS_DIR.mkdir(parents=True, exist_ok=True)
    with APPLICATIONS_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=APPLICATION_COLUMNS)
        writer.writeheader()
        for spec in SPECS:
            writer.writerow({"filename": spec.filename, **spec.application})


def write_documents() -> list[Path]:
    """One synthetic Registry printout per label, named to pair with its image.

    A Public COLA Registry detail page rather than a blank TTB F 5100.31,
    because the form has no item for the class or type designation, the alcohol
    content or the net contents: it carries the brand name and the ticked
    product type and nothing else this tool compares (A-17). A batch of forms
    would leave four of five fields with nothing to compare against, which would
    make the sample batch useless as a measurement and would say nothing true
    about the parser.

    Every value is invented and comes from `specs.py`. Nothing real is used, and
    the files are git-ignored for the same reason the artwork is: they are
    regenerated from a fixed specification rather than committed.
    """
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for spec in SPECS:
        application = spec.application
        document = ApplicationSpec(
            brand_name=application.get("brand_name", ""),
            class_type=application.get("class_type", ""),
            alcohol_content=application.get("alcohol_content", ""),
            net_contents=application.get("net_contents", ""),
            beverage_type=application.get("beverage_type", ""),
        )
        path = DOCUMENTS_DIR / f"{Path(spec.filename).stem}.pdf"
        path.write_bytes(as_pdf_bytes(registry_printout_lines(document)))
        written.append(path)
    return written


def main() -> int:
    images = write_images()
    write_expected()
    write_applications()
    documents = write_documents()
    print(f"Rendered {len(images)} labels into {IMAGES_DIR.relative_to(REPO_ROOT)}")
    print(f"Wrote {EXPECTED_CSV.relative_to(REPO_ROOT)}")
    print(f"Wrote {APPLICATIONS_CSV.relative_to(REPO_ROOT)}")
    print(f"Wrote {len(documents)} COLA documents into {DOCUMENTS_DIR.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
