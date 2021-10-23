"""LDA using PySpark and Spark NLP"""
from pyspark.ml import Pipeline
from sparknlp.base import DocumentAssembler, Finisher
from sparknlp.annotator import Tokenizer, Normalizer, LemmatizerModel, StopWordsCleaner, NGramGenerator, PerceptronModel
import nltk
from nltk.corpus import stopwords


def get_stopwords(lang: str):
    try:
        stopword_list = stopwords.words(lang)
    except LookupError:
        nltk.download("stopwords")

    return stopword_list


def filter_pos_combs(words, pos_tags):
    return [
        word
        for word, pos in zip(words, pos_tags)
        if (
            len(pos.split("_")) == 2
            and pos.split("_")[0] in ["JJ", "NN", "NNS", "VB", "VBP"]
            and pos.split("_")[1] in ["JJ", "NN", "NNS"]
        )
        or (
            len(pos.split("_")) == 3
            and pos.split("_")[0] in ["JJ", "NN", "NNS", "VB", "VBP"]
            and pos.split("_")[1] in ["JJ", "NN", "NNS", "VB", "VBP"]
            and pos.split("_")[2] in ["NN", "NNS"]
        )
    ]


def create_processing_pipeline(in_col: str):
    document_assembler = DocumentAssembler().setInputCol(in_col).setOutputCol("document")

    tokenizer = Tokenizer().setInputCols(["document"]).setOutputCol("tokenized")

    normalizer = Normalizer().setInputCols(["tokenized"]).setOutputCol("normalized").setLowercase(True)

    lemmatizer = LemmatizerModel.pretrained().setInputCols(["normalized"]).setOutputCol("lemmatized")

    sw_list = get_stopwords("en")

    stopwords_cleaner = StopWordsCleaner().setInputCols(["lemmatized"]).setOutputCol("unigrams").setStopWords(sw_list)

    ngrammer = (
        NGramGenerator()
        .setInputCols(["lemmatized"])
        .setOutputCol("ngrams")
        .setN(3)
        .setEnableCumulative(True)
        .setDelimiter("_")
    )

    pos_tagger = PerceptronModel.pretrained("pos_anc").setInputCols(["document", "lemmatized"]).setOutputCol("pos")

    finisher = Finisher().setInputCols(["unigrams", "ngrams", "pos"])

    pipeline = Pipeline().setStages(
        [document_assembler, tokenizer, normalizer, lemmatizer, stopwords_cleaner, pos_tagger, ngrammer, finisher]
    )

    return pipeline
