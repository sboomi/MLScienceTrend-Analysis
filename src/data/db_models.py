from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Table
from sqlalchemy.orm import relationship
from . import Base


class PaperAuthor(Base):
    __tablename__ = "paper_author"
    paper_id = Column(Integer, ForeignKey("papers.id"), primary_key=True)
    author_id = Column(Integer, ForeignKey("authors.id"), primary_key=True)


class Papers(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True)
    hash = Column(String(36))
    year = Column(Integer)
    published_date = Column(DateTime)
    updated_date = Column(DateTime)
    title = Column(String(100))
    authors = relationship("Authors", secondary="paper_author")
    abstract = Column(Text(2000))
    full_text = Column(Text)
    doi = Column(String(50))
    category = Column(String(40))
    dataset = Column(String(40), nullable=False)
    publication = Column(String(100))
    comment = Column(Text)
    links = relationship("Links")

    def __repr__(self):
        return f"Paper(dataset={self.dataset})"


class Authors(Base):
    __tablename__ = "authors"
    id = Column(Integer, primary_key=True)
    firstname = Column(String(30), nullable=False)
    lastname = Column(String(30), nullable=False)
    institution = Column(String(60))
    papers = relationship("Papers", secondary="paper_author")

    def __repr__(self):
        return f"{self.firstname} {self.lastname}"


class Links(Base):
    __tablename__ = "links"
    id = Column(Integer, primary_key=True)
    type = Column(String(20), nullable=False)
    url = Column(String(150), nullable=False)
    paper = Column(Integer, ForeignKey("papers.id"))

    def __repr__(self):
        return f"{self.type}: {self.url}"
