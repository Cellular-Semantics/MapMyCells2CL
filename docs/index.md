# MapMyCells2CL

Annotate [MapMyCells](https://brain-map.org/bkp/analyze/mapmycells) output with
[Cell Ontology (CL)](https://obofoundry.org/ontology/cl.html) terms.

```{toctree}
:maxdepth: 2
:hidden:

autoapi/index
```

## Overview

MapMyCells assigns cells to Allen Brain Atlas (ABA) taxonomy nodes
(e.g. `CS20230722_SUBC_053`). This library maps those IDs to CL or Provisional
Cell Ontology (PCL) terms and selects the **most specific CL term** using
information-content (IC) ranking — ready for CELLxGENE schema compliance.

## Quick start

```bash
pip install mapmycells2cl

# Annotate a MapMyCells CSV
mapmycells2cl annotate results.csv

# Annotate an h5ad file (CxG-compliant obs columns)
mapmycells2cl annotate-h5ad results.csv cells.h5ad
```

## Python API

```python
from mapmycells2cl import CellTypeMapper

mapper = CellTypeMapper()
result = mapper.lookup("CS20230722_SUBC_313")

print(result.best_cl_id)     # CL:4300353
print(result.best_cl_label)  # Purkinje cell (Mmus)
print(result.best_cl_ic)     # IC score
```

See the {doc}`API reference <autoapi/index>` for full documentation.
