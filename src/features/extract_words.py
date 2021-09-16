import logging
from pathlib import Path
from typing import List

import coloredlogs
import pandas as pd
from pydantic import BaseModel
from sklearn.feature_extraction.text import CountVectorizer

STOP_WORDS = ["for", "of", "and", "with", "in", "the", "to", "on", "from", "via", "by", "an"]

log_fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=log_fmt)
logger = logging.getLogger(__name__)
coloredlogs.install()


class FeatureCount(BaseModel):
    feat_name: List[str] = []
    feat_count: List[int] = []


def extract_keywords(csv_file: Path, n_grams: int = 1, to_file: Path = None, sort_df: bool = True) -> pd.DataFrame:
    """[summary]

    Parameters
    ----------
    csv_file : Path
        [description]
    n_grams : int, optional
        [description], by default 1
    to_file : Path, optional
        [description], by default None
    sort_df : bool, optional
        [description], by default True

    Returns
    -------
    pd.DataFrame
        [description]
    """
    feature_count = FeatureCount()

    df = pd.read_csv(csv_file)
    vectorizer = CountVectorizer(analyzer="word", ngram_range=(n_grams, n_grams), stop_words=STOP_WORDS)

    try:
        title_vectorized = vectorizer.fit_transform(df.title)
    except AttributeError:
        logger.error("CSV must have a title attribute")
        return

    feature_count.feat_name.extend(vectorizer.get_feature_names())
    feature_count.feat_count.extend(title_vectorized.toarray().sum(axis=0).tolist())

    feature_count_df = pd.DataFrame(feature_count.dict())

    if sort_df:
        feature_count_df = feature_count_df.sort_values(by="feat_count", ascending=False)

    if to_file:
        feature_count_df.to_csv(to_file, index=None)

    return feature_count_df
