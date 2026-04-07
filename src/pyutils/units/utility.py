import inspect
import os
import re
from functools import cached_property, partial, wraps
from typing import Any, Callable, Iterable, List, Optional, Union

import numpy as np
from auto_all import public
from pint import Quantity
from pint.facets.plain import PlainQuantity, PlainUnit

from pyutils.decorators import update_signature_from_partial, wrap_once
from pyutils.funcs import get_anno_class

from . import NUMBER_RE, UREG
from .unit_types import NUM
from .unit_types import *


def has_unit(x: NUM):
    return isinstance(x, (Quantity, PlainQuantity)) or (isinstance(x, np.ndarray) and issubclass(x.dtype.type, (Quantity, PlainQuantity)))

@public
def convert_temp(temp: Union[str, NUM], temp_unit: str="C", **kwargs) -> Kelvin:
    if isinstance(temp, (Quantity, PlainQuantity)):
        return Kelvin(temp) #temp.to(UREG.kelvin)

    if isinstance(temp, str):
        if temp == "room":
            temp = "27"
            temp_unit = "C"
        else:
            if (v := re.match(NUMBER_RE, temp.strip())) is not None:
                temp, temp_unit = v.group(0), temp.replace(v.group(1), "").strip()
    
    return Kelvin(f"{temp} {temp_unit}")


@public
def magnitude(x: NUM) -> NUM:
    """Return the magnitude of a Quantity or UnitType, else return x unchanged."""
    if isinstance(x, (Quantity, PlainQuantity)):
        return x.to_preferred().magnitude
    return x


@public
def has_units_in_sig(func: Callable[..., Any]) -> bool:
    """ Check if a function has any unit annotations in its signature. """
    try:
        sig = inspect.signature(func)
    except ValueError:
        return False
    return any(map(get_units, [p.annotation for p in sig.parameters.values()] + [sig.return_annotation]))


@public
def get_units(anno: inspect.Parameter):
    """ Gets the units associated with a type annotation (if any). """
    cls = get_anno_class(anno)
    return getattr(cls, "__unit__", getattr(cls, "units", None))
    return next(map(get_units, getattr(anno, "__args__", [])), getattr(anno, "__unit__", getattr(anno, "units", None)))


@public
def obj_using_units(obj: object, *args, USING_UNITS: Optional[bool]=None, **kwargs) -> bool:
    """ Determine if units are being used based on the object's USE_UNITS attribute. 
    Args:
        obj (object): The object to check for the USE_UNITS attribute.
        USING_UNITS (Optional[bool], optional): Override flag to specify if units are being used. Defaults to None.
    Returns:
        bool: True if units are being used, False otherwise.
    """
    if USING_UNITS is not None:
        return USING_UNITS
    return getattr(obj, "USE_UNITS", globals().get("USE_UNITS", os.getenv("USE_UNITS")))


@public
@wrap_once
def arg_unit_conv(func: Callable[..., Any], *, pref_units: Optional[List[str]]=None) -> Callable[..., Any]:
    """Decorator to convert preferred UnitType in arguments to floats.
    Args:
        func (Callable[..., Any]): The function to decorate.
        pref_units (Optional[List[str]], optional): List of preferred units to convert to. Defaults to None.
    Returns:
        Callable[..., Any]: The decorated function
    """
    if func is None:
        return partial(arg_unit_conv, pref_units=pref_units)
    
    pref = UREG.default_preferred_units if not pref_units else pref_units
    @wraps(func)
    def wrapper(*args, **kwargs):
        def arg_conv(arg):
            if has_unit(arg):
                return arg.to_preferred(pref).magnitude
            elif isinstance(arg, dict):
                return dict_conv(arg)
            else:
                return arg
        dict_conv = lambda d: {k: arg_conv(v) for k, v in d.items()}
        return func(*map(arg_conv, args), **dict_conv(kwargs))
    return wrapper


@public
@wrap_once
def return_unit_conv(func: Optional[Callable[..., Any]]=None, *, pref_units: Optional[List[str]]=None) -> Callable[..., Any]:
    """Decorator to convert floats to preferred UnitType in returns.
    Args:
        func (Callable[..., Any]): The function to decorate.
        pref_units (Optional[List[str]], optional): List of preferred units to convert to. Defaults to None.
    Returns:
        Callable[..., Any]: The decorated function
    """
    if func is None:
        return partial(return_unit_conv, pref_units=pref_units)
    
    pref = UREG.default_preferred_units if not pref_units else pref_units
    @wraps(func)
    def wrapper(*args, USING_UNITS: Optional[bool]=None, **kwargs):
        # Use the attr of the first positional argument to determine if units are being used. Default to global USE_UNITS.
        USING_UNITS = obj_using_units(*args, USING_UNITS=USING_UNITS)
        res = func(*args, **kwargs)
        
        if has_unit(res):
            res = res.to_preferred(pref)
            if not USING_UNITS:
                return res.magnitude
            return res
        return res
    return wrapper


@public
@wrap_once
def dynamic_unit_wrap(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to dynamically wrap functions with unit arguments at call-time.
    Args:
        func (Callable[..., Any]): The function to decorate.
    Returns:
        Callable[..., Any]: The decorated function
    """
    if not callable(func) or getattr(func, "__dynamic_unit_wrap__", False):
        return func
    
    setattr(func, "__dynamic_unit_wrap__", True)
    if not has_units_in_sig(func):
        return func
    
    signature = inspect.signature(func)
    pos_kw = lambda sig: filter(lambda p: p[1].kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD), sig.parameters.items())

    # Get the units for each argument & return value
    getargs = lambda t: getattr(t, "__args__", [t])
    anno_units = lambda it: map(get_units, it if isinstance(it, Iterable) else [it])

    return_units_base = tuple(filter(None, anno_units(getargs(signature.return_annotation))))

    @wraps(func)
    def dynamic_unit_wrapper(*args, **kwargs):
        # Bind the arguments to the signature to apply defaults
        bound = signature.bind_partial(*args, **kwargs)
        bound.apply_defaults()

        f_partial = update_signature_from_partial(partial(
            func,
            **dict(map(lambda k: (k, bound.arguments[k]), bound.arguments.keys() - map(lambda p: p[0], pos_kw(signature))))
        ))
        sig = inspect.signature(f_partial)
        
        return_units = return_units_base[:]
        if len(return_units) == 1:
            return_units = return_units[0]
        if not return_units:
            return_units = None
        
        arg_units = tuple(anno_units(map(lambda p: p.annotation, sig.parameters.values())))

        # Wrap the call function for converting argument units
        if obj_using_units(args[0], USING_UNITS=kwargs.pop('USING_UNITS', None)):
            f_partial = UREG.check(*arg_units)(f_partial)
            arg_units = (None,) * len(arg_units)
        f_partial = UREG.wraps(return_units, arg_units, strict=False)(f_partial)

        return f_partial(*bound.args, **bound.kwargs)
    
    return dynamic_unit_wrapper


@public
@wrap_once
def apply_unit_wraps(cls: object) -> object:
    """
    Apply unit conversion decorators to all callable attributes of the class that have unit annotations.
    """
    def class_callables(c):
        for k in getattr(c, "__dict__", {k: None for k in dir(c)}).keys():
            if callable(attr := getattr(c, k, None)):
                try:
                    yield k, attr
                except ValueError:
                    pass
            elif isinstance(attr, property):
                yield k, attr
            elif isinstance(attr, cached_property):
                yield k, attr 

    for key, attr in class_callables(cls):
        if isinstance(attr, property):
            # Property attribute
            setattr(cls, key, property(*map(lambda n: dynamic_unit_wrap(getattr(attr, n)), filter(lambda n: getattr(attr, n, None), ("fget", "fset", "fdel", "__doc__")))))
        elif isinstance(attr, cached_property):
            # Cached property attribute
            attr = cached_property(dynamic_unit_wrap(attr.func))
            attr.__set_name__(cls, key)
            setattr(cls, key, attr)
        else:
            setattr(cls, key, dynamic_unit_wrap(attr))

    return cls

def unit_str_addon(unit: Union[NUM, UREG.Unit, PlainUnit]) -> str:
    """ Turn a unit (or quantity with a unit) into a string formatted like [`UNIT`] """
    if not isinstance(unit, (UREG.Unit, PlainUnit)) and not hasattr(unit, "units"):
        return ""
    unit = getattr(unit, "units", unit)
    return " [-]" if unit == UREG.dimensionless else fr" [{unit:~P}]"
