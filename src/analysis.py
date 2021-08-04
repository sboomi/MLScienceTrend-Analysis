"""File where the programs are stored"""


import logging
from pathlib import Path

import coloredlogs

from src.data.ml4physics import extract_ml4physics
from src.data.neurips import get_neurips_hashs
from src import log_program

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
