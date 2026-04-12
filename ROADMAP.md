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
3. Add columns/fields using the field naming schema below.
4. Write annotated output in same format.

**Field naming schema** — follows CxG standard field names, extended using
CAP/HCA double-dash convention for multi-level CSV output:

| Field | Content | When present |
|-------|---------|--------------|
| `cell_type_ontology_term_id` | Most specific CL CURIE (IC-ranked best, or CL exact if available) | Always |
| `cell_type` | Label for above | Always |
| `cell_type_pcl_ontology_term_id` | PCL exact match CURIE | Only when exact match is PCL (omitted when exact is already CL — adding it would be redundant and confusing) |
| `cell_type_pcl` | PCL label | Only when exact match is PCL |
| `cell_type_cl_broad_ontology_term_ids` | All CL broad CURIEs, `\|`-joined in CSV / list in JSON/h5ad | Only when exact match is PCL |

For multi-level CSV (class / subclass / supertype / cluster), each field is
prefixed with the level name and a double dash (CAP/HCA convention):

```
cluster--cell_type_ontology_term_id
cluster--cell_type
cluster--cell_type_pcl_ontology_term_id        ← only when PCL exact
cluster--cell_type_pcl                         ← only when PCL exact
cluster--cell_type_cl_broad_ontology_term_ids  ← only when PCL exact
subclass--cell_type_ontology_term_id
subclass--cell_type
...
```

The h5ad / CxG single-level output uses the unprefixed names directly in `obs`.

> **Note:** The initial MVP implementation used `{level}_cl_exact`, `{level}_cl_label`,
> `{level}_cl_broad` as column names. These are superseded by the CAP/HCA schema
> above and will be updated in the Phase 4 release (breaking change, before any
> stable release).

**CLI:**

```bash
mapmycells2cl annotate input.csv -o output.csv
mapmycells2cl annotate input.json -o output.json
```

### Phase 4: Post-MVP — most-specific CL term via Information Content

When a PCL exact match has multiple CL broad matches (polyhierarchy), there is currently no principled way to select the single "best" CL term. The output exposes all of them, leaving the choice to the user. This phase adds IC-based ranking to identify the most specific informative CL term.

**Problem:** Given a PCL cluster with broad matches `[CL:4023017, CL:4023069]`, one term may be a highly specific interneuron type while the other is a broad regional classification. A user wanting a single annotation needs a way to pick the more informative one.

**Proposed approach — Information Content (IC):**

IC quantifies specificity from the ontology graph structure. More specific (lower in the hierarchy, fewer descendants) terms have higher IC.

Two IC formulations to explore:

- **Structure-based IC** (no corpus needed): `IC(c) = -log( desc(c) / |leaves| )` where `desc(c)` is the number of leaf descendants of `c`. Computable directly from CL without external data.
- **Annotation-based IC**: weighted by how many annotated cells use the term in a reference corpus. More biologically grounded but requires a reference dataset.

For an initial implementation, structure-based IC over **CL alone** is the right starting point.

**Why CL alone, not PCL:**

PCL has two properties that distort IC calculations:

1. **Uneven coverage** — ABA taxonomy coverage in PCL is dense in some brain regions and sparse in others. IC computed over a graph with thousands of nodes in one subtree and few in another will artificially inflate specificity scores for the well-covered areas.
2. **Potential redundancy** — PCL contains provisional terms that may partially overlap in meaning before formal CL curation. This could make some subtrees artificially deep.

CL alone gives a cleaner, more stable base for IC. PCL terms are then mapped to their CL ancestors for scoring.

**Output:** Phase 4 delivers the `cell_type_ontology_term_id` field defined in
the Phase 3 schema — it was left as a placeholder in the MVP because IC
selection was not yet implemented. Phase 4 completes that field and renames
the legacy `{level}_cl_*` columns to the CAP/HCA double-dash convention.

The IC score is stored in `mapping.json` at generation time (pre-computed,
version-locked) so no runtime CL dependency is needed.

**Experiments to run (`experiments/`) before implementing:**

1. Compute structure-based IC over CL alone; inspect distribution across cell type subtrees.
2. For a sample of PCL clusters with multiple CL broad matches, compare the IC-ranked "best" term against biological intuition (e.g. for Sst interneuron clusters, does IC select the interneuron-type term over the broader regional term?).
3. Evaluate whether IC differs meaningfully between the two available CL graphs (full CL vs CL without PCL imports).
4. Consider whether IC should be pre-computed and stored in `mapping.json` (fast lookup, version-locked) or computed on the fly from CL at runtime (always current, adds CL as a dependency).

**Critique / risks:**

- Structure-based IC is sensitive to ontology size and how "complete" a subtree is — CL cell type coverage is itself uneven in some areas.
- Annotation-based IC would be more robust but requires agreeing on a reference corpus; this is worth revisiting post-MVP once the tool is in use.
- "Most specific" is not always "most useful" — a highly specific term in a poorly curated subtree may be less informative than a slightly less specific but well-established term. May need a confidence threshold.

### Phase 5: Post-MVP — h5ad support (CELLxGENE schema compliant)

Add support for annotating h5ad files, with output that conforms to the [CELLxGENE schema](https://github.com/chanzuckerberg/single-cell-curation/blob/main/schema/5.2.0/schema.md) for cell type annotation so that annotated datasets can be submitted directly to CZ CELLxGENE Discover.

**CELLxGENE schema requirements for cell type annotation (`obs` columns):**

- `cell_type_ontology_term_id` — a valid CL CURIE (must be CL, not PCL). Required. Unprefixed.
- `cell_type` — human-readable label for the above. Required. Unprefixed.
- PCL CURIEs are forbidden in `cell_type_ontology_term_id` — IC-based best-CL selection (Phase 4) is therefore a hard prerequisite.

**obs column layout for h5ad output:**

The CxG-required unprefixed pair is always written and always carries the
single winning CL term. This is the cluster-level best CL (finest ABA
taxonomy level), which is also the most specific CL across all levels.
All other levels and provenance fields sit alongside it in prefixed columns.

```
# CxG required — unprefixed, single winning CL term (cluster level)
cell_type_ontology_term_id    CL:4023017
cell_type                     sst GABAergic interneuron

# Per-level annotations — CAP/HCA double-dash prefix
cluster--cell_type_ontology_term_id        CL:4023017
cluster--cell_type                         sst GABAergic interneuron
cluster--cell_type_pcl_ontology_term_id    PCL:0113148   ← only when PCL exact
cluster--cell_type_pcl                     Sst Gaba_3 Chrnb3 ...
cluster--cell_type_cl_broad_ontology_term_ids  CL:4023017|CL:4023069

supertype--cell_type_ontology_term_id      CL:4023017
supertype--cell_type                       sst GABAergic interneuron
supertype--cell_type_pcl_ontology_term_id  PCL:0110786   ← only when PCL exact
...

subclass--cell_type_ontology_term_id       CL:4023017
...

class--cell_type_ontology_term_id          CL:4023069
...
```

**Mapping strategy for `cell_type_ontology_term_id`:**

| Exact match type | Value written | Source |
|------------------|---------------|--------|
| CL exact match | exact CL CURIE | Phase 1 |
| PCL exact match with CL broad matches | highest-IC CL broad match | Phase 4 |
| PCL exact match, no CL broad match | `CL:0000000` (cell) + warning | fallback |

**Implementation:**

1. Read h5ad with `anndata`.
2. For each cell, look up ABA taxonomy IDs from MapMyCells obs columns.
3. Write the unprefixed CxG pair (`cell_type_ontology_term_id`, `cell_type`) using the cluster-level best CL.
4. Write prefixed per-level columns for all taxonomy levels, including PCL and broad fields where applicable.
5. Validate against the CxG schema with `cellxgene-schema` if available.
6. Write annotated h5ad.

**Dependency note:** Requires `anndata` (runtime) and optionally `cellxgene-schema` (validation). Both are optional extras to keep the base install light:

```bash
pip install mapmycells2cl[h5ad]          # adds anndata
pip install mapmycells2cl[h5ad,validate] # adds anndata + cellxgene-schema
```

**CLI:**

```bash
mapmycells2cl annotate input.h5ad -o output.h5ad
mapmycells2cl annotate input.h5ad --validate   # run CxG schema validator after writing
```

**Critique / risks:**

- CxG schema evolves — pin the target schema version and document it.
- Phase 4 (IC selection) is a hard prerequisite: without a principled "best CL" selection, PCL-only exact matches cannot be validly written to `cell_type_ontology_term_id`.
- `CL:0000000` fallback is schema-valid but semantically uninformative; warn loudly and report which ABA IDs triggered it.

### Phase 6: Post-MVP — mapping regeneration CLI

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
