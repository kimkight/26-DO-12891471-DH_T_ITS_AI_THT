"""The version is declared once, and the documents count what is there.

Two things the v1.2.0 code review found stale, and both were stale because
nothing checked them (docs/CODE_REVIEW_2026-09.md, findings 3 and 15).

The version was a literal in three files and the build tagged v1.2.0 reported
1.1.0. ``app.__version__`` now reads the installed distribution, whose version
is the one in ``backend/pyproject.toml``; ``frontend/package.json`` still
carries its own copy, and this is what keeps the two equal.

The traceability matrix's coverage summary counted 22 requirements and 10 ADRs
against 26 and 18 in the tree. The summary says its rows "can be checked rather
than taken"; these tests do the checking.

These read the repository's own files, so they run from a checkout and not from
the container image, which carries none of them. Every path is resolved from
this file rather than from the working directory.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from app import __version__

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs"


def _matrix_summary() -> dict[str, str]:
    """The Measure and Count columns of section 3 of the traceability matrix."""
    text = (DOCS / "TRACEABILITY_MATRIX.md").read_text()
    section = text.split("## 3. Coverage summary", 1)[1].split("\n## ", 1)[0]
    rows = re.findall(r"^\| ([^|]+?) \| ([^|]+?) \|$", section, flags=re.MULTILINE)
    return {measure.strip(): count.strip() for measure, count in rows}


def _heading_count(document: str, pattern: str) -> int:
    return len(re.findall(pattern, (DOCS / document).read_text(), flags=re.MULTILINE))


class TestTheVersionIsDeclaredOnce:
    def test_the_package_reports_the_version_pyproject_declares(self):
        declared = tomllib.loads((REPO_ROOT / "backend" / "pyproject.toml").read_text())
        assert __version__ == declared["project"]["version"]

    def test_the_frontend_carries_the_same_version(self):
        package = json.loads((REPO_ROOT / "frontend" / "package.json").read_text())
        assert package["version"] == __version__

    def test_the_lock_file_agrees_with_the_manifest(self):
        lock = json.loads((REPO_ROOT / "frontend" / "package-lock.json").read_text())
        assert lock["version"] == __version__
        assert lock["packages"][""]["version"] == __version__


class TestTheCoverageSummaryCountsWhatIsThere:
    def test_requirements_defined(self):
        functional = _heading_count("03_REQUIREMENTS.md", r"^### FR-\d+ ")
        non_functional = _heading_count("03_REQUIREMENTS.md", r"^### NFR-\d+ ")
        total = functional + non_functional
        expected = f"{total} ({functional} functional, {non_functional} non-functional)"
        assert _matrix_summary()["Requirements defined"] == expected

    def test_user_stories(self):
        stories = _heading_count("04_USER_STORIES.md", r"^### US-\d+")
        summary = _matrix_summary()
        assert summary["User stories"] == str(stories)
        assert summary["Stories with acceptance criteria"] == f"{stories} of {stories}"

    def test_adrs(self):
        adrs = [
            path
            for path in (DOCS / "adr").glob("[0-9][0-9][0-9][0-9]-*.md")
            if not path.name.startswith("0000-")
        ]
        assert _matrix_summary()["ADRs"] == str(len(adrs))

    def test_every_requirement_has_a_row_in_section_two(self):
        text = (DOCS / "TRACEABILITY_MATRIX.md").read_text()
        section = text.split("## 2. Requirement coverage", 1)[1].split("\n## 3.", 1)[0]
        in_table = set(re.findall(r"^\| ((?:N?FR)-\d+) ", section, flags=re.MULTILINE))
        requirements = (DOCS / "03_REQUIREMENTS.md").read_text()
        defined = set(re.findall(r"^### ((?:N?FR)-\d+) ", requirements, flags=re.MULTILINE))
        assert defined <= in_table, sorted(defined - in_table)
