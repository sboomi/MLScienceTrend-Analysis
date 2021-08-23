import json
import logging
from pathlib import Path
from typing import List, Optional

import coloredlogs
import pandas as pd
import pymongo
import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from pydantic import BaseModel, NoneStr
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

from . import Base
from .db_models import Authors, Papers
from .dbutils import MongoConnector, NeuripsAPIConnector

NEURIPS_URL = "https://papers.nips.cc/"
ROOT_DIR = Path(__file__).resolve().parents[2]
CURRENT_YEAR = 2021


log_fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=log_fmt)
logger = logging.getLogger(__name__)
coloredlogs.install()


class HashYearDataFrame(BaseModel):
    hash: List[NoneStr] = []
    year: List[Optional[int]] = []


class NeuripsInfoPaper(BaseModel):
    title: str = ""
    authors: str = ""
    abstract: str = ""


class NeuripsInfoDataFrame(BaseModel):
    title: List[str] = []
    authors: List[str] = []
    abstract: List[str] = []


class MongoCreds(BaseModel):
    uri: NoneStr
    host: str = "localhost"
    port: int = 27017
    database: str = "neurips"
    collection: str = "neurips_metadata"


def extract_text(el: Optional[Tag]) -> str:
    """Extract the inner text from a BS4 tag

    Parameters
    ----------
    el : Optional[Tag]
        BS4 tag (can be null)

    Returns
    -------
    str
        The inner text (returns empty string if tag is empty)
    """
    if el:
        return el.text.strip()

    return ""


def author_entry(authors: str) -> Authors:
    authors = authors.strip()
    firstname, lastname = " ".join(authors.split()[:-1]), authors.split()[-1]
    return Authors(firstname=firstname, lastname=lastname)


def get_neurips_hashs(save_file: Optional[Path] = None) -> pd.DataFrame:
    """Retrieves the hashes from each NeurIPS abstract from the proceedings website: `https://papers.nips.cc/`

    The hashes and the year are needed to extract complementary information from that website, hence why the user can pass an optional parameter where the resut is stored in a CSV file.

    Parameters
    ----------
    save_file : Optional[Path], optional
        The file where the results are saved, by default None

    Returns
    -------
    pd.DataFrame
        The dataframe containing the hashs and year columns
    """
    year_hash = HashYearDataFrame()
    for y in range(1987, CURRENT_YEAR):
        year_url = NEURIPS_URL + f"paper/{y}"
        r = requests.get(year_url)
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, "html.parser")
            for p in soup.select("div.col li a"):
                url = p["href"]
                *_, abstract = url.split("/")
                hash_url, *_ = abstract.split("-")
                year_hash.hash.append(hash_url)
                year_hash.year.append(y)
    df = pd.DataFrame(year_hash.dict())
    if save_file:
        df.to_csv(save_file, index=None)
    return df


def save_neurips_info(save_folder: Path, hash_csv: Optional[Path] = None) -> pd.DataFrame:
    """Saves information about the articles in CSV file

    Parameters
    ----------
    save_folder : Path
        [description]
    hash_csv : Optional[Path], optional
        [description], by default None

    Returns
    -------
    pd.DataFrame
        [description]
    """
    data = NeuripsInfoDataFrame()

    if hash_csv:
        try:
            year_hash = pd.read_csv(hash_csv)
        except FileNotFoundError:
            logger.error(f"{hash_csv} not found. Retrieving data")
            year_hash = get_neurips_hashs(save_file=hash_csv)
    else:
        year_hash = get_neurips_hashs()

    for _, row in tqdm(year_hash.iterrows(), desc="Scraping abstracts", total=year_hash.shape[0], unit="row"):
        url = f"{NEURIPS_URL}paper/{row.year}/hash/{row.hash}-Abstract.html"
        paper = NeuripsInfoPaper()
        r = requests.get(url)
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, "html.parser")
            for title, content in zip(soup.select("div.col h4"), soup.select("div.col h4 + p")):
                title, content = extract_text(title), extract_text(content)

                if "part of" in content.lower():
                    paper.title = title

                if "authors" in title.lower():
                    paper.authors = content

                if "abstract" in title.lower():
                    paper.abstract = content

            data.title.append(paper.title)
            data.authors.append(paper.authors)
            data.abstract.append(paper.abstract)

        else:
            logger.error(f"Couldnt parse {url}. CODE: {r.status_code}")

    df = pd.DataFrame(data.dict())
    logger.info(f"Done! Saving to {save_folder / 'neurips_info.csv'}")
    df.to_csv(save_folder / "neurips_info.csv", index=None)
    return df


def save_neurips_info_sql(engine: Engine, hash_csv: Optional[Path] = None) -> None:
    """Saves Neurips data inside the SQL database you logged in.

    Parameters
    ----------
    engine : Engine
        An SQLalchemy engine
    hash_csv : Optional[Path], optional
        [description], by default None
    """

    # Creates the tables
    Base.metadata.create_all(engine)

    Session = sessionmaker(engine)
    session = Session()

    if hash_csv:
        try:
            year_hash = pd.read_csv(hash_csv)
        except FileNotFoundError:
            logger.error(f"{hash_csv} not found. Retrieving data")
            year_hash = get_neurips_hashs(save_file=hash_csv)
    else:
        year_hash = get_neurips_hashs()

    for _, row in tqdm(year_hash.iterrows(), desc="Scraping abstracts", total=year_hash.shape[0], unit="row"):
        url = f"{NEURIPS_URL}paper/{row.year}/hash/{row.hash}-Abstract.html"
        paper = NeuripsInfoPaper()
        r = requests.get(url)
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, "html.parser")
            for title, content in zip(soup.select("div.col h4"), soup.select("div.col h4 + p")):
                title, content = extract_text(title), extract_text(content)

                if "part of" in content.lower():
                    paper.title = title

                if "authors" in title.lower():
                    paper.authors = content

                if "abstract" in title.lower():
                    paper.abstract = content

            paper_entry = Papers(
                hash=row.hash,
                year=int(row.year),
                title=paper.title,
                abstract=paper.abstract,
                authors=([author_entry(author) for author in paper.authors.split(",")] if paper.authors else []),
            )

        else:
            logger.error(f"Couldnt parse {url}. CODE: {r.status_code}")
            paper_entry = Papers(hash=row.hash, year=int(row.year))

        session.add(paper_entry)

    session.commit()
    logger.info("Done!")


def save_neurips_metadata(hash_csv: Optional[Path] = None, mongo_creds: Optional[MongoCreds] = None) -> None:
    """[summary]

    Parameters
    ----------
    hash_csv : Optional[Path], optional
        [description], by default None
    mongo_creds : Optional[MongoCreds], optional
        [description], by default None
    """
    if hash_csv:
        try:
            year_hash = pd.read_csv(hash_csv)
        except FileNotFoundError:
            logger.error(f"{hash_csv} not found. Retrieving data")
            year_hash = get_neurips_hashs(save_file=hash_csv)
    else:
        year_hash = get_neurips_hashs()

    if mongo_creds:
        mongo_conn = MongoConnector()
        if mongo_creds.uri:
            logger.info("Mongo Atlas URI detected.")
            mongo_conn.connect_from_atlas(mongo_creds.uri)
        else:
            logger.info(f"Connecting to MongoDB at {mongo_creds.host}:{mongo_creds.port}")
            mongo_conn.connect_locally(host=mongo_creds.host, port=mongo_creds.port)

        client = mongo_conn.create_client()
        db = client[mongo_creds.database]
        collection = db[mongo_creds.collection]
    else:
        json_dir = ROOT_DIR / "data" / "raw" / "neurips_metadata"
        json_dir.mkdir(parents=True, exist_ok=True)

    for _, row in tqdm(year_hash.iterrows(), desc="retrieving metatdata", unit="hash", total=year_hash.shape[0]):
        # Before requesting, check if the entry isn't in the db / folder first
        if mongo_creds:
            current_entry = collection.find_one({"_id": row.hash})
        else:
            current_entry = (json_dir / f"{row.year}_{row.hash}.json").exists()

        if not current_entry:
            # Get request
            try:
                metadata = NeuripsAPIConnector.get_metadata(row.hash, row.year)
            except Exception as e:
                logger.error(f"{e}. Skipping...")
            else:
                # Check the error report first
                if "error" in metadata:
                    logger.error(f"{metadata['error']} with {metadata['url']}")
                    metadata["hash"] = row.hash
                    metadata["year"] = row.year
                    metadata["status"] = "Download failed"

                # Insert or register if everything is ok
                if mongo_creds:
                    metadata["_id"] = row.hash
                    try:
                        _ = collection.insert_one(metadata).inserted_id
                    except pymongo.errors.DuplicateKeyError:
                        logger.error(f"Entry {row.hash} already exists!")
                    else:
                        logger.info(f"Entry {row.hash} inserted!")

                else:
                    # Save everything as a JSON file
                    with open(json_dir / f"{row.year}_{row.hash}.json", "w") as json_f:
                        json.dump(metadata, json_f, indent=2)
                    logger.info(f"{json_dir / f'{row.year}_{row.hash}.json'} written!")
        else:
            logger.warning(f"Entry {row.hash} from {row.year} already exists")

    logger.info("Operation complete.")


def download_neurips_bibtex(target_folder: Path, hash_csv: Optional[Path] = None) -> None:
    """[summary]

    Parameters
    ----------
    target_folder : Path
        [description]
    hash_csv : Optional[Path], optional
        [description], by default None
    """
    if not target_folder.exists():
        logger.warning("Provided folder doesn't exist. Creating a new one")
        target_folder.mkdir(parents=True)

    if hash_csv:
        try:
            year_hash = pd.read_csv(hash_csv)
        except FileNotFoundError:
            logger.error(f"{hash_csv} not found. Retrieving data")
            year_hash = get_neurips_hashs(save_file=hash_csv)
    else:
        year_hash = get_neurips_hashs()
    for _, row in tqdm(year_hash.iterrows(), desc="Downloading bibtex refs", unit="hash", total=year_hash.shape[0]):
        bibtex_url = f"{NEURIPS_URL}paper/{row.year}/file/{row.hash}-Bibtex.bib"
        r = requests.get(bibtex_url)
        if r.status_code == 200 and not (target_folder / f"{row.year}_{row.hash}.bib").exists():
            with open(target_folder / f"{row.year}_{row.hash}.bib", "wb") as f:
                f.write(r.content)
            logger.info(f"{row.year}_{row.hash}.bib successfully written.")
    logger.info("Operation complete")


def download_neurips_papers(target_folder: Path, hash_csv: Optional[Path] = None, chunk_size: int = 512) -> None:
    """Function that downloads papers from the Neurips website.
    It takes a destination folder as well as a chunk_size in the possible case that the
    download might exceed the buffer's capacity.

    Parameters
    ----------
    target_folder : Path
        folder to put your PDFs in
    hash_csv : Optional[Path], optional
        metadata file containing the hashes and the years, by default None
    chunk_size : int, optional
        array size when the PDF is donwloaded by parts, by default 512
    """
    if not target_folder.exists():
        logger.warning("Provided folder doesn't exist. Creating a new one")
        target_folder.mkdir(parents=True)

    if hash_csv:
        try:
            year_hash = pd.read_csv(hash_csv)
        except FileNotFoundError:
            logger.error(f"{hash_csv} not found. Retrieving data")
            year_hash = get_neurips_hashs(save_file=hash_csv)
    else:
        year_hash = get_neurips_hashs()
    for _, row in tqdm(year_hash.iterrows(), desc="Downloading PDFS", unit="hash", total=year_hash.shape[0]):
        pdf_url = f"{NEURIPS_URL}paper/{row.year}/file/{row.hash}-Paper.pdf"
        r = requests.get(pdf_url, stream=True)
        if r.status_code == 200 and not (target_folder / f"{row.year}_{row.hash}.pdf").exists():
            with open(target_folder / f"{row.year}_{row.hash}.pdf", "wb") as f:
                for chunk in r.iter_content(chunk_size):
                    f.write(chunk)
            logger.info(f"{row.year}_{row.hash}.pdf successfully written.")
    logger.info("Operation complete")
