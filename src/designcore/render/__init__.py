"""Rendering: the step that proves a diagram exists as a picture."""

from __future__ import annotations


class BackendMissing(RuntimeError):
    """A required external renderer is not installed."""


class RenderError(RuntimeError):
    """The renderer ran and refused the input."""
