"""Offline-only DeckSpec foundation.

This package is deliberately not imported by mounted routes, workers, or the
historical ``full_html_deck.v1`` compiler.  It provides the disabled, local
foundation for the versioned source-package -> DeckSpec -> composition
compiler architecture.
"""

from .compiler import (
    COMPILER_VERSION,
    CompiledDeck,
    CompiledSlide,
    DeckSpecCompilationError,
    compile_deck_spec,
)
from .models import (
    DECK_SPEC_VERSION,
    SOURCE_PACKAGE_VERSION,
    DeckSpec,
    NormalizedSourcePackage,
)
from .source_package import (
    build_source_package_from_extraction_checkpoint,
    canonical_json_bytes,
    canonical_sha256,
)
from .validation import DeckSpecValidationError, validate_deck_spec

__all__ = [
    "COMPILER_VERSION",
    "DECK_SPEC_VERSION",
    "SOURCE_PACKAGE_VERSION",
    "CompiledDeck",
    "CompiledSlide",
    "DeckSpec",
    "DeckSpecCompilationError",
    "DeckSpecValidationError",
    "NormalizedSourcePackage",
    "build_source_package_from_extraction_checkpoint",
    "canonical_json_bytes",
    "canonical_sha256",
    "compile_deck_spec",
    "validate_deck_spec",
]
