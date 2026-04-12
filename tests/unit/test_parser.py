"""Unit tests for mapmycells2cl.parser."""

import pytest

from mapmycells2cl.parser import build_mapping_from_string


@pytest.mark.unit
def test_exact_cl_match(minimal_owl_xml: str) -> None:
    """CL exact match is extracted correctly."""
    mapping = build_mapping_from_string(minimal_owl_xml)
    exact = mapping["exact"]
    assert "CS20230722_SUBC_313" in exact
    entry = exact["CS20230722_SUBC_313"]
    assert entry["id"] == "CL:4300353"
    assert entry["ontology"] == "CL"
    assert entry["label"] == "Purkinje cell (Mmus)"


@pytest.mark.unit
def test_exact_pcl_match(minimal_owl_xml: str) -> None:
    """PCL exact match is extracted correctly."""
    mapping = build_mapping_from_string(minimal_owl_xml)
    exact = mapping["exact"]
    assert "CS20230722_CLUS_0001" in exact
    entry = exact["CS20230722_CLUS_0001"]
    assert entry["id"] == "PCL:0010001"
    assert entry["ontology"] == "PCL"


@pytest.mark.unit
def test_broad_via_subclass(minimal_owl_xml: str) -> None:
    """PCL term with subClassOf CL gets a broad match."""
    mapping = build_mapping_from_string(minimal_owl_xml)
    broad = mapping["broad"]
    # CS20230722_CLUS_0002 maps to PCL:0010002 which is subClassOf CL:4300353
    assert "CS20230722_CLUS_0002" in broad
    matches = broad["CS20230722_CLUS_0002"]
    assert any(m["id"] == "CL:4300353" for m in matches)


@pytest.mark.unit
def test_broad_via_individual_hierarchy(minimal_owl_xml: str) -> None:
    """ABA ID without subClassOf uses individual hierarchy for broad match."""
    mapping = build_mapping_from_string(minimal_owl_xml)
    broad = mapping["broad"]
    # CS20230722_CLUS_0003 has no exact match but its parent SUBC_313 -> CL:4300353
    assert "CS20230722_CLUS_0003" in broad
    matches = broad["CS20230722_CLUS_0003"]
    assert any(m["id"] == "CL:4300353" for m in matches)


@pytest.mark.unit
def test_version_extracted(minimal_owl_xml: str) -> None:
    """Ontology version is extracted from owl:versionInfo."""
    mapping = build_mapping_from_string(minimal_owl_xml)
    assert mapping["version"] == "2026-03-26"


@pytest.mark.unit
def test_no_broad_for_cl_exact(minimal_owl_xml: str) -> None:
    """CL exact matches do not appear in the broad map."""
    mapping = build_mapping_from_string(minimal_owl_xml)
    # CS20230722_SUBC_313 is a CL exact — broad map should not have it
    assert "CS20230722_SUBC_313" not in mapping["broad"]


@pytest.mark.unit
def test_mapping_has_required_keys(minimal_owl_xml: str) -> None:
    """Output dict has all required top-level keys."""
    mapping = build_mapping_from_string(minimal_owl_xml)
    assert {"version", "source", "generated", "exact", "broad"} <= mapping.keys()


@pytest.mark.unit
def test_two_hop_broad_via_individual(minimal_owl_xml: str) -> None:
    """CLUS_0004 -> CLUS_0003 -> SUBC_313 gives broad match via two hops."""
    mapping = build_mapping_from_string(minimal_owl_xml)
    broad = mapping["broad"]
    assert "CS20230722_CLUS_0004" in broad
    matches = broad["CS20230722_CLUS_0004"]
    assert any(m["id"] == "CL:4300353" for m in matches)
