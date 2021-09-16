"""File where the programs are stored"""


import logging
from pathlib import Path
from src.data.intermediate import extract_sql_to_df, metadata_to_sql_db
from src.data.dbutils import load_sql_engine

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
from src.features.extract_words import extract_keywords
from src.visualization.wordcloud import feature_wordcloud

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


def get_keywords(csv_file: Path, n_grams: int, save_folder: Path):
    if not csv_file.exists() or csv_file.suffix != ".csv":
        raise FileNotFoundError("Please provide a valid CSV file first.")

    if not save_folder.exists():
        raise FileNotFoundError("Pleas eprovide a valid folder first.")

    df_csv = save_folder / f"feat_count_{csv_file.stem}_{n_grams}_grams.csv"
    fig_png = save_folder / f"wc_{csv_file.stem}_{n_grams}_grams.png"

    feat_df = extract_keywords(csv_file, n_grams=n_grams, to_file=df_csv)
    feature_wordcloud(feat_df, title=f"Wordcloud {n_grams}-grams on file `{csv_file.stem}`", to_png=fig_png)


@log_program("Downloading Neurips Metadata JSON", timeit=True)
def send_neurips_to_sql_db(json_path, option):
    logger.info("Connecting to SQLite3 DB by default")
    engine = load_sql_engine()
    logger.info(f"Using DB: {engine.url}")
    metadata_to_sql_db(json_folder=json_path, sql_engine=engine, options=option)


@log_program("Preprocessing text", timeit=True)
def preprocessing_neurips(sql_uri=""):
    engine = load_sql_engine(database=sql_uri)
    papers = extract_sql_to_df(engine, "papers", columns=["title", "full_text"])
