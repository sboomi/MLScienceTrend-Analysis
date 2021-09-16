from wordcloud import WordCloud
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


def feature_wordcloud(df: pd.DataFrame, title: str, to_png: Path = None) -> None:
    fig, ax = plt.subplots(figsize=(20, 10))

    if not hasattr(df, "feat_name") or not hasattr(df, "feat_count"):
        raise AttributeError("Dataframe must have `feat_name` and `feat_count` as columns")

    wc = WordCloud(background_color="white")
    wc.generate_from_frequencies(
        {name: count for name, count in zip(df.feat_name.apply(lambda s: "_".join(s.split())), df.feat_count)}
    )

    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    ax.set_title(title)

    if to_png:
        fig.savefig(to_png)

    plt.show()
