from os import PathLike
from pathlib import Path
from typing import Literal, Union

import pymongo
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

DATABASES = Literal["sqlite", "mssql", "oracle", "mysql", "postgresql"]


def load_mongo_client(mongo_username: str, mongo_password: str) -> pymongo.MongoClient:
    """Loads MongoDB's client from Mongo credentials

    Parameters
    ----------
    mongo_username : str
        MongoDB's database username
    mongo_password : str
        MongoDB's database password

    Returns
    -------
    pymongo.MongoClient
        Database client of MongoDB
    """
    mongo_uri = f"mongodb+srv://{mongo_username}:{mongo_password}@maincluster.otbuf.mongodb.net/myFirstDatabase?retryWrites=true&w=majority"
    client = pymongo.MongoClient(mongo_uri)
    return client


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
