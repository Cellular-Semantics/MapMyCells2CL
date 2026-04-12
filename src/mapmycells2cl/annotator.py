"""Annotate MapMyCells CSV/JSON output with CL terms.

Reads MapMyCells output files and adds CL annotation columns/fields for
each taxonomy level present in the data.

**CSV format** — expects columns like ``{level}_label`` (e.g.
``cluster_label``) containing ABA taxonomy IDs.  Adds:

- ``{level}_cl_exact`` — exact CL/PCL CURIE
- ``{level}_cl_label`` — human-readable label
- ``{level}_cl_broad`` — ``|``-joined CL broad-match CURIEs (empty if exact is CL)

**JSON format** — expects a ``results`` list where each item has per-level
``assignment`` dicts containing a ``"label"`` key with the ABA taxonomy ID.
Adds ``cl_exact``, ``cl_label``, ``cl_broad`` keys to each assignment dict.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from mapmycells2cl.mapper import CellTypeMapper

# Taxonomy levels produced by MapMyCells (in hierarchy order)
TAXONOMY_LEVELS = ("class", "subclass", "supertype", "cluster")


def _level_from_columns(columns: list[str]) -> list[str]:
    """Detect taxonomy levels present in CSV columns.

    Args:
        columns: List of CSV column headers.

    Returns:
        Ordered list of detected level names.
    """
    found = []
    for col in columns:
        if col.endswith("_label"):
            level = col[: -len("_label")]
            if level not in found:
                found.append(level)
    return found


def annotate_csv(
    input_path: Path,
    output_path: Path,
    mapper: CellTypeMapper,
) -> None:
    """Annotate a MapMyCells CSV file with CL terms.

    Args:
        input_path: Path to input MapMyCells CSV.
        output_path: Destination path for annotated CSV.
        mapper: Configured :class:`~mapmycells2cl.mapper.CellTypeMapper`.
    """
    with open(input_path, newline="", encoding="utf-8") as fh:
        # Strip MapMyCells comment lines (start with '#') before parsing
        lines = [ln for ln in fh if not ln.startswith("#")]

    reader = csv.DictReader(lines)
    if reader.fieldnames is None:
        raise ValueError(f"CSV has no headers: {input_path}")
    fieldnames = list(reader.fieldnames)
    rows = list(reader)

    levels = _level_from_columns(fieldnames)

    # Build output fieldnames: insert CL columns after each existing level block
    out_fields: list[str] = []
    emitted_cl: set[str] = set()
    for col in fieldnames:
        out_fields.append(col)
        for level in levels:
            cl_exact_col = f"{level}_cl_exact"
            if col == f"{level}_label" and cl_exact_col not in emitted_cl:
                out_fields.append(cl_exact_col)
                out_fields.append(f"{level}_cl_label")
                out_fields.append(f"{level}_cl_broad")
                emitted_cl.add(cl_exact_col)

    for row in rows:
        for level in levels:
            label_col = f"{level}_label"
            aba_id = row.get(label_col, "").strip()
            if aba_id:
                result = mapper.lookup(aba_id)
                row[f"{level}_cl_exact"] = result.exact_id if result.found else ""
                row[f"{level}_cl_label"] = result.exact_label if result.found else ""
                row[f"{level}_cl_broad"] = (
                    "|".join(b.id for b in result.broad) if result.found else ""
                )
            else:
                row[f"{level}_cl_exact"] = ""
                row[f"{level}_cl_label"] = ""
                row[f"{level}_cl_broad"] = ""

    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def annotate_csv_string(text: str, mapper: CellTypeMapper) -> str:
    """Annotate CSV from a string, return annotated CSV string.

    Convenience wrapper used in tests.

    Args:
        text: CSV content as a string.
        mapper: Configured :class:`~mapmycells2cl.mapper.CellTypeMapper`.

    Returns:
        Annotated CSV as a string.
    """
    import tempfile

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8"
    ) as inf:
        inf.write(text)
        in_path = Path(inf.name)

    out_path = in_path.with_suffix(".out.csv")
    try:
        annotate_csv(in_path, out_path, mapper)
        return out_path.read_text(encoding="utf-8")
    finally:
        in_path.unlink(missing_ok=True)
        out_path.unlink(missing_ok=True)


def annotate_json(
    input_path: Path,
    output_path: Path,
    mapper: CellTypeMapper,
) -> None:
    """Annotate a MapMyCells JSON file with CL terms.

    Expects the standard MapMyCells JSON format where the top-level key
    ``results`` is a list of per-cell dicts, each containing an
    ``assignment`` dict keyed by taxonomy level.  Each level dict must
    have a ``"label"`` key with the ABA taxonomy ID.

    Args:
        input_path: Path to input MapMyCells JSON.
        output_path: Destination path for annotated JSON.
        mapper: Configured :class:`~mapmycells2cl.mapper.CellTypeMapper`.
    """
    data: dict[str, Any] = json.loads(input_path.read_text(encoding="utf-8"))

    results: list[dict[str, Any]] = data.get("results", [])
    for cell in results:
        assignment: dict[str, Any] = cell.get("assignment", {})
        for _level, level_data in assignment.items():
            if not isinstance(level_data, dict):
                continue
            aba_id = str(level_data.get("label", "")).strip()
            if not aba_id:
                continue
            result = mapper.lookup(aba_id)
            if result.found:
                level_data["cl_exact"] = result.exact_id
                level_data["cl_label"] = result.exact_label
                level_data["cl_broad"] = [b.id for b in result.broad]
            else:
                level_data["cl_exact"] = ""
                level_data["cl_label"] = ""
                level_data["cl_broad"] = []

    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
