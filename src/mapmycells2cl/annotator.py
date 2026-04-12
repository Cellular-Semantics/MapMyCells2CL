"""Annotate MapMyCells CSV/JSON output with CL terms.

Reads MapMyCells output files and adds CL annotation columns/fields for
each taxonomy level present in the data.

**Field naming schema** (CAP/HCA double-dash convention for multi-level):

For each taxonomy level (class, subclass, supertype, cluster) the following
columns are written to the output, prefixed with ``{level}--``:

- ``{level}--cell_type_ontology_term_id`` — Most specific CL CURIE (IC-ranked best). Always.
- ``{level}--cell_type`` — Label for the above. Always.
- ``{level}--cell_type_pcl_ontology_term_id`` — PCL exact match CURIE. PCL exact only.
- ``{level}--cell_type_pcl`` — PCL exact label. PCL exact only.
- ``{level}--cell_type_cl_broad_ontology_term_ids`` — All CL broad CURIEs, ``|``-joined.
  PCL exact only.

For JSON output the same keys (without prefix) are written inside each
level's assignment dict; the prefix is the dict key itself.

For h5ad output (Phase 5) the unprefixed CxG pair
``cell_type_ontology_term_id`` / ``cell_type`` is written to ``obs`` using
the cluster-level best CL, alongside all prefixed per-level columns.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from mapmycells2cl.mapper import CellTypeMapper, MatchResult

# Taxonomy levels produced by MapMyCells (hierarchy order, coarsest first)
TAXONOMY_LEVELS = ("class", "subclass", "supertype", "cluster")

# CAP/HCA double-dash separator
_SEP = "--"


def _level_from_columns(columns: list[str]) -> list[str]:
    """Detect taxonomy levels present in CSV columns (via ``{level}_label``).

    Args:
        columns: List of CSV column headers.

    Returns:
        Ordered list of detected level names (e.g. ``["class", "subclass"]``).
    """
    found = []
    for col in columns:
        if col.endswith("_label"):
            level = col[: -len("_label")]
            if level not in found:
                found.append(level)
    return found


def _empty_result(mapper: CellTypeMapper) -> MatchResult:
    """Return a not-found MatchResult for cells absent from the mmc output."""
    return MatchResult(
        aba_id="",
        exact_id="",
        exact_label="",
        ontology="",
        broad=[],
        best_cl_id="",
        best_cl_label="",
        best_cl_ic=0.0,
        mapping_version=mapper.mapping_version,
        found=False,
    )


def _cl_columns_for_level(level: str, result: MatchResult) -> dict[str, str]:
    """Build the annotation column dict for one level and one MatchResult.

    Args:
        level: Taxonomy level name, e.g. ``"cluster"``.
        result: Lookup result for this cell at this level.

    Returns:
        Dict of ``{column_name: value}`` ready to merge into the output row.
    """
    prefix = level + _SEP
    cols: dict[str, str] = {
        f"{prefix}cell_type_ontology_term_id": result.best_cl_id if result.found else "",
        f"{prefix}cell_type": result.best_cl_label if result.found else "",
    }
    # PCL-specific fields — only when exact match is PCL
    if result.found and result.ontology == "PCL":
        cols[f"{prefix}cell_type_pcl_ontology_term_id"] = result.exact_id
        cols[f"{prefix}cell_type_pcl"] = result.exact_label
        cols[f"{prefix}cell_type_cl_broad_ontology_term_ids"] = "|".join(b.id for b in result.broad)
    return cols


def _cl_json_for_level(result: MatchResult) -> dict[str, Any]:
    """Build the annotation dict for one level in JSON output.

    Args:
        result: Lookup result for this cell at this level.

    Returns:
        Dict of annotation keys to merge into the level's assignment dict.
    """
    out: dict[str, Any] = {
        "cell_type_ontology_term_id": result.best_cl_id if result.found else "",
        "cell_type": result.best_cl_label if result.found else "",
    }
    if result.found and result.ontology == "PCL":
        out["cell_type_pcl_ontology_term_id"] = result.exact_id
        out["cell_type_pcl"] = result.exact_label
        out["cell_type_cl_broad_ontology_term_ids"] = [b.id for b in result.broad]
    return out


def annotate_csv(
    input_path: Path,
    output_path: Path,
    mapper: CellTypeMapper,
) -> None:
    """Annotate a MapMyCells CSV file with CL terms.

    Args:
        input_path: Path to input MapMyCells CSV (``#`` comment lines allowed).
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

    # Annotate all rows first so we know which PCL-conditional columns appear
    annotated: list[dict[str, str]] = []
    pcl_levels: set[str] = set()
    for row in rows:
        extra: dict[str, str] = {}
        for level in levels:
            aba_id = row.get(f"{level}_label", "").strip()
            result = mapper.lookup(aba_id) if aba_id else _empty_result(mapper)
            extra.update(_cl_columns_for_level(level, result))
            if result.found and result.ontology == "PCL":
                pcl_levels.add(level)
        annotated.append({**row, **extra})

    # Build ordered output fieldnames: insert CL columns after each level's label
    out_fields: list[str] = []
    emitted: set[str] = set()
    for col in fieldnames:
        out_fields.append(col)
        for level in levels:
            if col != f"{level}_label" or level in emitted:
                continue
            emitted.add(level)
            prefix = level + _SEP
            out_fields.append(f"{prefix}cell_type_ontology_term_id")
            out_fields.append(f"{prefix}cell_type")
            if level in pcl_levels:
                out_fields.append(f"{prefix}cell_type_pcl_ontology_term_id")
                out_fields.append(f"{prefix}cell_type_pcl")
                out_fields.append(f"{prefix}cell_type_cl_broad_ontology_term_ids")

    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(annotated)


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
            level_data.update(_cl_json_for_level(result))

    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def annotate_h5ad(
    mmc_csv_path: Path,
    h5ad_in_path: Path,
    h5ad_out_path: Path,
    mapper: CellTypeMapper,
    cxg_level: str = "cluster",
) -> None:
    """Annotate an h5ad file with CL terms from MapMyCells CSV output.

    Reads ABA taxonomy IDs from the MapMyCells CSV, looks them up, and writes
    CL annotation columns to ``adata.obs``.

    Two sets of columns are added:

    1. **Unprefixed CxG pair** (required by CELLxGENE schema) sourced from
       *cxg_level* (default ``"cluster"``):
       ``cell_type_ontology_term_id``, ``cell_type``.

    2. **Prefixed per-level columns** following the CAP/HCA double-dash
       convention (see module docstring).

    Args:
        mmc_csv_path: Path to MapMyCells CSV output (``#`` comment lines ok).
        h5ad_in_path: Path to input h5ad file.
        h5ad_out_path: Destination path for annotated h5ad.
        mapper: Configured :class:`~mapmycells2cl.mapper.CellTypeMapper`.
        cxg_level: Taxonomy level used for the unprefixed CxG columns.
    """
    import anndata as ad
    import pandas as pd

    # Parse mmc CSV → {cell_id: {level: aba_id}}
    with open(mmc_csv_path, newline="", encoding="utf-8") as fh:
        lines = [ln for ln in fh if not ln.startswith("#")]
    reader = csv.DictReader(lines)
    if reader.fieldnames is None:
        raise ValueError(f"CSV has no headers: {mmc_csv_path}")
    fieldnames = list(reader.fieldnames)
    mmc_rows: dict[str, dict[str, str]] = {row["cell_id"]: dict(row) for row in reader}

    levels = _level_from_columns(fieldnames)

    # First pass: look up all cells, detect which levels have PCL matches
    cell_results: dict[str, dict[str, MatchResult]] = {}
    pcl_levels: set[str] = set()
    for cell_id, row in mmc_rows.items():
        level_map: dict[str, MatchResult] = {}
        for level in levels:
            aba_id = row.get(f"{level}_label", "").strip()
            result = mapper.lookup(aba_id) if aba_id else _empty_result(mapper)
            level_map[level] = result
            if result.found and result.ontology == "PCL":
                pcl_levels.add(level)
        cell_results[cell_id] = level_map

    adata = ad.read_h5ad(h5ad_in_path)

    # Build column lists in obs-index order
    new_cols: dict[str, list[str]] = {
        "cell_type_ontology_term_id": [],
        "cell_type": [],
    }
    for level in levels:
        p = level + _SEP
        new_cols[f"{p}cell_type_ontology_term_id"] = []
        new_cols[f"{p}cell_type"] = []
        if level in pcl_levels:
            new_cols[f"{p}cell_type_pcl_ontology_term_id"] = []
            new_cols[f"{p}cell_type_pcl"] = []
            new_cols[f"{p}cell_type_cl_broad_ontology_term_ids"] = []

    for cell_id in adata.obs.index:
        lvl_map = cell_results.get(str(cell_id))
        if lvl_map is None:
            for lst in new_cols.values():
                lst.append("")
            continue

        cxg = lvl_map.get(cxg_level, _empty_result(mapper))
        new_cols["cell_type_ontology_term_id"].append(cxg.best_cl_id if cxg.found else "")
        new_cols["cell_type"].append(cxg.best_cl_label if cxg.found else "")

        for level in levels:
            p = level + _SEP
            r = lvl_map[level]
            new_cols[f"{p}cell_type_ontology_term_id"].append(r.best_cl_id if r.found else "")
            new_cols[f"{p}cell_type"].append(r.best_cl_label if r.found else "")
            if level in pcl_levels:
                is_pcl = r.found and r.ontology == "PCL"
                new_cols[f"{p}cell_type_pcl_ontology_term_id"].append(r.exact_id if is_pcl else "")
                new_cols[f"{p}cell_type_pcl"].append(r.exact_label if is_pcl else "")
                new_cols[f"{p}cell_type_cl_broad_ontology_term_ids"].append(
                    "|".join(b.id for b in r.broad) if is_pcl else ""
                )

    for col, values in new_cols.items():
        adata.obs[col] = pd.Categorical(values)

    adata.write_h5ad(h5ad_out_path)
