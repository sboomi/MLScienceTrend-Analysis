"""Scripts to transfer data from file / db and vice-versa"""
import json
import logging
import pdb
from pathlib import Path
from typing import List

import coloredlogs
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import FlushError
from sqlalchemy.orm.session import sessionmaker
from tqdm import tqdm

from . import Base
from .db_models import Authors, Papers

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

    logger.info(f"Using engine from {sql_engine.url}...")
    if options == "create":
        Base.metadata.drop_all(sql_engine)
        Base.metadata.create_all(sql_engine)
        logger.info("Destroyed and created tables.")

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
                # session.add(paper)
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
            # Create paper
            paper = Papers(
                year=year,
                hash=paper_hash,
                title=metadata["title"],
                publication=metadata["book"],
                abstract=metadata["abstract"],
                full_text=metadata["full_text"],
                category="deep learning",
                dataset="neurips",
            )

            for author in metadata["authors"]:
                given_name = author["given_name"]
                last_name = author["family_name"]
                institution = author["institution"]
                try:
                    ent_author = (
                        session.query(Authors)
                        .filter(Authors.firstname == given_name, Authors.lastname == last_name)
                        .first()
                    )
                    if not ent_author:
                        ent_author = Authors(
                            firstname=given_name,
                            lastname=last_name,
                            institution=institution,
                        )
                        ent_author.papers.append(paper)
                        session.add(ent_author)
                        session.commit()

                    paper.authors.append(ent_author)

                except IntegrityError:
                    logger.error(f"Caught integrity issues with {ent_author}. Rerolling session...")
                    session.rollback()
                except FlushError:
                    logger.error(f"Flush error with {ent_author}. Rerolling...")
                    session.rollback()

                # pdb.set_trace()

            # pdb.set_trace()
            session.add(paper)

            try:
                session.commit()
            except FlushError:
                session.rollback()
            # session.flush()

            # assoc = PaperAuthor(paper=paper, author=author)

    # Commit session at the end of your operations
    try:
        session.commit()
    except FlushError:
        session.rollback()
    logger.info("Done!")
    session.close()


def extract_sql_to_df(engine: Engine, table: str, columns: List[str] = []) -> pd.DataFrame:
    if columns:
        query = f"SELECT {', '.join(columns)} FROM {table}"
    else:
        query = f"SELECT * FROM {table}"
    return pd.read_sql(query, engine)
