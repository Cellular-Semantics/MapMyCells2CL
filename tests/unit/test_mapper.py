"""Unit tests for mapmycells2cl.mapper."""

import pytest

from mapmycells2cl.mapper import CellTypeMapper
from mapmycells2cl.parser import build_mapping_from_string


@pytest.fixture()
def mapper_no_ic(minimal_owl_xml: str) -> CellTypeMapper:
    """Mapper without IC data."""
    return CellTypeMapper.from_mapping_dict(build_mapping_from_string(minimal_owl_xml))


@pytest.fixture()
def mapper(minimal_owl_xml: str, minimal_cl_owl_xml: str) -> CellTypeMapper:
    """Mapper with IC data."""
    mapping = build_mapping_from_string(minimal_owl_xml, cl_owl_xml=minimal_cl_owl_xml)
    return CellTypeMapper.from_mapping_dict(mapping)


# ---------------------------------------------------------------------------
# Basic lookup
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_lookup_cl_exact(mapper: CellTypeMapper) -> None:
    result = mapper.lookup("CS20230722_SUBC_313")
    assert result.found is True
    assert result.exact_id == "CL:4300353"
    assert result.exact_label == "Purkinje cell (Mmus)"
    assert result.ontology == "CL"
    assert result.broad == []


@pytest.mark.unit
def test_lookup_pcl_exact_with_broad(mapper: CellTypeMapper) -> None:
    result = mapper.lookup("CS20230722_CLUS_0002")
    assert result.found is True
    assert result.ontology == "PCL"
    assert result.exact_id == "PCL:0010002"
    assert any(b.id == "CL:4300353" for b in result.broad)


@pytest.mark.unit
def test_lookup_unknown_id(mapper: CellTypeMapper) -> None:
    result = mapper.lookup("CS20230722_UNKNOWN_999")
    assert result.found is False
    assert result.exact_id == ""
    assert result.broad == []
    assert result.best_cl_id == ""


@pytest.mark.unit
def test_lookup_many(mapper: CellTypeMapper) -> None:
    ids = ["CS20230722_SUBC_313", "CS20230722_UNKNOWN_999", "CS20230722_CLUS_0001"]
    results = mapper.lookup_many(ids)
    assert len(results) == 3
    assert results[0].found is True
    assert results[1].found is False
    assert results[2].exact_id == "PCL:0010001"


@pytest.mark.unit
def test_mapping_version(mapper: CellTypeMapper) -> None:
    assert mapper.mapping_version == "2026-03-26"


@pytest.mark.unit
def test_result_carries_version(mapper: CellTypeMapper) -> None:
    assert mapper.lookup("CS20230722_SUBC_313").mapping_version == mapper.mapping_version


# ---------------------------------------------------------------------------
# best_cl / IC fields
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_has_ic_true(mapper: CellTypeMapper) -> None:
    assert mapper.has_ic is True


@pytest.mark.unit
def test_has_ic_false(mapper_no_ic: CellTypeMapper) -> None:
    assert mapper_no_ic.has_ic is False


@pytest.mark.unit
def test_best_cl_for_cl_exact(mapper: CellTypeMapper) -> None:
    """CL exact: best_cl_id == exact_id."""
    result = mapper.lookup("CS20230722_SUBC_313")
    assert result.best_cl_id == "CL:4300353"
    assert result.best_cl_ic >= 0  # 0.0 valid in single-leaf fixture


@pytest.mark.unit
def test_best_cl_for_pcl_exact(mapper: CellTypeMapper) -> None:
    """PCL exact: best_cl_id is the IC-ranked CL broad match."""
    result = mapper.lookup("CS20230722_CLUS_0002")
    assert result.best_cl_id == "CL:4300353"
    assert result.best_cl_ic >= 0


@pytest.mark.unit
def test_best_cl_empty_without_ic(mapper_no_ic: CellTypeMapper) -> None:
    """Without IC data best_cl_id is empty string."""
    result = mapper_no_ic.lookup("CS20230722_SUBC_313")
    assert result.best_cl_id == ""
    assert result.best_cl_ic == 0.0
