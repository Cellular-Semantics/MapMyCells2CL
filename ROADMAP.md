# MapMyCells2CL

## Background and functional specs

[Map My Cells](https://brain-map.org/bkp/analyze/mapmycells) produces content with Allen Brain Atlas taxonomy IDs. Some of these taxonomy terms are directly used to define CL terms while others have general CL term mappings.

Where they are mapped to CL terms the OWL follows this structure:

```xml
<owl:Class rdf:about="http://purl.obolibrary.org/obo/CL_4300353">
    <owl:equivalentClass>
        <owl:Class>
            <owl:intersectionOf rdf:parseType="Collection">
                <rdf:Description rdf:about="http://purl.obolibrary.org/obo/CL_0000000"/>
                <owl:Restriction>
                    <owl:onProperty rdf:resource="http://purl.obolibrary.org/obo/RO_0015001"/>
                    <owl:hasValue rdf:resource="https://purl.brain-bican.org/ontology/CCN20230722/CS20230722_SUBC_313"/>
                </owl:Restriction>
            </owl:intersectionOf>
        </owl:Class>
    </owl:equivalentClass>
```

The aim of this project is to provide a standard library for using the outputs of MapMyCells to annotate cells with CL terms, indicating exact and broad matches.

MVP output: modified MapMyCells JSON (& csv?) with CL IDs.

First post-MVP output: support updating h5ad files, following CELLxGENE standard for cell type annotation.

## Exploration findings (2026-04-12)

### Data source: pcl.owl

The Provisional Cell Ontology (`http://purl.obolibrary.org/obo/pcl.owl`) is the primary data source. It imports CL and contains far richer ABA taxonomy coverage than CL alone.

**Exact match coverage (CCN20230722):**

| Level | -> CL | -> PCL | Total |
|-------|-------|--------|-------|
| CLAS (class) | 3 | 24 | 27 |
| SUBC (subclass) | 15 | 230 | 245 |
| SUPT (supertype) | 32 | 983 | 1,015 |
| CLUS (cluster) | 80 | 5,234 | 5,314 |
| **Total** | **130** | **6,471** | **6,601** |

### Exact matches

Extracted from `owl:equivalentClass` axioms on CL and PCL classes:

```
CL/PCL class ≡ CL_0000000 and (RO_0015001 hasValue <ABA_individual>)
```

Where `RO_0015001` = "has exemplar data". This gives a direct ABA taxonomy ID -> CL/PCL term mapping.

### Broad matches

For PCL terms that lack a direct CL equivalent, walk up the `rdfs:subClassOf` hierarchy from exact-match PCL terms to find the nearest CL ancestor(s). Note: polyhierarchy means a PCL term may have **multiple CL broad matches** (e.g. a PCL neuron subtype that is subClassOf both a brain-region CL type and a neurotransmitter CL type).

### Approaches ruled out

- **OBO JSON Graph** (`cl-full.json`): `logicalDefinitionAxioms` does not capture `hasValue` restrictions (individual fillers). Edges section also lacks `RO_0015001`.
- **OLS4 API**: Cannot reverse-lookup from ABA individual to CL class. Individual `types` endpoint only returns `PCL_0010001`.
- **oaklib** (v0.6.23): Broken on Python 3.14 (linkml `Format.JSON` removed). Worth revisiting when fixed, but unclear whether its SQLite DB captures `hasValue` restrictions either.

### Known gaps

- Basal Ganglia mappings missing from CL — fix planned for next CL release.

## Implementation plan

### Phase 1: OWL parser and mapping generator

Build a module that downloads and parses `pcl.owl` to produce a versioned mapping file.

**Inputs:** pcl.owl (downloaded from `http://purl.obolibrary.org/obo/pcl.owl`)

**Outputs:** A versioned JSON mapping file containing:

```json
{
  "version": "2026-03-26",
  "source": "http://purl.obolibrary.org/obo/pcl.owl",
  "generated": "2026-04-12T...",
  "exact": {
    "CS20230722_SUBC_313": {
      "id": "CL:4300353",
      "label": "Purkinje cell (Mmus)",
      "ontology": "CL"
    },
    "CS20230722_CLAS_01": {
      "id": "PCL:0110001",
      "label": "...",
      "ontology": "PCL"
    }
  },
  "broad": {
    "CS20230722_CLUS_0943": [
      {
        "id": "CL:4300101",
        "label": "...",
        "via": ["PCL:...", "PCL:..."]
      }
    ]
  }
}
```

**Steps:**

1. **OWL downloader** — fetch pcl.owl from PURL, cache locally, extract ontology version from `owl:versionInfo`.
2. **Exact match extractor** — scan `owl:Class` blocks for `equivalentClass` axioms containing `RO_0015001` + `hasValue` with `brain-bican` URIs. Record target as CL or PCL with label.
3. **Broad match extractor** — for each PCL exact-match term, collect all `rdfs:subClassOf` named ancestors. Walk up the hierarchy until CL term(s) are reached. Store all CL ancestors (polyhierarchy → multiple broad matches). Include the intermediate path for provenance.
4. **Mapping serialiser** — write the combined exact + broad mapping to versioned JSON.

### Phase 2: Lookup library

A fast, dependency-light lookup module that ships with a pre-built mapping file.

**Core API:**

```python
from mapmycells2cl import CellTypeMapper

mapper = CellTypeMapper()  # loads packaged mapping

# Single lookup
result = mapper.lookup("CS20230722_SUBC_313")
# -> MatchResult(exact=CL:4300353, broad=[], label="Purkinje cell (Mmus)")

# ABA ID without exact CL match
result = mapper.lookup("CS20230722_CLUS_0943")
# -> MatchResult(exact=PCL:..., broad=[CL:4300101, ...], label="...")

# Batch lookup
results = mapper.lookup_many(["CS20230722_SUBC_313", "CS20230722_CLUS_0943"])
```

**MatchResult fields:**
- `exact`: The CL or PCL term this ABA ID is equivalent to
- `broad`: List of CL terms reachable via subClassOf from the exact PCL match (empty if exact is already CL). Multiple entries possible due to polyhierarchy.
- `label`: Human-readable name
- `ontology`: "CL" or "PCL"
- `mapping_version`: Version of the mapping data

### Phase 3: MapMyCells output annotator (MVP)

Read MapMyCells CSV/JSON output and annotate with CL terms.

**MapMyCells output format** (from `cell_type_mapper`):
- CSV: columns per taxonomy level — `{level}_label`, `{level}_name`, `{level}_bootstrapping_probability`
- JSON: `results` list with per-cell dicts containing `assignment` per level

**Annotator behaviour:**
1. Parse MapMyCells output (CSV or JSON).
2. For each cell, at each taxonomy level, look up the `{level}_label` value (e.g. `CS20230722_SUBC_313`).
3. Add columns/fields: `{level}_cl_exact`, `{level}_cl_broad`, `{level}_cl_label`.
4. For broad matches with multiple CL terms (polyhierarchy), join with `|` in CSV or use a list in JSON.
5. Write annotated output in same format.

**CLI:**

```bash
mapmycells2cl annotate input.csv -o output.csv
mapmycells2cl annotate input.json -o output.json
```

### Phase 4: Post-MVP — h5ad support

Add support for annotating h5ad files following CELLxGENE schema conventions.

### Phase 5: Post-MVP — mapping regeneration CLI

```bash
# Download latest pcl.owl and regenerate mapping
mapmycells2cl update-mappings

# Generate from local OWL file
mapmycells2cl update-mappings --owl /path/to/pcl.owl
```

### Versioning strategy

- The packaged mapping JSON includes the PCL ontology version (`owl:versionInfo` date).
- `update-mappings` fetches the latest pcl.owl and regenerates.
- The library warns if the mapping version is older than a configurable threshold.
- Mapping JSON is committed to the repo (small file, ~1-2 MB) so users get it on install without needing to run the generator.
