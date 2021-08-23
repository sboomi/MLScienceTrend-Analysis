"""Main `scitrend-analysis` cli"""
import os
import sys
from pathlib import Path
from typing import Optional

import click
import torch
from dotenv import load_dotenv

from src import __version__, analysis

ROOT_DIR = Path(__file__).resolve().parents[1]


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
def dowload_metadata(
    hash_csv: str,
    mongo_uri: Optional[str] = "",
    mongo_host: Optional[str] = "",
    mongo_port: Optional[int] = 0,
    is_env: bool = False,
) -> None:
    if not is_env:
        mongo_uri = ""
        mongo_host = ""
        mongo_port = 0
        click.echo("Using the local storage for metadata")

    if mongo_host and mongo_port:
        mongo_uri = ""
        click.echo(f"Using local MongoDB database at {mongo_host}:{mongo_port}")

    analysis.get_neurips_metadata(Path(hash_csv), mongo_uri=mongo_uri, mongo_host=mongo_host, mongo_port=mongo_port)


if __name__ == "__main__":
    env_path = ROOT_DIR / ".config" / ".env"
    load_dotenv(env_path)
    main()
