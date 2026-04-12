# MapMyCells2CL

Annotate [MapMyCells](https://brain-map.org/bkp/analyze/mapmycells) output with [Cell Ontology (CL)](https://obofoundry.org/ontology/cl.html) terms.

MapMyCells assigns cells to Allen Brain Atlas (ABA) taxonomy nodes (e.g. `CS20230722_SUBC_053`). This library maps those IDs to CL or Provisional Cell Ontology (PCL) terms, providing both **exact matches** and **broad CL matches** for fine-grained PCL types.

---

## Quick start

```bash
# 1. Clone and set up
git clone https://github.com/<your-username>/MapMyCells2CL.git
cd MapMyCells2CL
uv sync

# 2. Annotate a MapMyCells CSV
./mmc2cl annotate results.csv

# Output written to results_annotated.csv
```

---

## Installation

### From source (development)

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/<your-username>/MapMyCells2CL.git
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
# Annotate CSV — output written to results_annotated.csv
./mmc2cl annotate results.csv

# Specify output path
./mmc2cl annotate results.csv -o /data/annotated.csv

# Annotate JSON output
./mmc2cl annotate results.json -o results_annotated.json

# Use a custom/updated mapping
./mmc2cl annotate results.csv --mapping /path/to/mapping.json
```

**CSV input format** — standard MapMyCells CSV with `#` comment header lines and columns such as `class_label`, `subclass_label`, `supertype_label`, `cluster_label`.

**CSV output** — adds three columns immediately after each `{level}_label` column:

| Column | Description |
|--------|-------------|
| `{level}_cl_exact` | CL or PCL CURIE for the exact equivalentClass match (e.g. `PCL:0110113`) |
| `{level}_cl_label` | Human-readable label for the exact match |
| `{level}_cl_broad` | `\|`-joined CL CURIEs for broad matches via subClassOf (empty if exact match is already CL) |

Example output row (subclass level):

```
subclass_label          → CS20230722_SUBC_053
subclass_cl_exact       → PCL:0110113
subclass_cl_label       → Sst Gaba sst GABAergic cortical interneuron (Mmus)
subclass_cl_broad       → CL:4023017|CL:4023069
```

**JSON input format** — MapMyCells JSON with a `results` list where each cell has an `assignment` dict keyed by level (each level has a `"label"` key with the ABA taxonomy ID).

**JSON output** — adds `cl_exact`, `cl_label`, `cl_broad` keys to each level's assignment dict:

```json
{
  "results": [
    {
      "cell_id": "H2",
      "assignment": {
        "subclass": {
          "label": "CS20230722_SUBC_053",
          "cl_exact": "PCL:0110113",
          "cl_label": "Sst Gaba sst GABAergic cortical interneuron (Mmus)",
          "cl_broad": ["CL:4023017", "CL:4023069"]
        }
      }
    }
  ]
}
```

---

### `update-mappings`

Download the latest `pcl.owl` and regenerate the bundled `mapping.json`.

```bash
./mmc2cl update-mappings [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--owl PATH` | Use a local OWL file instead of downloading |
| `--output PATH` | Output path for mapping JSON (default: bundled `src/mapmycells2cl/data/mapping.json`) |

**Examples:**

```bash
# Download latest pcl.owl and regenerate
./mmc2cl update-mappings

# Use a locally cached OWL file
./mmc2cl update-mappings --owl /data/pcl.owl

# Write to a custom path
./mmc2cl update-mappings --owl pcl.owl --output /data/my_mapping.json
```

---

## Python API

### `CellTypeMapper`

```python
from mapmycells2cl import CellTypeMapper

# Load bundled mapping (default)
mapper = CellTypeMapper()

# Or load a custom mapping
mapper = CellTypeMapper(mapping_path="/path/to/mapping.json")

print(mapper.mapping_version)  # e.g. "2025-07-07"
```

### Single lookup

```python
result = mapper.lookup("CS20230722_SUBC_313")

result.found          # True
result.exact_id       # "CL:4300353"
result.exact_label    # "Purkinje cell (Mmus)"
result.ontology       # "CL"
result.broad          # [] (already a CL term — no broad match needed)
result.mapping_version  # "2025-07-07"
```

```python
result = mapper.lookup("CS20230722_SUBC_053")

result.exact_id     # "PCL:0110113"
result.ontology     # "PCL"
result.broad        # [BroadMatch(id="CL:4023017", ...), BroadMatch(id="CL:4023069", ...)]

# Broad matches include provenance
for b in result.broad:
    print(b.id, b.label, b.via)
    # CL:4023017  sst GABAergic cortical interneuron  [...]
    # CL:4023069  medial ganglionic eminence derived GABAergic cortical interneuron  [...]
```

```python
# Unknown ID
result = mapper.lookup("CS20230722_UNKNOWN_999")
result.found  # False
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
from mapmycells2cl.annotator import annotate_csv, annotate_json

mapper = CellTypeMapper()

annotate_csv(Path("results.csv"), Path("results_annotated.csv"), mapper)
annotate_json(Path("results.json"), Path("results_annotated.json"), mapper)
```

---

## Match types explained

### Exact match

Extracted from `owl:equivalentClass` axioms in `pcl.owl`:

```
CL/PCL_class ≡ CL_0000000 ∧ (RO_0015001 hasValue <ABA_individual>)
```

Every ABA taxonomy ID maps to either a **CL term** (direct Cell Ontology entry) or a **PCL term** (Provisional Cell Ontology — finer-grained types not yet in CL).

### Broad match

For PCL exact matches, the library walks `rdfs:subClassOf` edges upward until CL terms are reached. Because the hierarchy is a DAG (not a tree), a single PCL term may yield **multiple CL broad matches** (polyhierarchy).

| Coverage (CCN20230722 taxonomy) | → CL | → PCL | Total |
|---------------------------------|------|-------|-------|
| CLAS (class) | 3 | 24 | 27 |
| SUBC (subclass) | 15 | 230 | 245 |
| SUPT (supertype) | 32 | 983 | 1,015 |
| CLUS (cluster) | 80 | 5,234 | 5,314 |
| **Total** | **130** | **6,471** | **6,601** |

---

## Data source

Mappings are extracted from the [Provisional Cell Ontology](http://purl.obolibrary.org/obo/pcl.owl) (`pcl.owl`), which imports CL and contains the full ABA taxonomy coverage. The bundled `mapping.json` is versioned with the PCL ontology release date.

The large OWL files (`pcl.owl`, `cl-full.owl`) are excluded from the repo. Run `./mmc2cl update-mappings` to regenerate `mapping.json` from the latest release.

---

## Development

```bash
uv sync --dev

# Type check
uv run mypy src/

# Lint + format
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/

# Unit tests
uv run pytest -m unit --cov

# All tests (requires network / local pcl.owl)
uv run pytest -m integration
```

CI runs mypy, ruff, and unit tests on every PR via GitHub Actions.

---

## Known gaps

- Basal Ganglia ABA mappings are absent from CL — fix planned for a future CL release.
- `oaklib` support deferred pending Python 3.14 compatibility fix.
- h5ad / CELLxGENE annotation support planned (Phase 4).
