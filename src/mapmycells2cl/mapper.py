"""CellTypeMapper — fast lookup from ABA taxonomy ID to CL/PCL terms.

Loads a pre-built mapping JSON (produced by :mod:`mapmycells2cl.parser`)
and provides :meth:`CellTypeMapper.lookup` and
:meth:`CellTypeMapper.lookup_many`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Default bundled mapping path (installed alongside the package)
_DEFAULT_MAPPING = Path(__file__).parent / "data" / "mapping.json"


@dataclass(frozen=True)
class BroadMatch:
    """A single broad CL match for a PCL exact-match term."""

    id: str
    """CL CURIE, e.g. ``CL:4300353``."""

    label: str
    """Human-readable cell type name."""

    via: list[str] = field(default_factory=list)
    """Intermediate PCL / ABA IDs traversed to reach this CL term."""


@dataclass(frozen=True)
class MatchResult:
    """Result of a single ABA taxonomy ID lookup."""

    aba_id: str
    """The queried ABA taxonomy short ID."""

    exact_id: str
    """CL or PCL CURIE for the exact equivalentClass match."""

    exact_label: str
    """Human-readable label for the exact match."""

    ontology: str
    """``"CL"`` or ``"PCL"``."""

    broad: list[BroadMatch]
    """CL broad matches (empty when exact match is already CL)."""

    best_cl_id: str
    """Most specific CL CURIE (IC-ranked). Equal to ``exact_id`` when exact is CL;
    highest-IC broad match when exact is PCL. Empty string without IC data."""

    best_cl_label: str
    """Label for ``best_cl_id``."""

    best_cl_ic: float
    """Information Content score for ``best_cl_id`` (0.0 when IC data is absent)."""

    mapping_version: str
    """Version of the mapping data used."""

    found: bool = True
    """``False`` when the ABA ID had no entry in the mapping."""


class CellTypeMapper:
    """Map MapMyCells ABA taxonomy IDs to Cell Ontology terms.

    Args:
        mapping_path: Path to a versioned mapping JSON produced by
            :func:`mapmycells2cl.parser.build_mapping`.  Defaults to
            the mapping bundled with the package.

    Example:
        .. code-block:: python

            mapper = CellTypeMapper()
            result = mapper.lookup("CS20230722_SUBC_313")
            print(result.best_cl_id)   # CL:4300353
    """

    def __init__(self, mapping_path: Path | None = None) -> None:
        path = mapping_path or _DEFAULT_MAPPING
        if not path.exists():
            raise FileNotFoundError(
                f"Mapping file not found: {path}\n"
                "Run `mapmycells2cl update-mappings` to generate it."
            )
        raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        self._version: str = raw.get("version", "unknown")
        self._exact: dict[str, dict[str, str]] = raw.get("exact", {})
        self._broad: dict[str, list[dict[str, Any]]] = raw.get("broad", {})
        self._best_cl: dict[str, dict[str, Any]] = raw.get("best_cl", {})

        if not self._best_cl:
            import warnings

            warnings.warn(
                "Mapping file has no 'best_cl' data. "
                "Regenerate with `mapmycells2cl update-mappings --cl-owl cl.owl` "
                "to enable cell_type_ontology_term_id output.",
                stacklevel=2,
            )

    @property
    def mapping_version(self) -> str:
        """Version string from the mapping file (e.g. ``"2026-03-26"``)."""
        return self._version

    @property
    def has_ic(self) -> bool:
        """True when the mapping includes IC-ranked best_cl data."""
        return bool(self._best_cl)

    def lookup(self, aba_id: str) -> MatchResult:
        """Look up a single ABA taxonomy ID.

        Args:
            aba_id: Short ABA taxonomy ID, e.g. ``CS20230722_SUBC_313``.

        Returns:
            :class:`MatchResult` — ``found=False`` when ID is not in mapping.
        """
        exact_entry = self._exact.get(aba_id)
        if exact_entry is None:
            return MatchResult(
                aba_id=aba_id,
                exact_id="",
                exact_label="",
                ontology="",
                broad=[],
                best_cl_id="",
                best_cl_label="",
                best_cl_ic=0.0,
                mapping_version=self._version,
                found=False,
            )

        broad_raw = self._broad.get(aba_id, [])
        broad = [
            BroadMatch(
                id=str(b["id"]),
                label=str(b.get("label", "")),
                via=[str(v) for v in (b.get("via") or [])],
            )
            for b in broad_raw
        ]

        best = self._best_cl.get(aba_id, {})

        return MatchResult(
            aba_id=aba_id,
            exact_id=str(exact_entry["id"]),
            exact_label=str(exact_entry.get("label", "")),
            ontology=str(exact_entry.get("ontology", "")),
            broad=broad,
            best_cl_id=str(best.get("id", "")),
            best_cl_label=str(best.get("label", "")),
            best_cl_ic=float(best.get("ic", 0.0)),
            mapping_version=self._version,
        )

    def lookup_many(self, aba_ids: list[str]) -> list[MatchResult]:
        """Look up multiple ABA taxonomy IDs.

        Args:
            aba_ids: List of short ABA taxonomy IDs.

        Returns:
            List of :class:`MatchResult` in the same order as *aba_ids*.
        """
        return [self.lookup(aid) for aid in aba_ids]

    @classmethod
    def from_mapping_dict(cls, mapping: dict[str, Any]) -> CellTypeMapper:
        """Create a mapper directly from an in-memory mapping dict.

        Useful for testing without writing to disk.

        Args:
            mapping: Dict as returned by :func:`mapmycells2cl.parser.build_mapping`.

        Returns:
            :class:`CellTypeMapper` instance.
        """
        import tempfile
        import warnings

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tf:
            json.dump(mapping, tf)
            tmp_path = Path(tf.name)

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                instance = cls(mapping_path=tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        return instance
