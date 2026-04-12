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
@click.option("-o", "--output", "output_file", type=click.Path(path_type=Path), default=None,
              help="Output file path. Defaults to <input>_annotated.<ext>.")
@click.option("--mapping", "mapping_path", type=click.Path(exists=True, path_type=Path),
              default=None, help="Path to a custom mapping JSON file.")
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


@cli.command("update-mappings")
@click.option("--owl", "owl_path", type=click.Path(path_type=Path), default=None,
              help="Path to a local pcl.owl. Downloads from PURL if omitted.")
@click.option("--output", "output_path", type=click.Path(path_type=Path), default=None,
              help="Output path for mapping JSON. Defaults to bundled data/mapping.json.")
def update_mappings(owl_path: Path | None, output_path: Path | None) -> None:
    """Download latest pcl.owl and regenerate the bundled mapping JSON."""
    from mapmycells2cl.parser import build_mapping, save_mapping

    if owl_path is None:
        import urllib.request

        pcl_url = "http://purl.obolibrary.org/obo/pcl.owl"
        cache = Path("pcl.owl")
        click.echo(f"Downloading {pcl_url} ...")
        try:
            urllib.request.urlretrieve(pcl_url, cache)  # noqa: S310
        except Exception as exc:
            click.echo(f"Error downloading pcl.owl: {exc}", err=True)
            sys.exit(1)
        owl_path = cache

    if output_path is None:
        output_path = Path(__file__).parent / "data" / "mapping.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    click.echo(f"Parsing {owl_path} ...")
    mapping = build_mapping(owl_path)
    click.echo(
        f"  Extracted {len(mapping['exact'])} exact matches, "
        f"{len(mapping['broad'])} broad matches (version: {mapping['version']})"
    )

    save_mapping(mapping, output_path)
    click.echo(f"Mapping saved to {output_path}")
