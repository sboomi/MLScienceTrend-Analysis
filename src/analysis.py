"""File where the programs are stored"""


import logging
from pathlib import Path

import coloredlogs

from src import log_program
from src.data.ml4physics import extract_ml4physics
from src.data.neurips import (
    download_neurips_bibtex,
    download_neurips_papers,
    get_neurips_hashs,
    save_neurips_metadata,
    MongoCreds,
)

log_fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=log_fmt)
logger = logging.getLogger(__name__)
coloredlogs.install()


@log_program("Downloading metadata for neurips and ml4physics", timeit=True)
def download_metadata(dest_folder: Path):
    df_ml4 = extract_ml4physics(save_file=(dest_folder / "ml4physics.csv"))
    logger.info(f"Downloaded {df_ml4.shape[0]} of raw data")
    df_neurips = get_neurips_hashs(save_file=(dest_folder / "neurips.csv"))
    logger.info(f"Downloaded {df_neurips.shape[0]} of raw data")


@log_program("Downloading Neurips Metadata JSON", timeit=True)
def get_neurips_metadata(metadata_csv: Path, mongo_uri: str = "", mongo_host: str = "", mongo_port: int = 0) -> None:
    mongo_creds = None
    if mongo_uri:
        logger.info(f"Registering metadata in MongoDB Atlas cluster\nURI:{mongo_uri}")
        mongo_creds = MongoCreds(uri=mongo_uri)
    elif mongo_host and mongo_port:
        logger.info(f"Registering metadata in MongoDB local base\nHost:{mongo_host} / Port:{mongo_port}")
        mongo_creds = MongoCreds(host=mongo_host, port=mongo_port)
    else:
        logger.info("No MongoDB creds found. Saving locally.")

    save_neurips_metadata(hash_csv=metadata_csv, mongo_creds=mongo_creds)
