"""TTB alcohol label verification prototype: backend application package."""

from importlib.metadata import PackageNotFoundError, version

# The version is declared once, in pyproject.toml, and read from the installed
# distribution. Until v1.2.1 it was a literal here, a second literal in
# pyproject.toml and a third in frontend/package.json, and the build tagged
# v1.2.0 shipped reporting 1.1.0 because the release skipped the bump.
# backend/tests/test_release_metadata.py asserts the three agree, and the
# deploy workflow refuses a release whose tag disagrees with this value.
try:
    __version__ = version("ttb-label-verifier-backend")
except PackageNotFoundError:  # pragma: no cover - only when the package is not installed
    __version__ = "0.0.0+uninstalled"
