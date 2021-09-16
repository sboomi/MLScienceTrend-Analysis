"""Scripts to transfer data from file / db and vice-versa"""
from pathlib import Path
import json
import logging
from typing import List
import coloredlogs
import pandas as pd
from sqlalchemy.orm.session import sessionmaker
from tqdm import tqdm
from sqlalchemy.engine import Engine
from . import Base
from .db_models import Papers, Authors

log_fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=log_fmt)
logger = logging.getLogger(__name__)
coloredlogs.install()


def metadata_to_sql_db(json_folder: Path, sql_engine: Engine, options: str = "create"):
    """[summary]

    Possible keys are 'title', 'book', 'page_first', 'page_last',
    'abstract', 'full_text', 'award', 'sourceid', 'authors'

    Parameters
    ----------
    json_folder : Path
        [description]
    sql_engine : Engine
        [description]
    """

    if options == "create":
        Base.metadata.drop_all(sql_engine)
        Base.metadata.create_all(sql_engine)

    Session = sessionmaker(sql_engine)
    session = Session()

    total_data = len(list(json_folder.iterdir()))
    for json_meta in tqdm(json_folder.iterdir(), desc="Transferring to db", total=total_data):
        year, paper_hash = json_meta.stem.split("_")
        year = int(year)

        with open(json_meta, "rb") as json_f:
            metadata = json.load(json_f)

        if "error" in metadata.keys():
            logger.warning("Invalid file detected. Skipping.")
            if options == "replace":
                session.query(Papers).filter(Papers.hash == paper_hash).update(
                    {"year": year, "category": "deep learning", "dataset": "neurips"}, synchronize_session="fetch"
                )
            else:
                paper = Papers(year=year, hash=paper_hash, category="deep learning", dataset="neurips")
                session.add(paper)
            continue

        if options == "replace":
            session.query(Papers).filter(Papers.hash == paper_hash).update(
                {
                    "year": year,
                    "hash": paper_hash,
                    "title": metadata["title"],
                    "publication": metadata["book"],
                    "abstract": metadata["abstract"],
                    "full_text": metadata["full_text"],
                    "category": "deep learning",
                    "dataset": "neurips",
                },
                synchronize_session="fetch",
            )
        else:
            paper = Papers(
                year=year,
                hash=paper_hash,
                title=metadata["title"],
                authors=[
                    Authors(
                        firstname=author["given_name"],
                        lastname=author["family_name"],
                        institution=author["institution"],
                    )
                    for author in metadata["authors"]
                ],
                publication=metadata["book"],
                abstract=metadata["abstract"],
                full_text=metadata["full_text"],
                category="deep learning",
                dataset="neurips",
            )
            session.add(paper)

    # Commit session at the end of your operations
    session.commit()
    logger.info("Done!")
    session.close()


def extract_sql_to_df(engine: Engine, table: str, columns: List[str] = []) -> pd.DataFrame:
    if columns:
        query = f"SELECT {', '.join(columns)} FROM {table}"
    else:
        query = f"SELECT * FROM {table}"
    return pd.read_sql(query, engine)
