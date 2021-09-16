import datetime as dt
import logging

import coloredlogs
import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from sqlalchemy.engine import Engine
from sqlalchemy.orm.session import sessionmaker
from src.data.db_models import Papers
from bs4.element import Tag
from .db_models import Papers, Links, Authors


log_fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=log_fmt)
logger = logging.getLogger(__name__)
coloredlogs.install()


def return_arxiv_entry(entry: Tag) -> Papers:
    return Papers(
        title=entry.title.text,
        abstract=entry.summary.text,
        updated_date=dt.datetime.fromisoformat(entry.updated.text.strip("Z")),
        published_date=dt.datetime.fromisoformat(entry.published.text.strip("Z")),
        doi=entry.doi.text,
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
        comment=entry.comment.text,
        publication=entry.journal_ref.text,
        category=entry.category.get("term"),
    )


def request_arxiv(url: str, engine: Engine):
    r = requests.get(url)
    if r.status_code == 200:
        Session = sessionmaker(engine)
        session = Session()
        soup = BeautifulSoup(r.content, "xml")
        logger.info(f"Found {soup.find('totalResults').text} results.")
        logger.info(f"Starts at {soup.find('startIndex').text} (results per page: {soup.find('ItemsPerPage').text})")
        for entry in soup.find_all("entry"):
            db_entry = return_arxiv_entry(entry)
            session.add(db_entry)

        session.commit()
    else:
        err_xml = BeautifulSoup(r.content, "xml")
        msg = err_xml.find("entry").find("summary").text
        logger.error(f"Error: {msg}")
