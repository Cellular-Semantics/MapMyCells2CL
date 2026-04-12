"""Command-line interface for mapmycells2cl.

Commands
--------
annotate
    Annotate a MapMyCells CSV or JSON file with CL terms.

update-mappings
    Download latest pcl.owl and regenerate the bundled mapping JSON.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from mapmycells2cl.mapper import CellTypeMapper


@click.group()
def cli() -> None:
    """Map MapMyCells ABA taxonomy IDs to Cell Ontology (CL) terms."""


@cli.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o",
    "--output",
    "output_file",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file path. Defaults to <input>_annotated.<ext>.",
)
@click.option(
    "--mapping",
    "mapping_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to a custom mapping JSON file.",
)
def annotate(input_file: Path, output_file: Path | None, mapping_path: Path | None) -> None:
    """Annotate a MapMyCells CSV or JSON file with CL terms.

    INPUT_FILE may be a .csv or .json file produced by MapMyCells.
    """
    from mapmycells2cl.annotator import annotate_csv, annotate_json

    suffix = input_file.suffix.lower()
    if suffix not in {".csv", ".json"}:
        click.echo(f"Error: unsupported file type '{suffix}'. Use .csv or .json.", err=True)
        sys.exit(1)

    if output_file is None:
        stem = input_file.stem
        output_file = input_file.with_name(f"{stem}_annotated{suffix}")

    try:
        mapper = CellTypeMapper(mapping_path)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Mapping version: {mapper.mapping_version}")
    click.echo(f"Annotating {input_file} -> {output_file}")

    if suffix == ".csv":
        annotate_csv(input_file, output_file, mapper)
    else:
        annotate_json(input_file, output_file, mapper)

    click.echo("Done.")


@cli.command("annotate-h5ad")
@click.argument("mmc_csv", type=click.Path(exists=True, path_type=Path))
@click.argument("h5ad_in", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o",
    "--output",
    "h5ad_out",
    type=click.Path(path_type=Path),
    default=None,
    help="Output h5ad path. Defaults to <input>_annotated.h5ad.",
)
@click.option(
    "--cxg-level",
    default="cluster",
    show_default=True,
    help="Taxonomy level used for unprefixed CxG cell_type columns.",
)
@click.option(
    "--mapping",
    "mapping_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to a custom mapping JSON file.",
)
def annotate_h5ad_cmd(
    mmc_csv: Path,
    h5ad_in: Path,
    h5ad_out: Path | None,
    cxg_level: str,
    mapping_path: Path | None,
) -> None:
    """Annotate an h5ad file with CL terms from a MapMyCells CSV.

    MMC_CSV is the MapMyCells CSV output. H5AD_IN is the AnnData file to annotate.
    """
    from mapmycells2cl.annotator import annotate_h5ad

    if h5ad_out is None:
        h5ad_out = h5ad_in.with_name(f"{h5ad_in.stem}_annotated.h5ad")

    try:
        mapper = CellTypeMapper(mapping_path)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Mapping version: {mapper.mapping_version}")
    click.echo(f"Annotating {h5ad_in} -> {h5ad_out}")

    annotate_h5ad(mmc_csv, h5ad_in, h5ad_out, mapper, cxg_level=cxg_level)
    click.echo("Done.")


@cli.command("update-mappings")
@click.option(
    "--owl",
    "owl_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to a local pcl.owl. Downloads from PURL if omitted.",
)
@click.option(
    "--cl-owl",
    "cl_owl_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to base cl.owl for IC computation. Downloads if omitted.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Output path for mapping JSON. Defaults to bundled data/mapping.json.",
)
def update_mappings(
    owl_path: Path | None,
    cl_owl_path: Path | None,
    output_path: Path | None,
) -> None:
    """Download latest pcl.owl + cl.owl and regenerate the bundled mapping JSON.

    IC-ranked best_cl data is included when cl.owl is available (recommended).
    """
    import urllib.request

    from mapmycells2cl.parser import build_mapping, save_mapping

    def _download(url: str, dest: Path) -> None:
        click.echo(f"Downloading {url} ...")
        try:
            urllib.request.urlretrieve(url, dest)  # noqa: S310
        except Exception as exc:
            click.echo(f"Error downloading {url}: {exc}", err=True)
            sys.exit(1)

    if owl_path is None:
        owl_path = Path("pcl.owl")
        _download("http://purl.obolibrary.org/obo/pcl.owl", owl_path)

    if cl_owl_path is None:
        cl_owl_path = Path("cl.owl")
        if not cl_owl_path.exists():
            _download("http://purl.obolibrary.org/obo/cl.owl", cl_owl_path)
        else:
            click.echo(f"Using existing {cl_owl_path}")

    if output_path is None:
        output_path = Path(__file__).parent / "data" / "mapping.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    click.echo(f"Parsing {owl_path} ...")
    mapping = build_mapping(owl_path, cl_owl_path=cl_owl_path)
    n_best = len(mapping.get("best_cl", {}))
    click.echo(
        f"  Extracted {len(mapping['exact'])} exact, "
        f"{len(mapping['broad'])} broad, "
        f"{n_best} best_cl entries (version: {mapping['version']})"
    )

    save_mapping(mapping, output_path)
    click.echo(f"Mapping saved to {output_path}")
