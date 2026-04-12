"""Unit tests for mapmycells2cl.mapper."""

import pytest

from mapmycells2cl.mapper import CellTypeMapper
from mapmycells2cl.parser import build_mapping_from_string


@pytest.fixture()
def mapper(minimal_owl_xml: str) -> CellTypeMapper:
    """CellTypeMapper built from the minimal fixture OWL."""
    mapping = build_mapping_from_string(minimal_owl_xml)
    return CellTypeMapper.from_mapping_dict(mapping)


@pytest.mark.unit
def test_lookup_cl_exact(mapper: CellTypeMapper) -> None:
    """Lookup of a CL exact match returns correct fields."""
    result = mapper.lookup("CS20230722_SUBC_313")
    assert result.found is True
    assert result.exact_id == "CL:4300353"
    assert result.exact_label == "Purkinje cell (Mmus)"
    assert result.ontology == "CL"
    assert result.broad == []


@pytest.mark.unit
def test_lookup_pcl_exact_with_broad(mapper: CellTypeMapper) -> None:
    """Lookup of a PCL exact match with broad CL ancestor returns both."""
    result = mapper.lookup("CS20230722_CLUS_0002")
    assert result.found is True
    assert result.ontology == "PCL"
    assert result.exact_id == "PCL:0010002"
    broad_ids = [b.id for b in result.broad]
    assert "CL:4300353" in broad_ids


@pytest.mark.unit
def test_lookup_unknown_id(mapper: CellTypeMapper) -> None:
    """Unknown ABA ID returns found=False with empty fields."""
    result = mapper.lookup("CS20230722_UNKNOWN_999")
    assert result.found is False
    assert result.exact_id == ""
    assert result.broad == []


@pytest.mark.unit
def test_lookup_many(mapper: CellTypeMapper) -> None:
    """lookup_many returns one result per input in order."""
    ids = ["CS20230722_SUBC_313", "CS20230722_UNKNOWN_999", "CS20230722_CLUS_0001"]
    results = mapper.lookup_many(ids)
    assert len(results) == 3
    assert results[0].found is True
    assert results[1].found is False
    assert results[2].found is True
    assert results[2].exact_id == "PCL:0010001"


@pytest.mark.unit
def test_mapping_version(mapper: CellTypeMapper) -> None:
    """mapping_version property returns version from fixture."""
    assert mapper.mapping_version == "2026-03-26"


@pytest.mark.unit
def test_result_carries_version(mapper: CellTypeMapper) -> None:
    """MatchResult.mapping_version matches mapper version."""
    result = mapper.lookup("CS20230722_SUBC_313")
    assert result.mapping_version == mapper.mapping_version
