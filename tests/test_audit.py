import numpy as np
import pandas as pd

from qc import audit


def test_image_scale_is_nullable_when_tag_absent():
    assert audit._first_scale(pd.Series([np.nan, np.nan])) is None
    assert audit._first_scale(pd.Series([np.nan, 25.0])) == 25.0
