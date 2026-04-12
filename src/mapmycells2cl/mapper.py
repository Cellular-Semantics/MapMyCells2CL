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
    """A single broad CL match for a PCL exact-match term.

    Attributes:
        id: CL CURIE, e.g. ``CL:4300353``.
        label: Human-readable cell type name.
        via: Intermediate PCL / ABA IDs traversed to reach this CL term.
    """

    id: str
    label: str
    via: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MatchResult:
    """Result of a single ABA taxonomy ID lookup.

    Attributes:
        aba_id: The queried ABA taxonomy short ID.
        exact_id: CL or PCL CURIE for the exact equivalentClass match.
        exact_label: Human-readable label for the exact match.
        ontology: ``"CL"`` or ``"PCL"``.
        broad: CL broad matches (empty when exact match is already CL).
        mapping_version: Version of the mapping data used.
        found: ``False`` when the ABA ID had no entry in the mapping.
    """

    aba_id: str
    exact_id: str
    exact_label: str
    ontology: str
    broad: list[BroadMatch]
    mapping_version: str
    found: bool = True


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
            print(result.exact_id)   # CL:4300353
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
        self._broad: dict[str, list[dict[str, str | list[str]]]] = raw.get("broad", {})

    @property
    def mapping_version(self) -> str:
        """Version string from the mapping file (e.g. ``"2026-03-26"``)."""
        return self._version

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

        return MatchResult(
            aba_id=aba_id,
            exact_id=str(exact_entry["id"]),
            exact_label=str(exact_entry.get("label", "")),
            ontology=str(exact_entry.get("ontology", "")),
            broad=broad,
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

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tf:
            json.dump(mapping, tf)
            tmp_path = Path(tf.name)

        try:
            instance = cls(mapping_path=tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        return instance
