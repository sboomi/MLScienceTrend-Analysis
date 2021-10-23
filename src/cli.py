"""Main `scitrend-analysis` cli"""
import os
import sys
from pathlib import Path
from typing import Optional

import click
import torch
from dotenv import load_dotenv

from src import __version__, analysis, ROOT_DIR


def version_msg() -> str:
    """Returns the package version, location, Python version"""
    python_version = sys.version[:3]
    location = Path(__file__).resolve().as_posix()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if "cuda" in device.type:
        device_properties = torch.cuda.get_device_properties(device)
        device_message = (
            f"{device_properties.name} ({device_properties.total_memory:,d} B, "
            f"{device_properties.major}.{device_properties.minor}, "
            f"{device_properties.multi_processor_count} multi-processors)"
        )
    else:
        device_message = "None. Using CPU."
    message = [f"Scitrend analysis at {location}"]
    message.append(f"Python version: {python_version}")
    message.append(f"Accelerator: {device_message}")
    return "\n".join(message)


@click.group()
@click.version_option(__version__, "-V", "--version", message=version_msg())
def main():
    pass


@main.command()
@click.argument("dest_folder", type=click.Path(exists=True), required=True)
def download(dest_folder: str) -> None:
    analysis.download_metadata(Path(dest_folder))


@main.command()
@click.argument("hash_csv", type=click.Path(exists=True), required=True)
@click.option("--mongo-uri", "mongo_uri", type=str, envvar="MONGO_ATLAS_URI", default="")
@click.option("-H", "--mongo-host", "mongo_host", envvar="MONGO_HOST", type=str, default="")
@click.option("-p", "--mongo-port", "mongo_port", envvar="MONGO_PORT", type=int, default=0)
@click.option(
    "-e",
    "--with-env",
    "is_env",
    is_flag=True,
    help="Looks for Mongo Atlas uri under MONGO_ATLAS_URI in your .env file in .config",
)
def download_metadata(
    hash_csv: str,
    mongo_uri: Optional[str] = "",
    mongo_host: Optional[str] = "",
    mongo_port: Optional[int] = 0,
    is_env: bool = False,
) -> None:
    """Downloads Neurips metadata on your selected support"""
    if not is_env:
        mongo_uri = ""
        mongo_host = ""
        mongo_port = 0
        click.echo("Using the local storage for metadata")

    if mongo_host and mongo_port:
        mongo_uri = ""
        click.echo(f"Using local MongoDB database at {mongo_host}:{mongo_port}")

    analysis.get_neurips_metadata(Path(hash_csv), mongo_uri=mongo_uri, mongo_host=mongo_host, mongo_port=mongo_port)


@main.command()
@click.argument("file_csv", type=click.Path(exists=True), required=True)
@click.option("-ng", "--n-grams", "n_grams", type=int, default=1)
@click.option("-o", "--output-folder", "save_folder", type=click.Path(exists=True), required=True)
def get_keywords(file_csv: Path, n_grams: int, save_folder: Path):
    """Pick keywords from Neurips article titles"""
    analysis.get_keywords(Path(file_csv), n_grams, Path(save_folder))


@main.command()
@click.argument("json_path", type=click.Path(exists=True), required=True)
@click.option("--db-option", "db_option", type=click.Choice(["create", "replace"], case_sensitive=False))
def neurips_meta_to_sql(json_path, db_option):
    """If you have downloaded Neurips metadata, sends it to SQL"""
    analysis.send_neurips_to_sql_db(Path(json_path), db_option)


@main.command()
@click.argument("query", type=str, nargs=-1)
@click.option("-m", "--max-results", "max_results", type=int, required=True, help="Number of results to fetch.")
@click.option("-f", "--chunk-size", "chunk_size", type=float, required=True, help="Fraction of max results to fetch")
def download_arxiv_info(query, max_results, chunk_size):
    analysis.query_arxiv_articles(" ".join(query), n_results=max_results, chunk_size=chunk_size)


@main.command()
@click.argument("dst_folder", type=click.Path(exists=True), required=True)
@click.option("-m", "--mode", type=click.Choice(["kaggle", "s3"], case_sensitive=False))
def dl_arxiv_manifest(dst_folder, mode):
    analysis.dl_arxiv_manifest(Path(dst_folder), mode=mode)


@main.command()
@click.argument("manifest_file", type=click.Path(exists=True), required=True)
@click.argument("output_folder", type=click.Path(exists=True), required=True)
@click.option("-y", "--yes", is_flag=True)
def arxiv_build_data(manifest_file, output_folder, yes):
    """Downloads bulk data from S3"""
    manifest_file = Path(manifest_file)
    if not manifest_file.suffix.endswith("xml"):
        click.echo("Not a valid manifest file. Must be `.xml` only.")
        return

    analysis.dl_arxiv_bulk_data(manifest_file, Path(output_folder), yes)


if __name__ == "__main__":
    env_path = ROOT_DIR / ".config" / ".env"
    load_dotenv(env_path)
    main()
