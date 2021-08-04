from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from . import Base


class Papers(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True)
    hash = Column(String(36), nullable=False)
    year = Column(Integer, nullable=False)
    title = Column(String(100))
    authors = relationship("Authors")
    abstract = Column(Text(2000))

    def __repr__(self):
        return f"Paper(hash={self.hash}, year={self.year})"


class Authors(Base):
    __tablename__ = "authors"
    id = Column(Integer, primary_key=True)
    firstname = Column(String(30), nullable=False)
    lastname = Column(String(30), nullable=False)
    paper = Column(Integer, ForeignKey("papers.id"))

    def __repr__(self):
        return f"{self.firstname} {self.lastname}"
