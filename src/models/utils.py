import sparknlp
import logging
import coloredlogs
from pyspark.ml import Pipeline
from pathlib import Path

log_fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=log_fmt)
logger = logging.getLogger(__name__)
coloredlogs.install()


def load_spark_pipeline(name_job: str, pipeline: Pipeline, data_fn: Path):
    # Init spark NLP with default parameters
    logger.info(f"Beginning task for {name_job}")
    spark = sparknlp.start()

    # Load dataframe
    df = spark.read.json(data_fn)

    result = pipeline.fit(df).transform(df)

    return result
