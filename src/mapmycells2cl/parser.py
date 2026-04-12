"""Parse pcl.owl to extract ABA taxonomy -> CL/PCL mappings.

Parses the Provisional Cell Ontology OWL file using streaming regex to extract:

1. **Exact matches** — ``owl:equivalentClass`` axioms of the form::

       CL/PCL_class ≡ CL_0000000 ∧ (RO_0015001 hasValue <ABA_individual>)

2. **Class labels** — ``rdfs:label`` on CL/PCL classes.

3. **SubClassOf** — ``rdfs:subClassOf`` edges between PCL/CL classes (for broad
   matching).

4. **Individual hierarchy** — ``RO_0015003`` (has_part_of_taxon) on ABA individuals
   giving the parent cell-set (used as a fallback when no subClassOf path exists).

5. **Broad matches** — PCL-only exact matches are walked up the ``subClassOf``
   hierarchy (and individual hierarchy as fallback) to find the nearest CL ancestor.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# URI helpers
# ---------------------------------------------------------------------------

_ABA_BASE = "https://purl.brain-bican.org/taxonomy/"
_CL_PREFIX = "http://purl.obolibrary.org/obo/CL_"
_PCL_PREFIX = "http://purl.obolibrary.org/obo/PCL_"


def _short_cl(uri: str) -> str:
    """Convert CL/PCL URI to CURIE, e.g. ``CL:4300353``."""
    local = uri.split("/")[-1]  # CL_4300353 or PCL_0010001
    return local.replace("_", ":", 1)


def _aba_short(uri: str) -> str:
    """Return the short ABA ID from a full URI, e.g. ``CS20230722_SUBC_313``."""
    return uri.split("/")[-1]


def _is_cl(uri: str) -> bool:
    return uri.startswith(_CL_PREFIX)


def _is_pcl(uri: str) -> bool:
    return uri.startswith(_PCL_PREFIX)


def _is_aba(uri: str) -> bool:
    return uri.startswith(_ABA_BASE)


# ---------------------------------------------------------------------------
# Streaming block parser
# ---------------------------------------------------------------------------

_CLASS_START = re.compile(
    r'<owl:Class rdf:about="(http://purl\.obolibrary\.org/obo/(?:CL|PCL)_\d+)">'
)
_IND_START = re.compile(
    r'<owl:NamedIndividual rdf:about="(https://purl\.brain-bican\.org/[^"]+)">'
)
_EQUIV_RO = re.compile(
    r'<owl:onProperty rdf:resource="[^"]*RO_0015001"/>'
)
_HAS_VALUE = re.compile(
    r'<owl:hasValue rdf:resource="(https://purl\.brain-bican\.org/[^"]+)"/>'
)
_LABEL = re.compile(r"<rdfs:label[^>]*>([^<]+)</rdfs:label>")
_SUBCLASS = re.compile(
    r'<rdfs:subClassOf rdf:resource="(http://purl\.obolibrary\.org/obo/(?:CL|PCL)_\d+)"/>'
)
_RO_0015003 = re.compile(
    r'obo:RO_0015003 rdf:resource="(https://purl\.brain-bican\.org/[^"]+)"'
)
_VERSION = re.compile(r"<owl:versionInfo>([^<]+)</owl:versionInfo>")


def _iter_blocks(owl_path: Path) -> tuple[
    dict[str, str],         # aba_uri -> cl/pcl uri (exact matches)
    dict[str, str],         # cl/pcl uri -> label
    dict[str, list[str]],   # cl/pcl uri -> list of superclass uris
    dict[str, list[str]],   # aba short_id -> list of parent aba short_ids
    str,                    # ontology version string
]:
    """Stream-parse pcl.owl into the core data structures.

    Args:
        owl_path: Path to the OWL file (RDF/XML serialisation).

    Returns:
        Tuple of (exact_map, labels, subclass_map, ind_hierarchy, version).
    """
    exact_map: dict[str, str] = {}
    labels: dict[str, str] = {}
    subclass_map: dict[str, list[str]] = {}
    ind_hierarchy: dict[str, list[str]] = {}
    version = "unknown"

    in_class = False
    class_depth = 0  # nesting depth of <owl:Class> within an outer named class block
    in_ind = False
    buf: list[str] = []
    current_class: str | None = None
    current_ind: str | None = None

    with open(owl_path, encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line

            # Extract version (appears in <owl:Ontology> block near top)
            if not in_class and not in_ind:
                vm = _VERSION.search(line)
                if vm:
                    version = vm.group(1).strip()

            # --- owl:Class blocks ---
            cm = _CLASS_START.search(line)
            if cm and not in_class and not in_ind:
                current_class = cm.group(1)
                in_class = True
                class_depth = 1
                buf = [line]
                continue

            if in_class:
                buf.append(line)
                # Track anonymous inner <owl:Class> elements (no rdf:about)
                if "<owl:Class>" in line or "<owl:Class " in line:
                    class_depth += 1
                if "</owl:Class>" in line:
                    class_depth -= 1
                    if class_depth == 0:
                        block = "".join(buf)
                        # Label
                        lm = _LABEL.search(block)
                        if lm and current_class:
                            labels[current_class] = lm.group(1).strip()
                        # Exact match via equivalentClass + RO_0015001
                        if _EQUIV_RO.search(block) and "equivalentClass" in block:
                            hv = _HAS_VALUE.findall(block)
                            for aba_uri in hv:
                                if _is_aba(aba_uri) and current_class:
                                    exact_map[aba_uri] = current_class
                        # subClassOf named class
                        if current_class:
                            parents = _SUBCLASS.findall(block)
                            if parents:
                                subclass_map[current_class] = parents
                        in_class = False
                        buf = []
                continue

            # --- owl:NamedIndividual blocks ---
            im = _IND_START.search(line)
            if im and not in_ind:
                current_ind = im.group(1)
                in_ind = True
                buf = [line]
                continue

            if in_ind:
                buf.append(line)
                if "</owl:NamedIndividual>" in line:
                    block = "".join(buf)
                    parents_aba = _RO_0015003.findall(block)
                    if parents_aba and current_ind:
                        short = _aba_short(current_ind)
                        ind_hierarchy[short] = [_aba_short(p) for p in parents_aba]
                    in_ind = False
                    buf = []

    return exact_map, labels, subclass_map, ind_hierarchy, version


# ---------------------------------------------------------------------------
# Broad-match computation
# ---------------------------------------------------------------------------

def _compute_broad_matches(
    exact_map: dict[str, str],
    labels: dict[str, str],
    subclass_map: dict[str, list[str]],
    ind_hierarchy: dict[str, list[str]],
) -> dict[str, list[dict[str, Any]]]:
    """For each PCL exact match, walk subClassOf to find CL ancestors.

    Falls back to the individual hierarchy (RO_0015003) for nodes without
    subClassOf edges.

    Args:
        exact_map: ABA URI -> CL/PCL URI.
        labels: CL/PCL URI -> label.
        subclass_map: CL/PCL URI -> list of direct superclass URIs.
        ind_hierarchy: ABA short ID -> list of parent ABA short IDs.

    Returns:
        Dict mapping ABA short ID -> list of broad-match dicts
        (id, label, ontology, via).  Only entries for PCL exact matches
        that have at least one CL ancestor are included.
    """
    # Build reverse: aba short -> cl/pcl uri (all exact matches)
    short_to_uri: dict[str, str] = {_aba_short(k): v for k, v in exact_map.items()}

    broad: dict[str, list[dict[str, Any]]] = {}

    # Broad matches for PCL exact-match terms (no subClassOf CL)
    for aba_uri, target_uri in exact_map.items():
        if _is_cl(target_uri):
            continue  # already a CL term — no broad match needed

        aba_short = _aba_short(aba_uri)
        cl_ancestors = _cl_ancestors_via_subclass(target_uri, subclass_map, labels)

        if not cl_ancestors:
            # Fallback: walk individual hierarchy to find ancestor with CL exact match
            cl_ancestors = _cl_ancestors_via_individual(
                aba_short, ind_hierarchy, short_to_uri, subclass_map, labels
            )

        if cl_ancestors:
            broad[aba_short] = cl_ancestors

    # Broad matches for ABA IDs that have NO exact match at all — walk individual
    # hierarchy to the nearest ancestor that does have a CL exact match.
    for aba_short in ind_hierarchy:
        if aba_short in broad:
            continue  # already handled above
        if aba_short in short_to_uri:
            continue  # has an exact match (CL or PCL) — handled above
        cl_ancestors = _cl_ancestors_via_individual(
            aba_short, ind_hierarchy, short_to_uri, subclass_map, labels
        )
        if cl_ancestors:
            broad[aba_short] = cl_ancestors

    return broad


def _cl_ancestors_via_subclass(
    start_uri: str,
    subclass_map: dict[str, list[str]],
    labels: dict[str, str],
) -> list[dict[str, Any]]:
    """Walk subClassOf from *start_uri* and collect all CL URIs reached.

    Args:
        start_uri: URI of a PCL class.
        subclass_map: Direct superclass edges.
        labels: URI -> label.

    Returns:
        List of CL ancestor dicts with keys id, label, ontology, via.
    """
    visited: set[str] = {start_uri}
    frontier = list(subclass_map.get(start_uri, []))
    path: list[str] = []
    cl_hits: list[dict[str, Any]] = []

    while frontier:
        uri = frontier.pop(0)
        if uri in visited:
            continue
        visited.add(uri)
        path.append(_short_cl(uri))
        if _is_cl(uri):
            cl_hits.append({
                "id": _short_cl(uri),
                "label": labels.get(uri, ""),
                "ontology": "CL",
                "via": list(path[:-1]),
            })
        else:
            for parent in subclass_map.get(uri, []):
                if parent not in visited:
                    frontier.append(parent)

    return cl_hits


def _cl_ancestors_via_individual(
    aba_short: str,
    ind_hierarchy: dict[str, list[str]],
    short_to_uri: dict[str, str],
    subclass_map: dict[str, list[str]],
    labels: dict[str, str],
) -> list[dict[str, Any]]:
    """Walk the individual (RO_0015003) hierarchy, then subClassOf from each hit.

    Args:
        aba_short: ABA short ID (no URI prefix).
        ind_hierarchy: ABA short ID -> parent ABA short IDs.
        short_to_uri: ABA short ID -> CL/PCL URI.
        subclass_map: CL/PCL URI -> superclass URIs.
        labels: URI -> label.

    Returns:
        List of CL broad-match dicts (empty if none found).
    """
    visited: set[str] = {aba_short}
    queue = list(ind_hierarchy.get(aba_short, []))
    via_path: list[str] = []
    results: list[dict[str, Any]] = []

    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)
        via_path.append(node)

        if node in short_to_uri:
            target = short_to_uri[node]
            if _is_cl(target):
                results.append({
                    "id": _short_cl(target),
                    "label": labels.get(target, ""),
                    "ontology": "CL",
                    "via": list(via_path),
                })
                continue
            # PCL — try subClassOf from there
            cl_hits = _cl_ancestors_via_subclass(target, subclass_map, labels)
            for hit in cl_hits:
                hit["via"] = list(via_path) + list(hit.get("via") or [])
            results.extend(cl_hits)
            if cl_hits:
                continue

        for parent in ind_hierarchy.get(node, []):
            if parent not in visited:
                queue.append(parent)

    return results


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_mapping(owl_path: Path) -> dict[str, Any]:
    """Parse *owl_path* and return the full versioned mapping dict.

    Args:
        owl_path: Path to pcl.owl (RDF/XML).

    Returns:
        Dict with keys: version, source, generated, exact, broad.

    Example:
        .. code-block:: python

            mapping = build_mapping(Path("pcl.owl"))
            print(mapping["version"])
    """
    exact_map, labels, subclass_map, ind_hierarchy, version = _iter_blocks(owl_path)

    exact_out: dict[str, dict[str, str]] = {}
    for aba_uri, target_uri in exact_map.items():
        aba_short = _aba_short(aba_uri)
        ontology = "CL" if _is_cl(target_uri) else "PCL"
        exact_out[aba_short] = {
            "id": _short_cl(target_uri),
            "label": labels.get(target_uri, ""),
            "ontology": ontology,
        }

    broad_out = _compute_broad_matches(exact_map, labels, subclass_map, ind_hierarchy)

    return {
        "version": version,
        "source": str(owl_path),
        "generated": datetime.now(UTC).isoformat(),
        "exact": exact_out,
        "broad": broad_out,
    }


def build_mapping_from_string(owl_xml: str, source: str = "<string>") -> dict[str, Any]:
    """Parse OWL XML from a string (mainly for testing).

    Args:
        owl_xml: Full RDF/XML content of an OWL file.
        source: Label to use in the ``source`` field of the output.

    Returns:
        Same structure as :func:`build_mapping`.
    """
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".owl", delete=False, encoding="utf-8") as tf:
        tf.write(owl_xml)
        tmp_path = Path(tf.name)

    try:
        result = build_mapping(tmp_path)
        result["source"] = source
        return result
    finally:
        tmp_path.unlink(missing_ok=True)


def save_mapping(mapping: dict[str, Any], output_path: Path) -> None:
    """Serialise *mapping* to JSON at *output_path*.

    Args:
        mapping: Dict returned by :func:`build_mapping`.
        output_path: Destination path for the JSON file.
    """
    output_path.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
