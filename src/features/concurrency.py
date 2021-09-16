from typing import Callable, Union, Optional
from multiprocessing import Pool
import pandas as pd
import numpy as np

# Function to parallelize the series
# Many thanks to Rahul Agarwal for the tip
# https://towardsdatascience.com/make-your-own-super-pandas-using-multiproc-1c04f41944a1
def parallelize_pd_data(
    dat: Union[pd.Series, pd.DataFrame], func: Callable, n_cores: Optional[int] = 4
) -> Union[pd.Series, pd.DataFrame]:
    """Uses Kaggle's CPU cores to divide the work and accelerate the process.

    Parameters
    ----------
    dat : Union[pd.Series, pd.DataFrame]
        Data structure to pass
    func : Callable
        Callback function to use
    n_cores : int, optional
        Number of jobs you want to perform on (CPU cores), by default 4

    Returns
    -------
    Union[pd.Series, pd.DataFrame]
        Final data
    """
    dat_split = np.array_split(dat, n_cores)
    pool = Pool(n_cores)
    dat = pd.concat(pool.map(func, dat_split))
    pool.close()
    pool.join()
    return dat


def transform_pd_data(dat: Union[pd.Series, pd.DataFrame], f: Callable) -> Union[pd.Series, pd.DataFrame]:
    """Calls pandas' apply method

    Needs to be ran with the following code, since lambads don't work on `Pool.map`:

    ```python
    import os
    from functools import partial
    partial(transform_pd_data, f=<your_apply_callback>), n_cores = os.cpu_count())
    ```

    Parameters
    ----------
    dat : Union[pd.Series, pd.DataFrame]
        Data structure to pass
    f : Callable
        Callback function to use your processing on

    Returns
    -------
    Union[pd.Series, pd.DataFrame]
        The processed data
    """
    return dat.apply(f)
