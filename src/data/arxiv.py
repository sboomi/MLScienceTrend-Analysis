import datetime as dt
import logging
import os
import sys
import time
from enum import Enum
from pathlib import Path
from subprocess import PIPE, Popen

import boto3
import coloredlogs
import requests
from botocore.exceptions import ClientError
from bs4 import BeautifulSoup
from bs4.element import Tag
from pydantic import BaseModel, ValidationError, validator
from sqlalchemy.engine import Engine
from sqlalchemy.orm.session import sessionmaker
from src.data.db_models import Papers
from tqdm import tqdm, trange

from .db_models import Authors, Links, Papers

PAUSE_TIME = 3
BASE_URL = "http://export.arxiv.org/api/"


class MethodName(BaseModel):
    search_query: str = ""
    id_list: str = ""
    start: int = 0
    max_results: int = 10  # max_results

    @validator("max_results")
    def max_results_lim_exceeded(cls, v):
        if v > 30000:
            raise ValidationError("max_results can't exceed 30,000")
        return v


class SearchQueryParams(Enum):
    title = "ti"
    author = "au"
    abstract = "abs"
    comment = "co"
    journal_ref = "jr"
    subject_cat = "cat"
    report_number = "rn"
    all = "all"


log_fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=log_fmt)
logger = logging.getLogger(__name__)
coloredlogs.install()


def return_arxiv_entry(entry: Tag) -> Papers:
    """Takes an entry from arXiv's API and turns it into
    an ORM instance

    Parameters
    ----------
    entry : Tag
        The entry's bs4 body. It usually contains the keywords specified
        by arXiv's API (https://arxiv.org/help/api/user-manual#_details_of_atom_results_returned)

    Returns
    -------
    Papers
        The corresponding SQL output
    """
    return Papers(
        title=entry.title.text if entry.title else None,
        abstract=entry.summary.text if entry.summary else None,
        updated_date=dt.datetime.fromisoformat(entry.updated.text.strip("Z")) if entry.updated else None,
        published_date=dt.datetime.fromisoformat(entry.published.text.strip("Z")) if entry.published else None,
        doi=entry.doi.text if entry.doi else None,
        dataset="arxiv",
        authors=[
            Authors(
                firstname=author.find("name").text.split()[:-1],
                lastname=author.find("name").text.split()[-1],
                institution=author.find("affiliation").text,
            )
            for author in entry.find_all("authors")
        ],
        links=[
            Links(type=link.get("type") or link.get("title"), url=link.get("href")) for link in entry.find_all("link")
        ],
        comment=entry.comment.text if entry.comment else None,
        publication=entry.journal_ref.text if entry.journal_ref else None,
        category=entry.category.get("term") if entry.category else None,
    )


def request_arxiv(url: str, session: sessionmaker) -> None:
    """takes an Arxiv URL and extracts the articles from it

    Parameters
    ----------
    url : str
        the url from the arXiv API
    session : sessionmaker
        A session created by SQLAlchemy's sessionmaker and engine
    """
    r = requests.get(url)
    if r.status_code == 200:
        soup = BeautifulSoup(r.content, "xml")
        logger.info(f"Found {soup.find('totalResults').text} results.")
        logger.info(f"Starts at {soup.find('startIndex').text} (results per page: {soup.find('itemsPerPage').text})")
        for entry in tqdm(
            soup.find_all("entry"), desc="Entry registering", total=len(soup.find_all("entry")), file=sys.stdout
        ):
            db_entry = return_arxiv_entry(entry)
            session.add(db_entry)

        session.commit()
    else:
        err_xml = BeautifulSoup(r.content, "xml")
        msg = err_xml.find("entry").find("summary").text
        logger.error(f"Error: {msg}")


def compose_arxiv_query(query: str, engine: Engine, max_results: int = 500, frac_requests: float = 0.5) -> None:
    """Takes a full arXiv query and registers from the API. The processing can be
    done through chunks of data if the request is too big. Total results per page
    must not exceed 30,000 requests as per arXiv's suggestion, and the function pauses
    the code of PAUSE_TIME seconds.

    Parameters
    ----------
    query : str
        the full query. Can be one or multiple words.
    engine : Engine
        SQLAlchemy engine.
    max_results : int, optional
        maximum requested results, by default 500
    frac_requests : float, optional
        chunk fraction, by default 0.5
    """
    max_res_per_page = int(max_results * frac_requests)
    Session = sessionmaker(engine)
    session = Session()
    for start_idx in trange(0, max_results, max_res_per_page):
        logger.info(f"From {start_idx} to {min(start_idx + max_res_per_page, max_results)}")
        fmt_query = query if len(query.split()) == 1 else f'"{query}"'
        met = MethodName(
            search_query=f"{SearchQueryParams.all.value}:{fmt_query}",
            start=start_idx,
            max_results=max_res_per_page,
        )
        url = f"{BASE_URL}query?{'&'.join([f'{k}={v}' for k,v in met.dict().items() if v])}"
        logger.info(f"Requesting {url}")
        request_arxiv(url, session)
        # Pause to avoid overloading
        time.sleep(PAUSE_TIME)
    session.close()


def dl_bulk_data_manifest(dst_folder: Path, pref_method: str = "kaggle"):
    if pref_method == "kaggle":
        # Downloads from Kaggle API
        try:
            proc = Popen(
                ["kaggle", "datasets", "download", "-d", "Cornell-University/arxiv", "-p", str(dst_folder.as_posix())],
                stdout=PIPE,
                stderr=PIPE,
            )
        except FileNotFoundError:
            logger.error("Kaggle API isn't installed. Please use `pip install kaggle`")
        stdout, stderr = proc.communicate()
        if stdout:
            logger.info(f"{stdout.decode()}")
        elif stderr:
            logger.error(f"{stderr.decode()}")

    elif pref_method == "s3":
        bucket_file = "src/arXiv_src_manifest.xml"
        logger.info(f"Downloading s3://arxiv/{bucket_file} to {dst_folder.as_posix()}/src/arXiv_src_manifest.xml...")
        s3resource = boto3.resource(
            "s3",  # the AWS resource we want to use
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_KEY"),
            region_name="us-east-1",  # same region arxiv bucket is in
        )
        try:
            s3resource.meta.client.download_file(
                Bucket="arxiv",
                Key=bucket_file,  # name of file to download from
                Filename=dst_folder / bucket_file,  # path to file to download to
                ExtraArgs={"RequestPayer": "requester"},
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                logger.error("ERROR: " + bucket_file + " does not exist in arxiv bucket")
