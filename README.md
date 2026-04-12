# MapMyCells2CL

Annotate [MapMyCells](https://brain-map.org/bkp/analyze/mapmycells) output with [Cell Ontology (CL)](https://obofoundry.org/ontology/cl.html) terms.

MapMyCells assigns cells to Allen Brain Atlas (ABA) taxonomy nodes (e.g. `CS20230722_SUBC_053`). This library maps those IDs to CL or Provisional Cell Ontology (PCL) terms and selects the **most specific CL term** using information-content (IC) ranking — ready for [CELLxGENE](https://cellxgene.cziscience.com/) schema compliance.

---

## Quick start

```bash
# 1. Clone and set up
git clone https://github.com/Cellular-Semantics/MapMyCells2CL.git
cd MapMyCells2CL
uv sync

# 2. Annotate a MapMyCells CSV
./mmc2cl annotate results.csv
# → results_annotated.csv

# 3. Annotate an h5ad file (CxG-compliant obs columns)
./mmc2cl annotate-h5ad results.csv cells.h5ad
# → cells_annotated.h5ad
```

---

## Installation

### From source (development)

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Cellular-Semantics/MapMyCells2CL.git
cd MapMyCells2CL
uv sync
```

This creates a `.venv` and installs the package with all dependencies. The `./mmc2cl` runner script uses this venv directly.

### As a Python package

```bash
pip install mapmycells2cl
# or
uv add mapmycells2cl
```

---

## The `./mmc2cl` runner

`mmc2cl` is a standalone shell script at the repo root. After `uv sync` it requires no `python` or `uv` prefix:

```bash
./mmc2cl <command> [options]
```

It looks for the installed venv binary first (fast path), then falls back to `uv run` if needed.

---

## CLI reference

### `annotate`

Annotate a MapMyCells CSV or JSON output file with CL terms.

```bash
./mmc2cl annotate INPUT_FILE [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-o, --output PATH` | Output file path. Defaults to `<input>_annotated.<ext>` |
| `--mapping PATH` | Path to a custom mapping JSON (default: bundled `mapping.json`) |

**Examples:**

```bash
# Annotate CSV
./mmc2cl annotate results.csv

# Annotate JSON
./mmc2cl annotate results.json

# Specify output path
./mmc2cl annotate results.csv -o /data/annotated.csv
```

**CSV output columns** — added after each `{level}_label` column using the CAP/HCA double-dash convention:

| Column | Content | When |
|--------|---------|------|
| `{level}--cell_type_ontology_term_id` | Most specific CL CURIE (IC-ranked) | Always |
| `{level}--cell_type` | Label for the above | Always |
| `{level}--cell_type_pcl_ontology_term_id` | PCL exact match CURIE | PCL exact only |
| `{level}--cell_type_pcl` | PCL exact label | PCL exact only |
| `{level}--cell_type_cl_broad_ontology_term_ids` | All CL broad CURIEs, `\|`-joined | PCL exact only |

Example (subclass level, PCL exact match):

```
subclass_label                              → CS20230722_SUBC_053
subclass--cell_type_ontology_term_id        → CL:4023017
subclass--cell_type                         → sst GABAergic cortical interneuron
subclass--cell_type_pcl_ontology_term_id    → PCL:0110113
subclass--cell_type_pcl                     → Sst Gaba sst GABAergic cortical interneuron (Mmus)
subclass--cell_type_cl_broad_ontology_term_ids → CL:4023017|CL:4023069
```

**JSON output** — `cell_type_ontology_term_id`, `cell_type`, and (for PCL) `cell_type_pcl_ontology_term_id`, `cell_type_pcl`, `cell_type_cl_broad_ontology_term_ids` are added to each level's assignment dict.

---

### `annotate-h5ad`

Annotate an AnnData h5ad file with CL terms from a MapMyCells CSV. Adds CL columns directly to `adata.obs`, including the unprefixed `cell_type_ontology_term_id` / `cell_type` pair required by the [CELLxGENE schema](https://github.com/chanzuckerberg/single-cell-curation/blob/main/schema/5.3.0/schema.md).

```bash
./mmc2cl annotate-h5ad MMC_CSV H5AD_IN [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-o, --output PATH` | Output h5ad path. Defaults to `<input>_annotated.h5ad` |
| `--cxg-level TEXT` | Taxonomy level used for unprefixed CxG columns (default: `cluster`) |
| `--mapping PATH` | Path to a custom mapping JSON |

**Examples:**

```bash
# Annotate h5ad — output written to cells_annotated.h5ad
./mmc2cl annotate-h5ad results.csv cells.h5ad

# Use supertype level for the CxG cell_type columns
./mmc2cl annotate-h5ad results.csv cells.h5ad --cxg-level supertype
```

**obs columns added:**

| Column | Content |
|--------|---------|
| `cell_type_ontology_term_id` | IC-best CL CURIE from `--cxg-level` (CxG required) |
| `cell_type` | Label for the above (CxG required) |
| `{level}--cell_type_ontology_term_id` | Per-level IC-best CL CURIE |
| `{level}--cell_type` | Per-level label |
| `{level}--cell_type_pcl_ontology_term_id` | PCL CURIE (PCL exact only) |
| `{level}--cell_type_pcl` | PCL label (PCL exact only) |
| `{level}--cell_type_cl_broad_ontology_term_ids` | `\|`-joined broad CL CURIEs (PCL exact only) |

Cells present in the h5ad but absent from the mmc CSV get empty strings.

---

### `update-mappings`

Download the latest `pcl.owl` and regenerate the bundled `mapping.json`. Pass `--cl-owl` to include IC-ranked best-CL data (strongly recommended).

```bash
./mmc2cl update-mappings [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--owl PATH` | Use a local `pcl.owl` instead of downloading |
| `--cl-owl PATH` | Path to base `cl.owl` for IC computation. Downloads if omitted |
| `--output PATH` | Output path (default: bundled `src/mapmycells2cl/data/mapping.json`) |

**Examples:**

```bash
# Download latest pcl.owl and regenerate (no IC)
./mmc2cl update-mappings

# With IC ranking (recommended) — requires cl.owl (~63 MB)
./mmc2cl update-mappings --cl-owl cl.owl

# Use locally cached files
./mmc2cl update-mappings --owl pcl.owl --cl-owl cl.owl
```

> **Note:** `cl.owl` is large (~63 MB). The PURL `http://purl.obolibrary.org/obo/cl.owl` redirects to GitHub; download it manually if needed and pass the path with `--cl-owl`.

---

## Python API

### `CellTypeMapper`

```python
from mapmycells2cl import CellTypeMapper

mapper = CellTypeMapper()              # bundled mapping
print(mapper.mapping_version)          # e.g. "2025-07-07"
print(mapper.has_ic)                   # True when mapping includes IC data
```

### Single lookup

```python
result = mapper.lookup("CS20230722_SUBC_313")

result.found            # True
result.exact_id         # "CL:4300353"
result.exact_label      # "Purkinje cell (Mmus)"
result.ontology         # "CL"
result.broad            # [] — already CL, no broad match needed
result.best_cl_id       # "CL:4300353" — IC-ranked most specific CL term
result.best_cl_label    # "Purkinje cell (Mmus)"
result.best_cl_ic       # IC score (higher = more specific)
result.mapping_version  # "2025-07-07"
```

```python
result = mapper.lookup("CS20230722_SUBC_053")

result.exact_id     # "PCL:0110113"
result.ontology     # "PCL"
result.best_cl_id   # "CL:4023017"  — IC-ranked best CL broad match
result.broad        # [BroadMatch(id="CL:4023017", ...), BroadMatch(id="CL:4023069", ...)]

for b in result.broad:
    print(b.id, b.label, b.via)
```

```python
result = mapper.lookup("CS20230722_UNKNOWN_999")
result.found        # False
result.best_cl_id   # ""
```

### Batch lookup

```python
results = mapper.lookup_many([
    "CS20230722_SUBC_313",
    "CS20230722_SUBC_053",
    "CS20230722_CLUS_0768",
])
# Returns List[MatchResult] in the same order
```

### Annotator (programmatic use)

```python
from pathlib import Path
from mapmycells2cl import CellTypeMapper
from mapmycells2cl.annotator import annotate_csv, annotate_json, annotate_h5ad

mapper = CellTypeMapper()

# CSV / JSON
annotate_csv(Path("results.csv"), Path("results_annotated.csv"), mapper)
annotate_json(Path("results.json"), Path("results_annotated.json"), mapper)

# h5ad — CxG-compliant obs columns
annotate_h5ad(
    Path("results.csv"),
    Path("cells.h5ad"),
    Path("cells_annotated.h5ad"),
    mapper,
    cxg_level="cluster",   # level used for unprefixed cell_type columns
)
```

---

## How it works

### Exact matches

Extracted from `owl:equivalentClass` axioms in `pcl.owl`:

```
CL/PCL_class ≡ CL_0000000 ∧ (RO_0015001 hasValue <ABA_individual>)
```

Every ABA taxonomy ID maps to either a **CL term** (direct Cell Ontology entry) or a **PCL term** (Provisional Cell Ontology — finer-grained types not yet promoted to CL).

### Broad matches

For PCL exact matches, the library walks `rdfs:subClassOf` edges upward until CL terms are reached. Because the hierarchy is a DAG (not a tree), a single PCL term may yield **multiple CL broad matches** (polyhierarchy).

### IC-ranked best CL term

When multiple CL broad matches exist, the **most specific** is selected using structure-based Information Content computed over the base CL hierarchy (no PCL):

```
IC(c) = -log2(|distinct leaf descendants of c| / |total CL leaves|)
```

Higher IC = more specific. This is pre-computed at `update-mappings` time and stored in `mapping.json`, so there is no runtime CL dependency.

### Coverage (CCN20230722 taxonomy)

| Level | → CL | → PCL | Total |
|-------|------|-------|-------|
| CLAS (class) | 3 | 24 | 27 |
| SUBC (subclass) | 15 | 230 | 245 |
| SUPT (supertype) | 32 | 983 | 1,015 |
| CLUS (cluster) | 80 | 5,234 | 5,314 |
| **Total** | **130** | **6,471** | **6,601** |

---

## Data sources

- [`pcl.owl`](http://purl.obolibrary.org/obo/pcl.owl) — Provisional Cell Ontology; primary mapping source
- [`cl.owl`](http://purl.obolibrary.org/obo/cl.owl) — Base Cell Ontology (no imports); used for IC computation

Both large OWL files are excluded from the repo. The bundled `mapping.json` is versioned with the PCL release date and includes all pre-computed IC scores.

---

## Development

```bash
uv sync --dev

uv run mypy src/                          # type check
uv run ruff check --fix src/ tests/       # lint
uv run ruff format src/ tests/            # format

uv run pytest -m unit --cov              # unit tests (fast, no external deps)
uv run pytest -m integration             # integration tests (requires test_resources/)
```

CI runs mypy, ruff, and unit tests on every PR via GitHub Actions.

---

## Known gaps

- Basal Ganglia ABA mappings are absent from CL — fix planned for a future CL release.
- `oaklib` integration deferred (not yet needed for current use cases).
