"""Unit tests for mapmycells2cl.parser."""

import pytest

from mapmycells2cl.parser import build_mapping_from_string


@pytest.mark.unit
def test_exact_cl_match(minimal_owl_xml: str) -> None:
    mapping = build_mapping_from_string(minimal_owl_xml)
    entry = mapping["exact"]["CS20230722_SUBC_313"]
    assert entry["id"] == "CL:4300353"
    assert entry["ontology"] == "CL"
    assert entry["label"] == "Purkinje cell (Mmus)"


@pytest.mark.unit
def test_exact_pcl_match(minimal_owl_xml: str) -> None:
    entry = build_mapping_from_string(minimal_owl_xml)["exact"]["CS20230722_CLUS_0001"]
    assert entry["id"] == "PCL:0010001"
    assert entry["ontology"] == "PCL"


@pytest.mark.unit
def test_broad_via_subclass(minimal_owl_xml: str) -> None:
    broad = build_mapping_from_string(minimal_owl_xml)["broad"]
    assert "CS20230722_CLUS_0002" in broad
    assert any(m["id"] == "CL:4300353" for m in broad["CS20230722_CLUS_0002"])


@pytest.mark.unit
def test_broad_via_individual_hierarchy(minimal_owl_xml: str) -> None:
    broad = build_mapping_from_string(minimal_owl_xml)["broad"]
    assert "CS20230722_CLUS_0003" in broad
    assert any(m["id"] == "CL:4300353" for m in broad["CS20230722_CLUS_0003"])


@pytest.mark.unit
def test_two_hop_broad_via_individual(minimal_owl_xml: str) -> None:
    broad = build_mapping_from_string(minimal_owl_xml)["broad"]
    assert "CS20230722_CLUS_0004" in broad
    assert any(m["id"] == "CL:4300353" for m in broad["CS20230722_CLUS_0004"])


@pytest.mark.unit
def test_version_extracted(minimal_owl_xml: str) -> None:
    assert build_mapping_from_string(minimal_owl_xml)["version"] == "2026-03-26"


@pytest.mark.unit
def test_no_broad_for_cl_exact(minimal_owl_xml: str) -> None:
    assert "CS20230722_SUBC_313" not in build_mapping_from_string(minimal_owl_xml)["broad"]


@pytest.mark.unit
def test_mapping_has_required_keys(minimal_owl_xml: str) -> None:
    assert {"version", "source", "generated", "exact", "broad"} <= build_mapping_from_string(
        minimal_owl_xml
    ).keys()


# ---------------------------------------------------------------------------
# IC / best_cl tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_best_cl_absent_without_cl_owl(minimal_owl_xml: str) -> None:
    """best_cl section absent when no cl.owl supplied."""
    assert "best_cl" not in build_mapping_from_string(minimal_owl_xml)


@pytest.mark.unit
def test_best_cl_present_with_cl_owl(minimal_owl_xml: str, minimal_cl_owl_xml: str) -> None:
    """best_cl section present when cl.owl supplied."""
    mapping = build_mapping_from_string(minimal_owl_xml, cl_owl_xml=minimal_cl_owl_xml)
    assert "best_cl" in mapping


@pytest.mark.unit
def test_best_cl_for_cl_exact(minimal_owl_xml: str, minimal_cl_owl_xml: str) -> None:
    """CL exact match: best_cl equals the exact match itself."""
    mapping = build_mapping_from_string(minimal_owl_xml, cl_owl_xml=minimal_cl_owl_xml)
    best = mapping["best_cl"]["CS20230722_SUBC_313"]
    assert best["id"] == "CL:4300353"
    assert best["ic"] >= 0  # 0.0 is valid when fixture has a single leaf


@pytest.mark.unit
def test_best_cl_for_pcl_exact(minimal_owl_xml: str, minimal_cl_owl_xml: str) -> None:
    """PCL exact match with CL broad: best_cl is the CL broad match."""
    mapping = build_mapping_from_string(minimal_owl_xml, cl_owl_xml=minimal_cl_owl_xml)
    best = mapping["best_cl"]["CS20230722_CLUS_0002"]
    assert best["id"] == "CL:4300353"
    assert best["ic"] >= 0


@pytest.mark.unit
def test_ic_score_is_non_negative(minimal_owl_xml: str, minimal_cl_owl_xml: str) -> None:
    """All IC scores in best_cl are non-negative."""
    mapping = build_mapping_from_string(minimal_owl_xml, cl_owl_xml=minimal_cl_owl_xml)
    for entry in mapping["best_cl"].values():
        assert entry["ic"] >= 0
