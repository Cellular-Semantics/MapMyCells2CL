"""Explore approaches for mapping ABA taxonomy IDs to CL terms.

Findings Summary (2026-04-12)
=============================

MapMyCells outputs taxonomy node assignments with IDs like CS20230722_SUBC_313.
Goal: map these to Cell Ontology (CL) terms, indicating exact and broad matches.

DATA SOURCES TESTED:
  1. cl-full.owl  - Cell Ontology OWL
  2. cl-full.json - Cell Ontology OBO JSON Graph
  3. pcl.owl      - Provisional Cell Ontology OWL
  4. OLS4 API     - EBI Ontology Lookup Service

APPROACH RESULTS:
  - cl-full.json: NOT VIABLE. logicalDefinitionAxioms doesn't capture hasValue
    restrictions (individual fillers). Edges section also lacks RO_0015001 edges.

  - OLS4 API: NOT VIABLE for reverse lookup. Individual 'types' endpoint only
    returns PCL_0010001 (rdf:type). Graph endpoint shows the link but requires
    knowing the CL term first (chicken-and-egg).

  - cl-full.owl: 130 exact CL mappings via equivalentClass + RO_0015001 hasValue.
    Only covers CCN20230722: CLAS(3), SUBC(15), SUPT(32), CLUS(80).

  - pcl.owl (WINNER): 6,471 PCL mappings + 130 CL mappings. Also contains:
    * RO_0015003 on individuals: parent cell set hierarchy (CLUS->SUPT->SUBC->CLAS)
    * RO_0015002 on individuals: reverse link to CL class (6,870 individuals)
    * CLM_0010005: accession ID annotation (6,895 individuals)
    * Full taxonomy hierarchy for broad matching

RECOMMENDED ARCHITECTURE:
  - Parse pcl.owl to build:
    1. ABA_ID -> CL_ID exact match lookup (from equivalentClass on CL terms)
    2. ABA_ID -> PCL_ID lookup (from equivalentClass on PCL terms)
    3. ABA taxonomy hierarchy via RO_0015003 (for walking up to broader matches)
  - Package pre-built lookup as versioned JSON with the library
  - Include tooling to download OWL files and regenerate mappings

OAK (oaklib):
  - Tested v0.6.23 - BROKEN on Python 3.14 (linkml Format.JSON attribute removed)
  - Would provide sqlite:obo:cl adapter for cached local queries
  - Worth revisiting when Python 3.14 compatibility is fixed
  - Key question: does OAK's SQL DB capture the hasValue restrictions?
    (OBO JSON doesn't, so the SQL might not either if derived from same source)
"""

import json
import re
import time
from collections import Counter
from pathlib import Path
from urllib.request import urlopen

OWL_DIR = Path(__file__).parent.parent
CL_OWL = OWL_DIR / "cl-full.owl"
PCL_OWL = OWL_DIR / "pcl.owl"


def extract_equiv_mappings(owl_path: Path) -> dict[str, str]:
    """Extract ABA taxonomy ID -> CL/PCL ID from equivalentClass axioms.

    Scans for pattern:
        <owl:Class rdf:about="...CL_XXXX"> or <owl:Class rdf:about="...PCL_XXXX">
          <owl:equivalentClass>
            ...
            <owl:onProperty rdf:resource="...RO_0015001"/>
            <owl:hasValue rdf:resource="...brain-bican...ABA_ID"/>

    Returns:
        Dict mapping ABA taxonomy URI -> CL/PCL URI
    """
    aba_to_class: dict[str, str] = {}
    in_class = False
    buf = ""
    current_class: str | None = None

    t0 = time.time()
    with open(owl_path) as f:
        for line in f:
            m = re.search(
                r'<owl:Class rdf:about="(http://purl\.obolibrary\.org/obo/(?:CL|PCL)_\d+)">',
                line,
            )
            if m:
                current_class = m.group(1)
                in_class = True
                buf = line
                continue
            if in_class:
                buf += line
                if "</owl:Class>" in line:
                    if "RO_0015001" in buf and "equivalentClass" in buf:
                        for aba_uri in re.findall(
                            r'owl:hasValue rdf:resource="(https://purl\.brain-bican\.org/[^"]+)"',
                            buf,
                        ):
                            aba_to_class[aba_uri] = current_class
                    in_class = False
                    buf = ""

    elapsed = time.time() - t0
    print(f"  Parsed {owl_path.name} in {elapsed:.1f}s -> {len(aba_to_class)} mappings")
    return aba_to_class


def extract_taxonomy_hierarchy(owl_path: Path) -> dict[str, list[str]]:
    """Extract ABA taxonomy hierarchy from PCL individuals via RO_0015003.

    Returns:
        Dict mapping ABA ID (short) -> list of parent ABA IDs (short)
    """
    parent_map: dict[str, list[str]] = {}
    in_ind = False
    buf = ""
    current: str | None = None

    t0 = time.time()
    with open(owl_path) as f:
        for line in f:
            m = re.search(
                r'<owl:NamedIndividual rdf:about="(https://purl\.brain-bican\.org/[^"]+)">', line
            )
            if m:
                current = m.group(1)
                in_ind = True
                buf = line
                continue
            if in_ind:
                buf += line
                if "</owl:NamedIndividual>" in line:
                    parents = re.findall(r'obo:RO_0015003 rdf:resource="([^"]+)"', buf)
                    if parents:
                        short_id = current.split("/")[-1]
                        parent_map[short_id] = [p.split("/")[-1] for p in parents]
                    in_ind = False
                    buf = ""

    elapsed = time.time() - t0
    print(f"  Parsed hierarchy in {elapsed:.1f}s -> {len(parent_map)} parent links")
    return parent_map


def build_broad_match_map(
    exact_map: dict[str, str],
    hierarchy: dict[str, list[str]],
) -> dict[str, str]:
    """For ABA IDs without exact CL matches, walk up hierarchy to find nearest CL match.

    Returns:
        Dict mapping ABA short ID -> nearest ancestor CL URI (or None)
    """
    # Build short_id -> CL URI from exact map
    exact_by_short = {}
    for aba_uri, cl_uri in exact_map.items():
        short = aba_uri.split("/")[-1]
        if "/CL_" in cl_uri:
            exact_by_short[short] = cl_uri

    broad_map: dict[str, str] = {}
    for aba_id in hierarchy:
        if aba_id in exact_by_short:
            continue  # has exact match already
        # Walk up
        visited = {aba_id}
        current = aba_id
        while current in hierarchy:
            parents = hierarchy[current]
            if not parents:
                break
            parent = parents[0]
            if parent in visited:
                break
            visited.add(parent)
            if parent in exact_by_short:
                broad_map[aba_id] = exact_by_short[parent]
                break
            current = parent

    return broad_map


if __name__ == "__main__":
    print("=" * 60)
    print("EXACT MAPPINGS FROM PCL.OWL")
    print("=" * 60)

    if PCL_OWL.exists():
        pcl_mappings = extract_equiv_mappings(PCL_OWL)

        # Split into CL and PCL targets
        cl_exact = {k: v for k, v in pcl_mappings.items() if "/CL_" in v}
        pcl_exact = {k: v for k, v in pcl_mappings.items() if "/PCL_" in v}

        print(f"  -> CL terms: {len(cl_exact)}")
        print(f"  -> PCL terms: {len(pcl_exact)}")

        # By taxonomy level
        for label, mapping in [("CL", cl_exact), ("PCL", pcl_exact)]:
            counts = Counter("_".join(u.split("/")[-1].split("_")[:-1]) for u in mapping)
            print(f"\n  {label} by level:")
            for p, c in sorted(counts.items()):
                print(f"    {p}: {c}")

        print()
        print("=" * 60)
        print("TAXONOMY HIERARCHY FROM PCL.OWL")
        print("=" * 60)
        hierarchy = extract_taxonomy_hierarchy(PCL_OWL)

        # Trace example
        print("\n  Example: CS20230722_CLUS_0001")
        node = "CS20230722_CLUS_0001"
        chain = [node]
        while node in hierarchy:
            node = hierarchy[node][0]
            chain.append(node)
        print(f"    {'  ->  '.join(chain)}")

        print()
        print("=" * 60)
        print("BROAD MATCHES (walk up to nearest CL)")
        print("=" * 60)
        broad = build_broad_match_map(pcl_mappings, hierarchy)
        print(f"  ABA IDs with broad CL match: {len(broad)}")

        # Show examples
        print("\n  Examples:")
        for aba_id, cl_uri in list(broad.items())[:5]:
            cl_id = cl_uri.split("/")[-1]
            # Trace the path
            node = aba_id
            path = [node]
            while node in hierarchy:
                node = hierarchy[node][0]
                path.append(node)
                short_aba = node
                full_uri = f"https://purl.brain-bican.org/taxonomy/CCN20230722/{node}"
                if full_uri in cl_exact:
                    break
            print(f"    {aba_id} ~broad~> {cl_id} (via {'->'.join(path)})")
    else:
        print(f"  pcl.owl not found at {PCL_OWL}")
        print("  Download: curl -L -o pcl.owl http://purl.obolibrary.org/obo/pcl.owl")

    if CL_OWL.exists():
        print()
        print("=" * 60)
        print("COMPARISON: CL.OWL ONLY")
        print("=" * 60)
        cl_mappings = extract_equiv_mappings(CL_OWL)
        print(f"  (PCL has {len(pcl_mappings)} vs CL's {len(cl_mappings)})")
