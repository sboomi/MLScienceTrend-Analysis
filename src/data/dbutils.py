import re
import base64
from os import PathLike
from pathlib import Path
from typing import Any, Literal, Union, Dict

import pymongo
import requests
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from requests.exceptions import ConnectionError
from json.decoder import JSONDecodeError

DATABASES = Literal["sqlite", "mssql", "oracle", "mysql", "postgresql"]


class MongoConnector:
    """Connector handling special instances of MongoDB"""

    uri_regex = re.compile(
        r"^mongodb\+srv:\/\/([a-zA-Z0-9_-]+):([a-zA-Z0-9]+)@([a-z]+)\.(\w+)\.mongodb.net\/(\w+)\?retryWrites=true&w=majority$",
        re.M,
    )

    @staticmethod
    def encode_pw(pw):
        return base64.b64encode(pw.encode("utf-8"))

    @staticmethod
    def decode_pw(enc_pw):
        return base64.b64decode(enc_pw).decode("utf-8")

    def __init__(self):
        self.uri = ""
        self.username = ""
        self.password = b""
        self.project_id = ""
        self.host = ""
        self.port = 0
        self.db = ""
        self.cluster_name = ""
        self.with_atlas = False

    def connect_from_atlas(self, uri: str) -> None:
        if not self.uri_regex.findall(uri) and len(self.uri_regex.findall(uri)) != 5:
            raise Exception("The URI you've entered isn't correct")

        self.username, raw_pw, self.cluster_name, self.project_id, self.db = self.uri_regex.findall(uri)[0]
        self.password = self.encode_pw(raw_pw)
        self.with_atlas = True
        rep_uri_pattern = fr"mongodb+srv://\1:{self.password.decode()}@\3.\4.mongodb.net/\5?retryWrites=true&w=majority"
        self.uri = self.uri_regex.sub(rep_uri_pattern, uri)

    def connect_locally(self, host: str = "localhost", port: int = 27017):
        self.host = host.strip()
        self.port = port
        self.uri = f"mongodb://{host}:{port}/"

    def create_client(self) -> pymongo.MongoClient:
        if not self.uri:
            raise Exception(
                """URI empty.
            Connect locally or using Atlas first using `connect_from_atlas(uri)` or
            `connect_locally(host, port)`."""
            )

        if self.with_atlas:
            raw_pw = self.decode_pw(self.password)
            uri = f"mongodb+srv://{self.username}:{raw_pw}@{self.cluster_name}.{self.project_id}.mongodb.net/{self.db}?retryWrites=true&w=majority"
            return pymongo.MongoClient(uri)

        return pymongo.MongoClient(self.uri)

    def __repr__(self) -> str:
        att_list = [f"{attr}={value}" for attr, value in self.__dict__.items()]
        return f"MongoConnector({', '.join(att_list)})"

    def __str__(self) -> str:
        if not self.uri:
            return "Connector not initialized"
        elif self.with_atlas:
            return f"Atlas URI: {self.uri}"
        else:
            return f"Local machine (host={self.host}, port={self.port})"


class NeuripsAPIConnector:
    request_type = ["pdf", "metadata", "bibtex"]
    base_url = "https://papers.nips.cc/"

    @classmethod
    def get_metadata(cls, hash: str, year: int) -> Dict:
        json_url = f"{cls.base_url}paper/{year}/file/{hash}-Metadata.json"
        try:
            req_json = requests.get(json_url)
        except ConnectionError as e:
            return {"error": f"{e}", "url": json_url}

        # Returns the empty dict if the request fails
        if req_json.status_code != 200:
            raise Exception(f"Code {req_json.status_code}: page not found or too many requests")
        return cls.test_json_request(req_json, json_url)

    @classmethod
    def request(cls, req_type: str, hash: str, year: int) -> Any:
        if req_type not in cls.request_type:
            raise Exception(f"Error. Request type must be one of the following: {cls.request_type}")

        if req_type == "metadata":
            cls.get_metadata(hash, year)

    @staticmethod
    def test_json_request(r: requests.Response, url: str) -> Dict:
        try:
            json_response = r.json()
        except JSONDecodeError as e:
            json_response = {"error": f"{e}", "url": url, "contents": r.text}

        return json_response


def load_sql_engine(
    dialect: DATABASES = "sqlite",
    username: str = "",
    password: str = "",
    port: int = 0,
    database: Union[str, PathLike[str]] = "",
    host: str = "localhost",
) -> Engine:
    """Creates a SQL instance based on uri parameters

    Parameters
    ----------
    dialect : DATABASES
        The dialect of the SQL database. Can only take the following values: "sqlite", "mssql", "oracle", "mysql", "postgresql"
    username : str, optional
        The username of the database
    password : str, optional
        The password of the database
    port : int, optional
        The port number of the database
    database : Union[str, PathLike[str]], optional
        The name of the database (or path if the db is a SQLite db), by default ""
    host : str, optional
        The name of the host of the db, by default "localhost"

    Returns
    -------
    Engine
        an SQL engine instance
    """
    if dialect == "sqlite":
        db_uri = f"sqlite:///{Path(database).as_posix()}" if Path(database) and Path(database).exists() else "sqlite://"
        engine = create_engine(db_uri)
    elif username and password and port:
        db_uri = f"{dialect}://{username}:{password}@{host}:{port}/{database}"
        engine = create_engine(db_uri)
    else:
        raise NameError("One or multiple fields aren't referenced.")
    return engine
