"""Shared test fixtures."""

import pytest


@pytest.fixture
def minimal_owl_xml() -> str:
    """Minimal PCL OWL XML with two exact matches (one CL, one PCL) and hierarchy."""
    return """\
<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:owl="http://www.w3.org/2002/07/owl#"
         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
         xmlns:obo="http://purl.obolibrary.org/obo/">

  <owl:Ontology rdf:about="http://purl.obolibrary.org/obo/pcl.owl">
    <owl:versionInfo>2026-03-26</owl:versionInfo>
  </owl:Ontology>

  <!-- CL exact match: CS20230722_SUBC_313 -> CL:4300353 -->
  <owl:Class rdf:about="http://purl.obolibrary.org/obo/CL_4300353">
    <rdfs:label>Purkinje cell (Mmus)</rdfs:label>
    <owl:equivalentClass>
      <owl:Class>
        <owl:intersectionOf rdf:parseType="Collection">
          <rdf:Description rdf:about="http://purl.obolibrary.org/obo/CL_0000000"/>
          <owl:Restriction>
            <owl:onProperty rdf:resource="http://purl.obolibrary.org/obo/RO_0015001"/>
            <owl:hasValue rdf:resource="https://purl.brain-bican.org/taxonomy/CCN20230722/CS20230722_SUBC_313"/>
          </owl:Restriction>
        </owl:intersectionOf>
      </owl:Class>
    </owl:equivalentClass>
  </owl:Class>

  <!-- PCL exact match: CS20230722_CLUS_0001 -> PCL:0010001 -->
  <owl:Class rdf:about="http://purl.obolibrary.org/obo/PCL_0010001">
    <rdfs:label>some cluster cell type</rdfs:label>
    <owl:equivalentClass>
      <owl:Class>
        <owl:intersectionOf rdf:parseType="Collection">
          <rdf:Description rdf:about="http://purl.obolibrary.org/obo/CL_0000000"/>
          <owl:Restriction>
            <owl:onProperty rdf:resource="http://purl.obolibrary.org/obo/RO_0015001"/>
            <owl:hasValue rdf:resource="https://purl.brain-bican.org/taxonomy/CCN20230722/CS20230722_CLUS_0001"/>
          </owl:Restriction>
        </owl:intersectionOf>
      </owl:Class>
    </owl:equivalentClass>
  </owl:Class>

  <!-- PCL class for subclass hierarchy: subClassOf CL:4300353 -->
  <owl:Class rdf:about="http://purl.obolibrary.org/obo/PCL_0010002">
    <rdfs:label>orphan cluster</rdfs:label>
    <owl:equivalentClass>
      <owl:Class>
        <owl:intersectionOf rdf:parseType="Collection">
          <rdf:Description rdf:about="http://purl.obolibrary.org/obo/CL_0000000"/>
          <owl:Restriction>
            <owl:onProperty rdf:resource="http://purl.obolibrary.org/obo/RO_0015001"/>
            <owl:hasValue rdf:resource="https://purl.brain-bican.org/taxonomy/CCN20230722/CS20230722_CLUS_0002"/>
          </owl:Restriction>
        </owl:intersectionOf>
      </owl:Class>
    </owl:equivalentClass>
    <rdfs:subClassOf rdf:resource="http://purl.obolibrary.org/obo/CL_4300353"/>
  </owl:Class>

  <!-- Individuals for hierarchy: CLUS_0003 has parent SUBC_313 -->
  <owl:NamedIndividual rdf:about="https://purl.brain-bican.org/taxonomy/CCN20230722/CS20230722_CLUS_0003">
    <obo:RO_0015003 rdf:resource="https://purl.brain-bican.org/taxonomy/CCN20230722/CS20230722_SUBC_313"/>
  </owl:NamedIndividual>

  <!-- CLUS_0004 parent is CLUS_0003 (two hops to SUBC_313) -->
  <owl:NamedIndividual rdf:about="https://purl.brain-bican.org/taxonomy/CCN20230722/CS20230722_CLUS_0004">
    <obo:RO_0015003 rdf:resource="https://purl.brain-bican.org/taxonomy/CCN20230722/CS20230722_CLUS_0003"/>
  </owl:NamedIndividual>

</rdf:RDF>
"""


@pytest.fixture
def minimal_cl_owl_xml() -> str:
    """Minimal base CL OWL XML for IC computation tests.

    Hierarchy:
        CL:0000000 (root/cell)
          └─ CL:4300353 (Purkinje cell — leaf)
    """
    return """\
<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:owl="http://www.w3.org/2002/07/owl#"
         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#">

  <owl:Ontology rdf:about="http://purl.obolibrary.org/obo/cl.owl">
    <owl:versionInfo>2026-03-26</owl:versionInfo>
  </owl:Ontology>

  <owl:Class rdf:about="http://purl.obolibrary.org/obo/CL_0000000">
    <rdfs:label>cell</rdfs:label>
  </owl:Class>

  <owl:Class rdf:about="http://purl.obolibrary.org/obo/CL_4300353">
    <rdfs:label>Purkinje cell (Mmus)</rdfs:label>
    <rdfs:subClassOf rdf:resource="http://purl.obolibrary.org/obo/CL_0000000"/>
  </owl:Class>

</rdf:RDF>
"""
