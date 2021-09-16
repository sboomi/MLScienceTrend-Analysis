"""Text preprocessing goes there"""
import os
import re
import string
from functools import partial

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer

from .concurrency import parallelize_pd_data, transform_pd_data


def whitespace_ratio(text: str, verbose: bool = False) -> float:
    """
    Takes a text and estimates the number of whitespaces over the
    number of characters. Uses the common token `\s` for estimation.
    """
    len_text = len(text)
    count_whitespaces = 0

    for match in re.finditer(r"\s", text, re.MULTILINE):
        count_whitespaces += match.end() - match.start()

    if verbose:
        print(f"Total whitespaces: {count_whitespaces} / {len_text} ({count_whitespaces/len_text:.2%})")

    return count_whitespaces / len_text


def clean_whitespace(text: str) -> str:
    """
    Removes the whitespace on the text
    """
    txt_no_spaces = re.sub(r"[ \t\f\r]+", " ", text)
    return re.sub(r"\n+", "\n", txt_no_spaces)


def char_proportion(text: str) -> float:
    """
    Returns a tuple with the following
    - Number of non-space characters
    - Number of digits
    - Number of punctuation characters
    """
    count_chrs = 0
    count_no_chrs = 0

    # Pattern for punctuation with Python's string module
    chr_patt = re.compile(r"\S+", re.M)
    punct_escape_chr = "".join(["\\" + char for char in string.punctuation])
    no_chr_patt = re.compile(fr"[\d{string.punctuation}]+", re.M)

    for match in chr_patt.finditer(text):
        count_chrs += match.end() - match.start()
        non_space_txt = match.group()

        for no_chr_match in no_chr_patt.finditer(non_space_txt):
            count_no_chrs += no_chr_match.end() - no_chr_match.start()

    try:
        count_no_chrs / count_chrs
    except ZeroDivisionError:
        return 0.0

    return count_no_chrs / count_chrs


def clean_all_papers(papers: pd.Series):
    """Clean all papers according to preprocessing steps

    Parameters
    ----------
    papers : pd.Series
        [description]

    Returns
    -------
    [type]
        [description]
    """
    # Clean non-entries
    no_na_papers = SimpleImputer(strategy="constant", fill_value="NO DATA").fit_transform(
        papers.drop("abstract", axis=1)
    )

    clean_papers = pd.DataFrame(data=no_na_papers, columns=[col for col in papers.columns if col != "abstract"])

    # Get paper length
    paper_length = clean_papers.full_text.apply(lambda text: len(text))
    paper_ws_ratio = parallelize_pd_data(
        clean_papers.full_text, partial(transform_pd_data, f=whitespace_ratio), n_cores=os.cpu_count()
    )
    # Clean whitespaces
    clean_papers.full_text = clean_papers.full_text.apply(clean_whitespace)

    # Get paper stats
    paper_ws = pd.concat([paper_length.rename("length"), paper_ws_ratio.rename("ws_ratio")], axis=1)
    kmeans = KMeans(n_clusters=2, random_state=1).fit(paper_ws.apply(np.log))
    paper_ws["clusters"] = kmeans.labels_
    chr_no_chr_prop = clean_papers.full_text.apply(char_proportion)

    # Delete incorrect text
    shortest_papers_idx = paper_length[paper_length < 1500].index
    compact_text_idx = paper_ws[paper_ws.clusters == 1].index
    gibberish_idx = chr_no_chr_prop[chr_no_chr_prop > 0.25].index

    idx_to_drop = list(set(shortest_papers_idx.to_list() + compact_text_idx.to_list() + gibberish_idx.to_list()))
    idx_to_drop = pd.Index(idx_to_drop)

    clean_papers = clean_papers.drop(idx_to_drop, axis=0)
    return clean_papers
