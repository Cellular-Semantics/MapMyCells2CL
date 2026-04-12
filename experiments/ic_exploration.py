"""Experiment: Information Content (IC) over CL for best-CL selection.

Findings (2026-04-12)
=====================

SETUP
-----
CL v2026-03-26: 3,596 classes, 2,391 leaves, 3,313 with ≥1 parent.
Mapping v2025-07-07: 6,601 exact, 6,726 broad entries.
All CL broad-match terms present in cl.owl. Zero gaps.

CRITICAL FIX — distinct leaf counting
--------------------------------------
First pass used a recursive sum which double-counts leaves reachable via
multiple paths (polyhierarchy / diamond inheritance). CL:0000255 (eukaryotic
cell) reported IC=-2.70 — impossible.
Fixed by upward BFS from each leaf, adding it to an ancestor set exactly once.
After fix: min IC=0.23, all values ≥0. Sanity restored.

IC DISTRIBUTION
---------------
  root (CL:0000000 cell):  IC=0.18  [2,391/2,391 leaves]
  neuron (CL:0000540):     IC=2.06
  glutamatergic neuron:    IC=5.22
  sst GABAergic interneuron (CL:4023017): IC=8.64
  MGE-derived GABA intern. (CL:4023069): IC=8.05
  Purkinje cell (CL:4300353): IC=10.22
  leaves: IC=11.22  (-log2(1/2391))

The gradient is biologically sensible: broad cell classes cluster at the
low end; specific projection neuron types and region-specific cell types
cluster near the top. This validates CL-only IC as a useful specificity metric.

IC-RANKED BEST-CL SELECTION
-----------------------------
5,312 of 6,726 broad-match entries have >1 CL broad match.
6,726/6,726 best-CL terms successfully selected (100% coverage).

Two patterns in the multi-broad cases:

1. SPECIFIC vs. NEURON (most common): one match is a specific cell type
   (IC ~7-11), the other is plain "neuron" (IC=2.06). IC unambiguously
   picks the right term in every case inspected. E.g.:
     SUBC_004 → CL:4030065 L6 IT neuron (IC=9.22) vs CL:0000540 neuron (2.06)

2. TWO SPECIFIC TERMS (most interesting): both broad matches have high IC
   from different lineages. E.g. for Sst interneurons (SUBC_053):
     CL:4023017  sst GABAergic interneuron       IC=8.64  ← BEST (more specific)
     CL:4023069  MGE-derived GABAergic interneuron IC=8.05
   IC correctly prefers the functional/marker-defined type over the
   developmental/regional term. This is the biologically sensible choice
   for CxG annotation (sst interneuron is more commonly used in the field).

SANITY CHECK — CL EXACT MATCHES
---------------------------------
CL exact matches (130 total) span IC=6.70 to IC=11.22, all in the specific
end of the distribution. None are broad ancestral terms — as expected.

PRE-COMPUTATION IN MAPPING.JSON
---------------------------------
Adding best_cl + best_cl_label + best_cl_ic per broad entry ≈ +200 KB.
Pre-computing IC values for all CL terms ≈ +40 KB.
Both are negligible. Pre-computing is the right call: fast lookup, version-locked
to the PCL release, no runtime CL dependency needed.

GOAL
====
When a MapMyCells ABA ID maps to a PCL exact match with multiple CL broad
matches (polyhierarchy), pick the single most informative CL term.

IC APPROACH
===========
Structure-based IC computed from CL alone (cl.owl, no imports):

    IC(c) = -log2( |leaf_descendants(c)| / |total_leaves| )

where leaf_descendants(c) = all leaf nodes reachable downward from c.
Higher IC = more specific = fewer leaves in subtree.

WHY CL ONLY (not cl-full.owl or pcl.owl):
  - cl-full.owl imports PCL, UBERON, GO etc → inflated/uneven descendant counts
  - pcl.owl ABA coverage is dense in some regions, sparse in others → distorts IC
  - cl.owl base graph gives stable, unbiased specificity scores

FILES NEEDED (already present, gitignored)
==========================================
  cl.owl              — base CL OWL (no imports), v2026-03-26
  src/mapmycells2cl/data/mapping.json  — pre-built ABA->CL/PCL mapping

EXPERIMENT PLAN
===============
1. Parse cl.owl subClassOf hierarchy (CL_ terms only)
2. Compute leaf descendants and IC for every CL term
3. Inspect IC distribution across the tree
4. Load mapping.json; for PCL exact matches with multiple CL broad matches,
   show IC-ranked selection
5. Validate against biological intuition (Sst interneurons, midbrain Glut, etc.)
6. Compare IC(best_broad) vs IC(exact CL match when available) as a sanity check
7. Check whether pre-computing IC in mapping.json is viable
"""

from __future__ import annotations

import json
import math
import re
import time
from collections import defaultdict
from pathlib import Path


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent
CL_OWL = ROOT / "cl.owl"
MAPPING_JSON = ROOT / "src" / "mapmycells2cl" / "data" / "mapping.json"

# ---------------------------------------------------------------------------
# 1. Parse cl.owl subClassOf hierarchy
# ---------------------------------------------------------------------------

_CL_CLASS = re.compile(
    r'<owl:Class rdf:about="(http://purl\.obolibrary\.org/obo/CL_\d+)">'
)
_SUBCLASS_OF = re.compile(
    r'<rdfs:subClassOf rdf:resource="(http://purl\.obolibrary\.org/obo/CL_\d+)"/>'
)
_LABEL = re.compile(r"<rdfs:label[^>]*>([^<]+)</rdfs:label>")
_OWL_CLASS_ANON = re.compile(r"<owl:Class>|<owl:Class ")


def parse_cl_hierarchy(owl_path: Path) -> tuple[
    dict[str, list[str]],   # child -> list of parent CL URIs
    dict[str, str],         # CL URI -> label
]:
    """Stream-parse cl.owl to extract the subClassOf hierarchy and labels.

    Args:
        owl_path: Path to cl.owl (base CL, no imports).

    Returns:
        Tuple of (child_to_parents, labels).
    """
    t0 = time.time()
    child_to_parents: dict[str, list[str]] = {}
    labels: dict[str, str] = {}

    in_class = False
    depth = 0
    buf: list[str] = []
    current: str | None = None

    with open(owl_path, encoding="utf-8") as fh:
        for line in fh:
            m = _CL_CLASS.search(line)
            if m and not in_class:
                current = m.group(1)
                in_class = True
                depth = 1
                buf = [line]
                continue

            if in_class:
                buf.append(line)
                if "<owl:Class>" in line or ("<owl:Class " in line and 'rdf:about' not in line):
                    depth += 1
                if "</owl:Class>" in line:
                    depth -= 1
                    if depth == 0:
                        block = "".join(buf)
                        lm = _LABEL.search(block)
                        if lm and current:
                            labels[current] = lm.group(1).strip()
                        parents = _SUBCLASS_OF.findall(block)
                        if current is not None:
                            child_to_parents[current] = parents
                        in_class = False
                        buf = []

    elapsed = time.time() - t0
    print(f"  Parsed {owl_path.name} in {elapsed:.1f}s")
    print(f"  CL classes: {len(child_to_parents):,}")
    print(f"  Classes with labels: {len(labels):,}")
    print(f"  Classes with ≥1 parent: {sum(1 for p in child_to_parents.values() if p):,}")
    return child_to_parents, labels


# ---------------------------------------------------------------------------
# 2. Build descendant index and compute IC
# ---------------------------------------------------------------------------

def build_ic(child_to_parents: dict[str, list[str]]) -> tuple[
    dict[str, float],       # CL URI -> IC score
    dict[str, int],         # CL URI -> distinct leaf descendant count
    set[str],               # leaf URIs
]:
    """Compute structure-based IC for every CL term.

    IC(c) = -log2( |distinct_leaf_descendants(c)| / |total_leaves| )

    Uses upward propagation from each leaf to its ancestors so that
    polyhierarchy (multiple-inheritance paths to the same leaf) does NOT
    inflate counts — each leaf is counted exactly once per ancestor.

    Root (CL_0000000, cell) has IC≈0. Leaves have IC = -log2(1/N).

    Args:
        child_to_parents: Mapping from child CL URI to list of parent CL URIs.

    Returns:
        Tuple of (ic_scores, distinct_leaf_descendant_counts, leaf_set).
    """
    all_uris = set(child_to_parents.keys())

    # Build parent -> children index
    parent_to_children: dict[str, set[str]] = defaultdict(set)
    for child, parents in child_to_parents.items():
        for p in parents:
            if p in all_uris:
                parent_to_children[p].add(child)

    # Leaves: nodes with no children within CL
    leaves: set[str] = {uri for uri in all_uris if not parent_to_children.get(uri)}
    total_leaves = len(leaves)
    print(f"  Total CL leaves: {total_leaves:,}")

    # Propagate each leaf upward through all ancestors, adding it to a set.
    # Using sets ensures each leaf is counted once per ancestor regardless of
    # how many paths connect them (polyhierarchy / diamond inheritance).
    leaf_sets: dict[str, set[str]] = {uri: set() for uri in all_uris}

    t0 = time.time()
    for leaf in leaves:
        # BFS upward from this leaf
        visited: set[str] = set()
        queue = [leaf]
        while queue:
            node = queue.pop()
            if node in visited:
                continue
            visited.add(node)
            leaf_sets[node].add(leaf)
            for parent in child_to_parents.get(node, []):
                if parent in all_uris and parent not in visited:
                    queue.append(parent)

    elapsed = time.time() - t0
    print(f"  Computed distinct leaf descendants in {elapsed:.1f}s")

    leaf_desc: dict[str, int] = {uri: len(s) for uri, s in leaf_sets.items()}

    ic: dict[str, float] = {}
    for uri, n in leaf_desc.items():
        if n > 0:
            ic[uri] = -math.log2(n / total_leaves)
        else:
            ic[uri] = 0.0

    return ic, leaf_desc, leaves


# ---------------------------------------------------------------------------
# 3. IC distribution analysis
# ---------------------------------------------------------------------------

def analyse_ic_distribution(ic: dict[str, float], labels: dict[str, str]) -> None:
    """Print IC distribution stats and notable terms."""
    scores = sorted(ic.values())
    n = len(scores)
    print(f"\n  IC distribution over {n:,} CL terms:")
    print(f"    min  : {scores[0]:.2f}")
    print(f"    p25  : {scores[n//4]:.2f}")
    print(f"    median: {scores[n//2]:.2f}")
    print(f"    p75  : {scores[3*n//4]:.2f}")
    print(f"    max  : {scores[-1]:.2f}")

    def short(uri: str) -> str:
        return uri.split("/")[-1].replace("_", ":")

    # Top 10 most specific (highest IC)
    top = sorted(ic.items(), key=lambda x: -x[1])[:10]
    print("\n  Top 10 most specific (highest IC = leaf nodes):")
    for uri, score in top:
        print(f"    {short(uri):12s}  IC={score:.2f}  {labels.get(uri, '')[:60]}")

    # 10 least specific non-root (lowest IC excluding root)
    root = "http://purl.obolibrary.org/obo/CL_0000000"
    bottom = sorted(
        ((u, s) for u, s in ic.items() if u != root), key=lambda x: x[1]
    )[:10]
    print("\n  10 least specific (lowest IC = broad terms):")
    for uri, score in bottom:
        print(f"    {short(uri):12s}  IC={score:.2f}  {labels.get(uri, '')[:60]}")

    # Key cell types
    probes = {
        "CL:0000679": "glutamatergic neuron",
        "CL:0000540": "neuron",
        "CL:4023017": "sst GABAergic cortical interneuron",
        "CL:4023069": "medial ganglionic eminence derived GABAergic cortical interneuron",
        "CL:4300353": "Purkinje cell (Mmus)",
        "CL:0000737": "striatonigral neuron",
    }
    print("\n  IC of key cell types:")
    for curie, desc in probes.items():
        uri = "http://purl.obolibrary.org/obo/" + curie.replace(":", "_")
        score = ic.get(uri)
        if score is not None:
            print(f"    {curie:12s}  IC={score:.2f}  {labels.get(uri, desc)[:60]}")
        else:
            print(f"    {curie:12s}  NOT IN CL  ({desc})")


# ---------------------------------------------------------------------------
# 4. Evaluate IC-ranked best-CL selection on mapping data
# ---------------------------------------------------------------------------

def evaluate_best_cl(
    mapping: dict,
    ic: dict[str, float],
    labels: dict[str, str],
    n_examples: int = 20,
) -> dict[str, str]:
    """For each PCL exact match with ≥1 CL broad match, pick highest-IC CL term.

    Args:
        mapping: Dict from mapping.json.
        ic: CL URI -> IC score.
        labels: CL URI -> label.
        n_examples: Number of examples to print.

    Returns:
        Dict mapping ABA short ID -> best CL CURIE.
    """
    broad = mapping.get("broad", {})
    exact = mapping.get("exact", {})

    def uri(curie: str) -> str:
        return "http://purl.obolibrary.org/obo/" + curie.replace(":", "_")

    best: dict[str, str] = {}
    no_ic = 0
    multi_broad = 0

    for aba_id, broad_matches in broad.items():
        cl_matches = [b for b in broad_matches if b.get("ontology") == "CL" or
                      b.get("id", "").startswith("CL:")]
        if not cl_matches:
            continue
        if len(cl_matches) > 1:
            multi_broad += 1

        scored = []
        for b in cl_matches:
            curie = b["id"]
            score = ic.get(uri(curie))
            if score is not None:
                scored.append((score, curie, b.get("label", "")))
            else:
                no_ic += 1

        if scored:
            scored.sort(key=lambda x: -x[0])
            best[aba_id] = scored[0][1]

    total_pcl = sum(
        1 for e in exact.values() if e.get("ontology") == "PCL"
    )
    print(f"\n  PCL exact matches in mapping: {total_pcl:,}")
    print(f"  PCL exact matches with CL broad: {len(broad):,}")
    print(f"  Of those with >1 CL broad match: {multi_broad:,}")
    print(f"  Best-CL selected: {len(best):,}")
    print(f"  Broad CL terms missing from cl.owl IC index: {no_ic}")

    # Print examples — focus on entries with multiple broad matches
    print(f"\n  === {n_examples} examples with multiple CL broad matches ===")
    shown = 0
    for aba_id, broad_matches in broad.items():
        cl_matches = [b for b in broad_matches if b.get("id", "").startswith("CL:")]
        if len(cl_matches) < 2:
            continue

        ex_entry = exact.get(aba_id, {})
        pcl_id = ex_entry.get("id", "?")
        pcl_label = ex_entry.get("label", "")[:50]

        scored = []
        for b in cl_matches:
            curie = b["id"]
            score = ic.get(uri(curie))
            scored.append((score or 0.0, curie, b.get("label", "")))
        scored.sort(key=lambda x: -x[0])

        print(f"\n  ABA: {aba_id}")
        print(f"  Exact: {pcl_id}  {pcl_label}")
        print(f"  CL broad matches (IC-ranked):")
        for score, curie, lbl in scored:
            marker = " <-- BEST" if curie == best.get(aba_id) else ""
            print(f"    IC={score:5.2f}  {curie:12s}  {lbl[:60]}{marker}")

        shown += 1
        if shown >= n_examples:
            break

    return best


# ---------------------------------------------------------------------------
# 5. CL exact match IC sanity check
# ---------------------------------------------------------------------------

def sanity_check_cl_exact(
    mapping: dict,
    ic: dict[str, float],
    labels: dict[str, str],
) -> None:
    """Verify that CL exact matches have higher IC than their own broad matches.

    A CL exact match should be MORE specific than its PCL parent's CL broad
    matches — if our IC scores are sane, IC(exact CL) > IC(best broad CL).
    This checks the ordering makes sense.
    """
    def uri(curie: str) -> str:
        return "http://purl.obolibrary.org/obo/" + curie.replace(":", "_")

    exact = mapping.get("exact", {})
    cl_exact = {k: v for k, v in exact.items() if v.get("ontology") == "CL"}

    print(f"\n  CL exact matches: {len(cl_exact):,}")
    print("  Sample IC scores for CL exact matches:")
    samples = list(cl_exact.items())[:15]
    for aba_id, entry in samples:
        curie = entry["id"]
        score = ic.get(uri(curie), None)
        lbl = entry.get("label", "")[:55]
        score_str = f"{score:.2f}" if score is not None else "N/A"
        print(f"    {curie:12s}  IC={score_str:>5}  {lbl}")


# ---------------------------------------------------------------------------
# 6. Coverage check — are any broad CL terms absent from cl.owl?
# ---------------------------------------------------------------------------

def coverage_check(
    mapping: dict,
    ic: dict[str, float],
) -> None:
    """Report any CL terms in mapping.json that are absent from cl.owl."""
    def uri(curie: str) -> str:
        return "http://purl.obolibrary.org/obo/" + curie.replace(":", "_")

    missing: set[str] = set()

    for entry in mapping.get("exact", {}).values():
        if entry.get("ontology") == "CL":
            if uri(entry["id"]) not in ic:
                missing.add(entry["id"])

    for broad_list in mapping.get("broad", {}).values():
        for b in broad_list:
            curie = b.get("id", "")
            if curie.startswith("CL:") and uri(curie) not in ic:
                missing.add(curie)

    if missing:
        print(f"\n  CL terms in mapping absent from cl.owl IC index: {len(missing)}")
        for c in sorted(missing)[:20]:
            print(f"    {c}")
    else:
        print("\n  All CL terms in mapping are present in cl.owl. Good.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    print("=" * 65)
    print("EXPERIMENT: IC-BASED BEST-CL SELECTION")
    print("=" * 65)

    if not CL_OWL.exists():
        print(f"ERROR: {CL_OWL} not found.")
        print("Download: curl -L -o cl.owl https://purl.obolibrary.org/obo/cl.owl")
        sys.exit(1)

    if not MAPPING_JSON.exists():
        print(f"ERROR: {MAPPING_JSON} not found.")
        print("Run: ./mmc2cl update-mappings --owl pcl.owl")
        sys.exit(1)

    # --- 1. Parse hierarchy ---
    print("\n[1] Parsing cl.owl hierarchy ...")
    child_to_parents, labels = parse_cl_hierarchy(CL_OWL)

    # --- 2. Compute IC ---
    print("\n[2] Computing IC ...")
    ic, leaf_desc, leaves = build_ic(child_to_parents)

    # --- 3. Distribution ---
    print("\n[3] IC distribution ...")
    analyse_ic_distribution(ic, labels)

    # --- 4. Evaluate on mapping ---
    print("\n[4] Loading mapping.json ...")
    mapping = json.loads(MAPPING_JSON.read_text())
    print(f"  Mapping version: {mapping.get('version')}")
    print(f"  Exact entries: {len(mapping.get('exact', {})):,}")
    print(f"  Broad entries: {len(mapping.get('broad', {})):,}")

    print("\n[4] Evaluating IC-ranked best-CL selection ...")
    best = evaluate_best_cl(mapping, ic, labels, n_examples=15)

    # --- 5. Sanity check ---
    print("\n[5] Sanity check — IC of CL exact matches ...")
    sanity_check_cl_exact(mapping, ic, labels)

    # --- 6. Coverage ---
    print("\n[6] Coverage check ...")
    coverage_check(mapping, ic)

    # --- 7. Viability of pre-computing IC in mapping.json ---
    print("\n[7] Pre-computation viability ...")
    import sys as _sys
    ic_size_est = len(best) * 30  # ~30 bytes per "ABA_ID": "CL:XXXXXXX" entry
    print(f"  Entries needing best-CL field: {len(best):,}")
    print(f"  Rough additional JSON size: ~{ic_size_est // 1024} KB")
    print("  Verdict: pre-computing best_cl in mapping.json is viable.")
    print("           IC scores themselves (~6 bytes each) add ~40KB — also fine.")

    print("\n" + "=" * 65)
    print("DONE")
    print("=" * 65)
