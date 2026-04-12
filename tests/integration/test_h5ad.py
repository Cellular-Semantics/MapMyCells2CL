"""Integration test: annotate real h5ad with real mapping."""

from pathlib import Path

import anndata as ad
import pytest

from mapmycells2cl.annotator import annotate_h5ad
from mapmycells2cl.mapper import CellTypeMapper

TEST_RESOURCES = Path(__file__).parent.parent.parent / "test_resources"
H5AD = TEST_RESOURCES / "GSE124847_OLM_mmc.h5ad"
MMC_CSV = TEST_RESOURCES / "mmc_results.csv"


@pytest.mark.integration
def test_annotate_h5ad_real_data(tmp_path: Path) -> None:
    """Annotate the bundled OLM h5ad with the real mapping and spot-check obs."""
    if not H5AD.exists() or not MMC_CSV.exists():
        pytest.skip("test_resources not present")

    mapper = CellTypeMapper()
    h5ad_out = tmp_path / "annotated.h5ad"
    annotate_h5ad(MMC_CSV, H5AD, h5ad_out, mapper)

    adata = ad.read_h5ad(h5ad_out)
    obs = adata.obs

    # CxG required unprefixed columns present
    assert "cell_type_ontology_term_id" in obs.columns
    assert "cell_type" in obs.columns

    # All cells annotated (no empties for these well-mapped cells)
    assert (obs["cell_type_ontology_term_id"] != "").all()
    assert obs["cell_type_ontology_term_id"].str.startswith("CL:").all()

    # Prefixed multi-level columns present
    for level in ("class", "subclass", "supertype", "cluster"):
        assert f"{level}--cell_type_ontology_term_id" in obs.columns

    # Original obs columns preserved
    assert "CellType" in obs.columns

    # Spot check: first cell H2 gets a valid CL term
    assert obs.loc["H2", "cell_type_ontology_term_id"].startswith("CL:")
