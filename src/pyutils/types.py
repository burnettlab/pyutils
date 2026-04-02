import numbers
from typing import TypeVar, Union

import numpy as np
import numpy.typing as npt
from auto_all import end_all, start_all

start_all()
T = TypeVar("T")
NUM = TypeVar("NUM", numbers.Number, np.number)
Vector = Union[T, npt.NDArray[T]]
end_all()