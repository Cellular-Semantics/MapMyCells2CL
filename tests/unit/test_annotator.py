"""Unit tests for mapmycells2cl.annotator."""

import json
import textwrap
from pathlib import Path

import pytest

from mapmycells2cl.annotator import annotate_csv_string, annotate_json
from mapmycells2cl.mapper import CellTypeMapper
from mapmycells2cl.parser import build_mapping_from_string


@pytest.fixture()
def mapper(minimal_owl_xml: str) -> CellTypeMapper:
    """CellTypeMapper built from the minimal fixture OWL."""
    mapping = build_mapping_from_string(minimal_owl_xml)
    return CellTypeMapper.from_mapping_dict(mapping)


# ---------------------------------------------------------------------------
# CSV tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_csv_adds_cl_columns(mapper: CellTypeMapper) -> None:
    """Annotator adds _cl_exact, _cl_label, _cl_broad columns."""
    csv_text = textwrap.dedent("""\
        cell_id,cluster_label,cluster_name
        cell1,CS20230722_SUBC_313,Purkinje
    """)
    out = annotate_csv_string(csv_text, mapper)
    import csv as _csv
    reader = _csv.DictReader(out.splitlines())
    row = next(reader)
    assert row["cluster_cl_exact"] == "CL:4300353"
    assert row["cluster_cl_label"] == "Purkinje cell (Mmus)"
    assert row["cluster_cl_broad"] == ""  # CL exact → no broad


@pytest.mark.unit
def test_csv_pcl_exact_has_broad(mapper: CellTypeMapper) -> None:
    """PCL exact match results in broad column being populated."""
    csv_text = textwrap.dedent("""\
        cell_id,cluster_label
        cell1,CS20230722_CLUS_0002
    """)
    out = annotate_csv_string(csv_text, mapper)
    import csv as _csv
    reader = _csv.DictReader(out.splitlines())
    row = next(reader)
    assert row["cluster_cl_exact"] == "PCL:0010002"
    assert "CL:4300353" in row["cluster_cl_broad"]


@pytest.mark.unit
def test_csv_unknown_id_empty(mapper: CellTypeMapper) -> None:
    """Unknown ABA ID produces empty CL columns."""
    csv_text = textwrap.dedent("""\
        cell_id,cluster_label
        cell1,CS20230722_UNKNOWN_999
    """)
    out = annotate_csv_string(csv_text, mapper)
    import csv as _csv
    reader = _csv.DictReader(out.splitlines())
    row = next(reader)
    assert row["cluster_cl_exact"] == ""
    assert row["cluster_cl_label"] == ""
    assert row["cluster_cl_broad"] == ""


@pytest.mark.unit
def test_csv_multiple_levels(mapper: CellTypeMapper) -> None:
    """Annotator handles multiple taxonomy levels in the same CSV."""
    csv_text = textwrap.dedent("""\
        cell_id,subclass_label,cluster_label
        cell1,CS20230722_SUBC_313,CS20230722_CLUS_0002
    """)
    out = annotate_csv_string(csv_text, mapper)
    import csv as _csv
    reader = _csv.DictReader(out.splitlines())
    row = next(reader)
    assert row["subclass_cl_exact"] == "CL:4300353"
    assert row["cluster_cl_exact"] == "PCL:0010002"


# ---------------------------------------------------------------------------
# JSON tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_json_annotates_assignment(tmp_path: Path, mapper: CellTypeMapper) -> None:
    """Annotator adds cl_exact/cl_label/cl_broad to each assignment level."""
    data = {
        "results": [
            {
                "cell_id": "cell1",
                "assignment": {
                    "cluster": {"label": "CS20230722_SUBC_313", "name": "Purkinje"},
                },
            }
        ]
    }
    in_path = tmp_path / "input.json"
    out_path = tmp_path / "output.json"
    in_path.write_text(json.dumps(data))

    annotate_json(in_path, out_path, mapper)

    result = json.loads(out_path.read_text())
    cluster = result["results"][0]["assignment"]["cluster"]
    assert cluster["cl_exact"] == "CL:4300353"
    assert cluster["cl_label"] == "Purkinje cell (Mmus)"
    assert cluster["cl_broad"] == []


@pytest.mark.unit
def test_json_pcl_gets_broad(tmp_path: Path, mapper: CellTypeMapper) -> None:
    """JSON annotator populates cl_broad list for PCL exact matches."""
    data = {
        "results": [
            {
                "cell_id": "cell1",
                "assignment": {
                    "cluster": {"label": "CS20230722_CLUS_0002"},
                },
            }
        ]
    }
    in_path = tmp_path / "input.json"
    out_path = tmp_path / "output.json"
    in_path.write_text(json.dumps(data))

    annotate_json(in_path, out_path, mapper)

    result = json.loads(out_path.read_text())
    cluster = result["results"][0]["assignment"]["cluster"]
    assert cluster["cl_exact"] == "PCL:0010002"
    assert "CL:4300353" in cluster["cl_broad"]


@pytest.mark.unit
def test_json_unknown_id(tmp_path: Path, mapper: CellTypeMapper) -> None:
    """JSON annotator sets empty strings for unknown ABA IDs."""
    data = {
        "results": [
            {
                "cell_id": "cell1",
                "assignment": {
                    "cluster": {"label": "CS20230722_NOPE_999"},
                },
            }
        ]
    }
    in_path = tmp_path / "input.json"
    out_path = tmp_path / "output.json"
    in_path.write_text(json.dumps(data))

    annotate_json(in_path, out_path, mapper)

    result = json.loads(out_path.read_text())
    cluster = result["results"][0]["assignment"]["cluster"]
    assert cluster["cl_exact"] == ""
    assert cluster["cl_broad"] == []
