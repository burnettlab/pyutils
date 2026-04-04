from typing import *

import numpy as np
import numpy.typing as npt
import scipy.interpolate as interp
from auto_all import public


@public
def geomean(x: npt.ArrayLike) -> float:
    arr = np.atleast_1d(x)
    return np.power(np.prod(arr), 1/arr.size)


@public
def resample(x_i: npt.ArrayLike, y_i: npt.ArrayLike, num_points: int=100, decade_th: int=2) -> Tuple[npt.ArrayLike, npt.ArrayLike]:
    """ Resample the input data to a specified number of points using linear/logarithmic interpolation. 
        Uses log-spaced interpolation if the range spans more than `decade_th` decades.
    """
    xi, yi = map(lambda arr: np.atleast_1d(getattr(arr, "magnitude", arr)), (x_i, y_i))
    assert xi.shape == yi.shape, "xi and yi must have the same shape"
    if xi.size == 0:
        return xi, yi

    xi_func = np.linspace if np.nonzero(xi)[0].size != xi.size or (np.abs(np.log10(np.max(xi)) - np.log10(np.min(xi))) <= decade_th) else np.logspace
    x_new = xi_func(xi[0], xi[-1], num_points)
    y_new = priority_interp(xi, yi, x_new)

    return x_new * getattr(x_i, "units", 1), y_new * getattr(y_i, "units", 1)


@public
def priority_interp(x_i: npt.ArrayLike, y_i: npt.ArrayLike, x_: npt.ArrayLike, axis: Optional[int]=None, nu: int=0, extrapolate: bool=True, left: Optional[float]=None, right: Optional[float]=None, **kwargs) -> npt.ArrayLike:
    """ Interpolate using PCHIP if possible, otherwise fall back to linear interpolation. 
    Args:
        xi: x-coordinates of the data points, must be 1-D.
        yi: y-coordinates of the data points, same length as xi.
        x: x-coordinates where to interpolate, can be multi-dimensional.
        axis: Axis along which to interpolate.
        nu: Order of derivative to compute (for PCHIP).
        extrapolate: Whether to extrapolate outside the range of xi (for PCHIP).
        left: Value to return for x < xi[0] (for np.interp).
        right: Value to return for x > xi[-1] (for np.interp).
    Returns:
        Interpolated values at x.
    """
    assert getattr(x_, "units", None) == getattr(x_i, "units", None), "x_ must have the same units as x_i"
    return_units = getattr(y_i, "units", 1)

    xi, yi, x = map(lambda arr: np.atleast_1d(getattr(arr, "magnitude", arr)), (x_i, y_i, x_))
    unique_xi = np.unique(xi, return_index=True, axis=axis)[1]
    xi, yi = map(lambda a: a[unique_xi], (xi, yi))

    try:
        interpolator = interp.PchipInterpolator(xi, yi, axis=axis or 0, extrapolate=extrapolate)
        return interpolator(x, nu=nu) * return_units
    except ValueError:
        kwdict = {}
        if not extrapolate or left is not None:
            kwdict["left"] = left
        if not extrapolate or right is not None:
            kwdict["right"] = right
        return np.interp(x, xi, yi, **kwdict) * return_units


@public
def local_max(x: npt.ArrayLike, y: npt.ArrayLike, resample_input: bool=False, num_points: int=1000) -> Tuple[npt.ArrayLike, npt.ArrayLike]:
    """ Find local maxima in the data. """
    if resample_input:
        x, y = resample(x, y, num_points=num_points)
    return local_extrema(x, y, max=True)


@public
def local_min(x: npt.ArrayLike, y: npt.ArrayLike, num_points: int=1000) -> Tuple[npt.ArrayLike, npt.ArrayLike]:
    """ Find local minima in the data. """
    return local_extrema(*resample(x, y, num_points=num_points), max=False)


@public
def local_extrema(x_: npt.ArrayLike, y_: npt.ArrayLike, max=True) -> Tuple[npt.ArrayLike, npt.ArrayLike]:
    """ Find local extrema in the data. """
    x, y = map(lambda arr: np.atleast_1d(getattr(arr, "magnitude", arr)), (x_, y_))
    assert x.shape == y.shape, "x and y must have the same shape"
    x_unit = getattr(x_, "units", 1)
    y_unit = getattr(y_, "units", 1)

    d2y = np.diff(y, n=2, prepend=y[0], append=y[-1])
    dy = np.diff(y, prepend=y[0], append=y[-1])
    extrema_indices = np.where((np.sign(dy[:-1]) != np.sign(dy[1:])) & (d2y < 0 if max else d2y > 0))
    return x[extrema_indices].squeeze() * x_unit, y[extrema_indices].squeeze() * y_unit


@public
def symmetric_logscale(min_val: float, max_val: float, num_points: int=100) -> npt.ArrayLike:
    """ Generate a symmetric log scale from min_val to max_val with num_points points. Most samples are near the endpoints. """
    assert min_val > 0 and max_val > 0, "min_val and max_val must both be positive"     # type: ignore
    low_half = np.logspace(np.log10(min_val), np.log10(max_val / 2), num_points // 2 + 1)      # type: ignore
    return np.concatenate((low_half, max_val - low_half[-2::-1]))


@public
def converge_iter(max_iter=5) -> Generator[None, Tuple[Any, ...], None]:
    """ Generator to iteratively converge a set of values.  
        Yields control back to the caller until convergence is reached or max_iter is exceeded.
    """
    assert max_iter > 0, "max_iter must be greater than 0"
    args = yield
    if not isinstance(args, tuple):
        args = (args,)

    for iter_count in range(max_iter):
        new_args = yield
        if not isinstance(new_args, tuple):
            new_args = (new_args,)

        if all(compare_args(a, b) for a, b in zip(args, new_args, strict=True)):
            print(f"Converged after {iter_count+1} iterations.")
            break
        args = new_args
