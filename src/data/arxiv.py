import datetime as dt
import hashlib
import json
import logging
import os
import shutil
import sys
import time
import zipfile
from enum import Enum
from pathlib import Path
from subprocess import PIPE, Popen
from typing import List

import boto3
import coloredlogs
import requests
from botocore.exceptions import ClientError
from bs4 import BeautifulSoup
from bs4.element import Tag
from pydantic import BaseModel, ValidationError, validator
from sqlalchemy.engine import Engine
from sqlalchemy.orm import session
from sqlalchemy.orm.session import sessionmaker
from tqdm import tqdm, trange

from .db_models import Authors, Links, PaperAuthor, Papers

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


def md5(fname):
    """Generates MD5 hash of a file to verify integrity

    Parameters
    ----------
    fname : [type]
        [description]

    Returns
    -------
    [type]
        [description]
    """
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def save_arxiv_entry(entry: Tag, session: sessionmaker) -> None:
    """Takes an entry tag and saves the results within the sessio

    Parameters
    ----------
    entry : Tag
        The entry's bs4 body. It usually contains the keywords specified
        by arXiv's API (https://arxiv.org/help/api/user-manual#_details_of_atom_results_returned)

    session : sessionmaker
        The SQLAlchemy session in which every operation is done and committed to.
    """
    published_date = dt.datetime.fromisoformat(entry.published.text.strip("Z")) if entry.published else None
    title = entry.title.text if entry.title else None
    if title and session.query(Papers).filter(Papers.title == title).first():
        return

    paper = Papers(
        title=title,
        abstract=entry.summary.text if entry.summary else None,
        updated_date=dt.datetime.fromisoformat(entry.updated.text.strip("Z")) if entry.updated else None,
        year=published_date.year if published_date else None,
        published_date=published_date,
        doi=entry.doi.text if entry.doi else None,
        dataset="arxiv",
        links=[
            Links(type=link.get("type") or link.get("title"), url=link.get("href")) for link in entry.find_all("link")
        ],
        comment=entry.comment.text if entry.comment else None,
        publication=entry.journal_ref.text if entry.journal_ref else None,
        category=entry.category.get("term") if entry.category else None,
    )
    for author in entry.find_all("authors"):
        fn, ln = author.find("name").text.split()[:-1], author.find("name").text.split()[-1]
        ent_author = session.query(Authors).filter(Authors.firstname == fn, Authors.lastname == ln).first()
        if not ent_author:
            ent_author = Authors(
                firstname=fn,
                lastname=ln,
                institution=author.find("affiliation").text,
            )
        ent_author.papers.append(paper)
        paper.authors.append(author)
        session.add(ent_author)
    session.add(paper)


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
            save_arxiv_entry(entry, session)

        try:
            session.commit()
        except Exception as e:
            logger.error(f"SQLAlchemy error: {e}. Rerolling...")
            session.rollback()
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
    """Downloads the manifest according to the appropriate method.
    The manifest file can be downloaded from two ways.

    * From S3: You must configure your `AWS_ACCESS_KEY` and `AWS_SECRET_KEY` using your AWS account. The script will then download `src/arXiv_src_manifest.xml`.
    * From Kaggle: you must store your Kaggle API credentials as instructed by Kaggle (https://www.kaggle.com/docs/api). The file downloaded is taken from [ArXiV's dataset](https://www.kaggle.com/Cornell-University/arxiv).

    Parameters
    ----------
    dst_folder : Path
        The folder in which the manifest must be downloaded
    pref_method : str, optional
        Downloading method, from `kaggle` or AWS's `s3` bucket, by default "kaggle"
    """
    logger.info(f"Chosen method: {pref_method}")
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
            logger.info(f"Extracting from {dst_folder / 'arxiv.zip'}")
            with zipfile.ZipFile(dst_folder / "arxiv.zip", "r") as zip_ref:
                zip_ref.extractall(dst_folder / "arxiv_manifest")
            logger.info(f"Deleting {(dst_folder / 'arxiv.zip')}")
            (dst_folder / "arxiv.zip").unlink(missing_ok=False)
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
                Filename=(dst_folder / Path(bucket_file.lstrip("src/"))).as_posix(),  # path to file to download to
                ExtraArgs={"RequestPayer": "requester"},
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                logger.error("ERROR: " + bucket_file + " does not exist in arxiv bucket")


def explore_bucket_metadata(manifest_xml: Path):
    """Examines `manifest.xml` file

    Parameters
    ----------
    manifest_xml : Path
        Path of the XML manifest
    """
    logger.info("ArXiV bucker metadata:")
    total_size = 0

    with open(manifest_xml, "r") as manifest:
        soup = BeautifulSoup(manifest, "xml")

        arxiv_ts = soup.arXivSRC.find("timestamp", recursive=False).string
        logger.info(f"Manifest was last edited on {arxiv_ts}")

        num_files = len(soup.find_all("file"))
        logger.info(f"ArXiV bucket contains {num_files} tarfiles.")

        for size in soup.find_all("size"):
            total_size += int(size.string)
        logger.info(f"Total size: {total_size / 10e9:.2f} GB")


def _download_paginator(output_dir: Path):
    logger.info("Beginning tar download and extraction")
    s3ressource = boto3.resource(
        "s3",  # the AWS resource we want to use
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_KEY"),
        region_name="us-east-1",  # same region arxiv bucket is in
    )
    paginator = s3ressource.meta.client.get_paginator("list_objects_v2")

    page_iterator = paginator.paginate(Bucket="arxiv", RequestPayer="requester", Prefix="src/")

    for page in tqdm(page_iterator, total=len(page_iterator), desc="Page iterator"):
        for file in tqdm(page["Contents"], total=len(page["Contents"]), desc="File download"):
            key = file["Key"]
            if key.endswith(".tar"):
                logger.info(f"Downloading s3://arxiv/{key} to {key}...")

            try:
                s3ressource.meta.client.download_file(
                    Bucket="arxiv",
                    Key=key,
                    Filename=(output_dir / key).as_posix(),
                    ExtraArgs={"RequestPayer": "requester"},
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "404":
                    logger.error(f"{key} does not exist in arxiv bucket")


def download_source_code(manifest_xml: Path, output_dir: Path, confirm: bool = True):
    """Downloads ArXiV bulk data to `output_dir` using the manifest.

    Parameters
    ----------
    manifest_xml : Path
        [description]
    output_dir : Path
        [description]

    Raises
    ------
    Exception
        If there's not enough space on the disk, aborts the process.
    """
    logger.info(f"Beginning tar download and extraction using {manifest_xml}")

    with open(manifest_xml, "r") as manifest:
        soup = BeautifulSoup(manifest, "xml")

    # Compute space disk
    bulk_dl_size = 0
    number_files = 0
    total, used, free = [space / (2 ** 30) for space in shutil.disk_usage(output_dir)]
    logger.info(f"{used:.2f}/{total:.2f} GB used.")

    for size in soup.find_all("size"):
        bulk_dl_size += int(size.string)
        number_files += 1

    logger.info(f"Found {number_files} in {manifest_xml} ({bulk_dl_size/10e9:.2f} GB).")
    logger.info(f"Average file size: {(bulk_dl_size/number_files)/10e6:.2f} MB")

    if free < bulk_dl_size / 10e9:
        raise Exception(f"Insufficent space on disk ({bulk_dl_size / 10e9:.2f}/{free:.2f} GB)")

    logger.warning(f"After this operation, {bulk_dl_size / 10e9:.2f}/{free:.2f} GB will be used.")

    if not confirm:
        abort_process = ""
        while True:
            abort_process = input("Do you wish to continue? (Y/n)\n").strip()
            if abort_process == "Y" or abort_process == "n":
                break

        if abort_process == "n":
            logger.warning("Aborting process...")
            sys.exit()

    logger.info("Creating S3 resource.")
    s3ressource = boto3.resource(
        "s3",  # the AWS resource we want to use
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_KEY"),
        region_name="us-east-1",  # same region arxiv bucket is in
    )

    for filename in tqdm(soup.find_all("filename"), total=number_files, desc="File download"):
        file_key = filename.text
        logger.info(f"Downloading s3://arxiv/{file_key} to {output_dir / Path(file_key)}...")

        if not (output_dir / Path(file_key)).exists():
            try:
                s3ressource.meta.client.download_file(
                    Bucket="arxiv",
                    Key=file_key,
                    Filename=(output_dir / Path(file_key).name).as_posix(),
                    ExtraArgs={"RequestPayer": "requester"},
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "404":
                    logger.error(f"{file_key} does not exist in arxiv bucket")
                else:
                    raise
        else:
            logger.info(f"{(output_dir / Path(file_key)).as_posix()} already exists. Skipping.")

    # Verify integrity
    logger.info("Verifying file integrity.")
    integrity_report = output_dir / "integrity_report.json"
    problematic_files = []

    for xml_file in tqdm(soup.find_all("file"), total=number_files, desc="Verifying file integrity"):
        content_md5sum = xml_file.find("content_md5sum").text
        disk_file = output_dir / Path(xml_file.find("filename").text)
        file_hash_md5 = md5(disk_file)
        if content_md5sum != file_hash_md5:
            problematic_files.append(disk_file.as_posix())

    logger.warning(
        f"There was a problem with {len(problematic_files)}. Please check `integrity_report.json` for details."
    )
    with open(integrity_report, "w") as f:
        json.dump({"problematicFiles": problematic_files}, f)
