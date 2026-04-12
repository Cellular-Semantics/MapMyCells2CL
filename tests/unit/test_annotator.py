"""Unit tests for mapmycells2cl.annotator."""

import json
import textwrap
from pathlib import Path

import pytest

from mapmycells2cl.annotator import annotate_csv_string, annotate_json
from mapmycells2cl.mapper import CellTypeMapper
from mapmycells2cl.parser import build_mapping_from_string


@pytest.fixture()
def mapper(minimal_owl_xml: str, minimal_cl_owl_xml: str) -> CellTypeMapper:
    """Mapper with IC data."""
    mapping = build_mapping_from_string(minimal_owl_xml, cl_owl_xml=minimal_cl_owl_xml)
    return CellTypeMapper.from_mapping_dict(mapping)


# ---------------------------------------------------------------------------
# CSV — column naming (CAP/HCA double-dash convention)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_csv_cl_exact_columns(mapper: CellTypeMapper) -> None:
    """CL exact match: only cell_type pair written, no PCL columns."""
    csv_text = textwrap.dedent("""\
        cell_id,cluster_label,cluster_name
        cell1,CS20230722_SUBC_313,Purkinje
    """)
    out = annotate_csv_string(csv_text, mapper)
    import csv as _csv
    row = next(_csv.DictReader(out.splitlines()))

    assert row["cluster--cell_type_ontology_term_id"] == "CL:4300353"
    assert row["cluster--cell_type"] == "Purkinje cell (Mmus)"
    # PCL columns must NOT be present for a CL exact match
    assert "cluster--cell_type_pcl_ontology_term_id" not in row
    assert "cluster--cell_type_pcl" not in row
    assert "cluster--cell_type_cl_broad_ontology_term_ids" not in row


@pytest.mark.unit
def test_csv_pcl_exact_has_all_columns(mapper: CellTypeMapper) -> None:
    """PCL exact match: best_cl + PCL + broad columns all written."""
    csv_text = textwrap.dedent("""\
        cell_id,cluster_label
        cell1,CS20230722_CLUS_0002
    """)
    out = annotate_csv_string(csv_text, mapper)
    import csv as _csv
    row = next(_csv.DictReader(out.splitlines()))

    assert row["cluster--cell_type_ontology_term_id"] == "CL:4300353"
    assert row["cluster--cell_type_pcl_ontology_term_id"] == "PCL:0010002"
    assert "CL:4300353" in row["cluster--cell_type_cl_broad_ontology_term_ids"]


@pytest.mark.unit
def test_csv_unknown_id_empty(mapper: CellTypeMapper) -> None:
    csv_text = textwrap.dedent("""\
        cell_id,cluster_label
        cell1,CS20230722_UNKNOWN_999
    """)
    out = annotate_csv_string(csv_text, mapper)
    import csv as _csv
    row = next(_csv.DictReader(out.splitlines()))
    assert row["cluster--cell_type_ontology_term_id"] == ""
    assert row["cluster--cell_type"] == ""


@pytest.mark.unit
def test_csv_multiple_levels(mapper: CellTypeMapper) -> None:
    """Each level gets its own prefixed columns."""
    csv_text = textwrap.dedent("""\
        cell_id,subclass_label,cluster_label
        cell1,CS20230722_SUBC_313,CS20230722_CLUS_0002
    """)
    out = annotate_csv_string(csv_text, mapper)
    import csv as _csv
    row = next(_csv.DictReader(out.splitlines()))
    assert row["subclass--cell_type_ontology_term_id"] == "CL:4300353"
    assert row["cluster--cell_type_ontology_term_id"] == "CL:4300353"
    assert row["cluster--cell_type_pcl_ontology_term_id"] == "PCL:0010002"
    # subclass is CL exact — no PCL columns for it
    assert "subclass--cell_type_pcl_ontology_term_id" not in row


@pytest.mark.unit
def test_csv_mixed_cl_and_pcl_levels(mapper: CellTypeMapper) -> None:
    """PCL columns only appear when at least one row at that level is PCL."""
    csv_text = textwrap.dedent("""\
        cell_id,subclass_label
        cell1,CS20230722_SUBC_313
        cell2,CS20230722_CLUS_0002
    """)
    out = annotate_csv_string(csv_text, mapper)
    import csv as _csv
    rows = list(_csv.DictReader(out.splitlines()))
    # CLUS_0002 is PCL so PCL columns are present for the level
    assert "subclass--cell_type_pcl_ontology_term_id" in rows[1]
    # cell1 (CL exact) has empty PCL column since the column was added for the level
    assert rows[0]["subclass--cell_type_pcl_ontology_term_id"] == ""


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_json_cl_exact(tmp_path: Path, mapper: CellTypeMapper) -> None:
    data = {"results": [{"cell_id": "c1", "assignment": {
        "cluster": {"label": "CS20230722_SUBC_313"}
    }}]}
    in_p, out_p = tmp_path / "i.json", tmp_path / "o.json"
    in_p.write_text(json.dumps(data))
    annotate_json(in_p, out_p, mapper)

    cluster = json.loads(out_p.read_text())["results"][0]["assignment"]["cluster"]
    assert cluster["cell_type_ontology_term_id"] == "CL:4300353"
    assert cluster["cell_type"] == "Purkinje cell (Mmus)"
    assert "cell_type_pcl_ontology_term_id" not in cluster


@pytest.mark.unit
def test_json_pcl_exact(tmp_path: Path, mapper: CellTypeMapper) -> None:
    data = {"results": [{"cell_id": "c1", "assignment": {
        "cluster": {"label": "CS20230722_CLUS_0002"}
    }}]}
    in_p, out_p = tmp_path / "i.json", tmp_path / "o.json"
    in_p.write_text(json.dumps(data))
    annotate_json(in_p, out_p, mapper)

    cluster = json.loads(out_p.read_text())["results"][0]["assignment"]["cluster"]
    assert cluster["cell_type_ontology_term_id"] == "CL:4300353"
    assert cluster["cell_type_pcl_ontology_term_id"] == "PCL:0010002"
    assert "CL:4300353" in cluster["cell_type_cl_broad_ontology_term_ids"]


@pytest.mark.unit
def test_json_unknown_id(tmp_path: Path, mapper: CellTypeMapper) -> None:
    data = {"results": [{"cell_id": "c1", "assignment": {
        "cluster": {"label": "CS20230722_NOPE_999"}
    }}]}
    in_p, out_p = tmp_path / "i.json", tmp_path / "o.json"
    in_p.write_text(json.dumps(data))
    annotate_json(in_p, out_p, mapper)

    cluster = json.loads(out_p.read_text())["results"][0]["assignment"]["cluster"]
    assert cluster["cell_type_ontology_term_id"] == ""
    assert "cell_type_pcl_ontology_term_id" not in cluster
