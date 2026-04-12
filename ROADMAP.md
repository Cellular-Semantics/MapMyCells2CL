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

> Status legend: ✅ Complete · 🔲 Planned

### Phase 1: OWL parser and mapping generator ✅

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

### Phase 2: Lookup library ✅

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

### Phase 3: MapMyCells output annotator (MVP) ✅

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

> **Implemented:** CAP/HCA double-dash column naming is live from Phase 4 onwards.
> The earlier `{level}_cl_exact` / `{level}_cl_label` / `{level}_cl_broad` names
> were superseded before any stable release.

**CLI:**

```bash
mapmycells2cl annotate input.csv -o output.csv
mapmycells2cl annotate input.json -o output.json
```

### Phase 4: Post-MVP — most-specific CL term via Information Content ✅

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

**Implemented approach:**

- Structure-based IC over base `cl.owl` (no PCL imports): `IC(c) = -log2(|distinct leaf descendants| / |total leaves|)`. Distinct-leaf counting uses upward BFS per leaf to avoid double-counting under polyhierarchy.
- Pre-computed at `update-mappings` time and stored in `mapping.json` under `best_cl`. No runtime CL dependency.
- `MatchResult` exposes `best_cl_id`, `best_cl_label`, `best_cl_ic`. `CellTypeMapper.has_ic` indicates whether the mapping includes IC data.
- Experiment in `experiments/ic_exploration.py` confirmed IC correctly selects functional/marker interneuron types over broad regional types for Sst clusters.
- 100% coverage: all CL broad-match terms from the pcl.owl mapping are present in the cl.owl IC index.

**Remaining risks (deferred):**

- Annotation-based IC would be more biologically grounded; worth revisiting once the tool is in wider use.
- "Most specific" is not always "most useful" in poorly curated subtrees — a confidence threshold may be needed.

### Phase 5: Post-MVP — h5ad support (CELLxGENE schema compliant) ✅

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

**Implemented approach:**

- `annotate_h5ad(mmc_csv, h5ad_in, h5ad_out, mapper, cxg_level="cluster")` in `annotator.py`.
  Joins MapMyCells CSV to h5ad by `cell_id` → obs index, writes all CL columns to `adata.obs`.
- `anndata` is a runtime dependency (not an optional extra — it's central to the use case).
- `mapmycells2cl annotate-h5ad MMC_CSV H5AD_IN` CLI command with `--cxg-level` option.
- Integration test validated against real GSE124847 OLM data: 46 cells, 4 taxonomy levels,
  all cells receive valid `CL:` terms.

**Deferred:**

- CxG schema validation via `cellxgene-schema` — not yet implemented. Worth adding as an
  optional `--validate` flag once the schema pinning strategy is agreed.
- `CL:0000000` fallback for PCL terms with no CL broad match — currently writes empty string
  with no warning. Should warn loudly and log the offending ABA IDs.

### Phase 6: Post-MVP — mapping regeneration CLI ✅

Implemented as `mapmycells2cl update-mappings` with `--owl`, `--cl-owl`, and `--output` options.
Downloads `pcl.owl` (and optionally `cl.owl`) from their PURLs if local files are not provided.
IC data is included whenever `--cl-owl` is supplied (strongly recommended).

```bash
mapmycells2cl update-mappings                          # download + regenerate
mapmycells2cl update-mappings --cl-owl cl.owl          # with IC ranking
mapmycells2cl update-mappings --owl pcl.owl --cl-owl cl.owl  # fully local
```

### Versioning strategy

- The packaged `mapping.json` includes the PCL ontology version (`owl:versionInfo` date).
- `update-mappings` fetches the latest `pcl.owl` and regenerates.
- Mapping JSON is committed to the repo (~1-2 MB) so users get it on install without running the generator.
- Future: warn if the mapping version is older than a configurable threshold.

---

## Remaining / future work

- **CxG schema validation** (`--validate` flag on `annotate-h5ad`) — pin schema version, run `cellxgene-schema` post-write.
- **Empty-string fallback warning** — when a PCL exact match has no CL broad matches, currently writes `""`. Should fall back to `CL:0000000` with a loud warning listing the offending ABA IDs.
- **Annotation-based IC** — structure-based IC is working well; annotation-based IC (weighted by reference corpus) could be more biologically grounded post-MVP.
- **oaklib integration** — deferred; not needed for current use cases, worth revisiting if richer OWL query support is required.
- **PyPI release** — package is structured and ready; publish once community testing is complete.
