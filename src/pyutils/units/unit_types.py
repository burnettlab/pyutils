import re
from dataclasses import dataclass
from functools import cached_property
from typing import TypeVar, Union

import numpy as np
import numpy.typing as npt
from auto_all import end_all, public, start_all
from pint import Quantity, Unit
from pint.errors import OffsetUnitCalculusError
from pint.facets.plain import PlainQuantity, PlainUnit

from pyutils.types import NUM, T, Vector

from . import NUMBER_RE, UREG

NUM = TypeVar("NUM", *NUM.__constraints__, Quantity, PlainQuantity)


@public
@dataclass
class UnitType(Quantity):
    """Base class for unit types."""
    value: Union[Quantity, PlainQuantity]
    __unit__: Union[str, Unit, PlainUnit] = ""

    @cached_property
    def units(self):    # type: ignore
        if isinstance(self.__unit__, str):
            return UREG(self.__unit__)
        return self.__unit__

    def __new__(cls, num: NUM):
        if getattr(getattr(num, "dtype", None), "type", None) == np.bytes_:
            num = str(num.astype(str))      # type: ignore

        if isinstance(num, (Quantity, PlainQuantity)):
            cls.value = num.to(cls.units.func(cls))
        elif isinstance(num, str):
            if (v := re.match(NUMBER_RE, num.strip())) is None:
                raise ValueError(f"Cannot parse quantity from string: {num}")
            non_num = num.replace(v.group(1), "").strip()
            if non_num and non_num in UREG:
                if cls.units.func(cls)== UREG.kelvin:  # special case for Kelvin
                    try:
                        cls.value = np.float64(v.group(1)) * UREG(f"deg{non_num}")
                    except OffsetUnitCalculusError:
                        cls.value = UREG.Quantity(0, UREG.degC).to(cls.units.func(cls)) + (np.float64(v.group(1)) * UREG(f"delta_deg{non_num}"))  # type: ignore
                else:
                    cls.value = np.float64(v.group(1)) * UREG(non_num)
            else:
                cls.value = np.float64(v.group(1)) * UREG(f"{non_num}{cls.units.func(cls)}")
        else:
            cls.value = num * cls.units.func(cls)
        return cls.value
    
    def __init_subclass__(cls, __unit__: Union[str, Unit, PlainUnit], *args, **kwargs) :
        cls.__unit__ = __unit__
        return super().__init_subclass__()


start_all()
NUM = TypeVar("NUM", *NUM.__constraints__, UnitType)
Vector = Union[*Vector.__args__, PlainQuantity[npt.NDArray[T]]]

for unit in filter(lambda t: isinstance(t, (UREG.Unit, PlainUnit)), map(lambda k: getattr(UREG, k, None), list(UREG) + ["dimensionless"])):
    name = ''.join(map(lambda s: s.capitalize(), f"{unit:D}".split('_')))
    globals()[name] = type(name, (UnitType,), {}, __unit__=unit)

end_all()

### Formerly used UnitType instantiaions
# Dimensionless = type("Dimensionless", (UnitType,), {}, __unit__="dimensionless")
# Kelvin = type("Kelvin", (UnitType,), {}, __unit__="kelvin")
# Volt = type("Volt", (UnitType,), {}, __unit__="volt")
# Amp = type("Amp", (UnitType,), {}, __unit__="ampere")
# Coulomb = type("Coulomb", (UnitType,), {}, __unit__="coulomb")
# Farad = type("Farad", (UnitType,), {}, __unit__="farad")
# Ohm = type("Ohm", (UnitType,), {}, __unit__="ohm")
# Siemens = type("Siemens", (UnitType,), {}, __unit__="siemens")
# Henry = type("Henry", (UnitType,), {}, __unit__="henry")
# Second = type("Second", (UnitType,), {}, __unit__="second")
# Hz = type("Hz", (UnitType,), {}, __unit__="hertz")
# Rad_s = type("Rad_s", (UnitType,), {}, __unit__="radian / second")
# Micron = type("Micron", (UnitType,), {}, __unit__="micron")
# sq_Micron = type("sq_Micron", (UnitType,), {}, __unit__="micron**2")
# Watt = type("Watt", (UnitType,), {}, __unit__="watt")
# Joule = type("Joule", (UnitType,), {}, __unit__="joule")
# Efficiency = type("Efficiency", (UnitType,), {}, __unit__="hertz * siemens / ampere")
# Percent = type("Percent", (UnitType,), {}, __unit__="percent")
# GMID = type("GMID", (UnitType,), {}, __unit__="siemens / ampere")
# GAMMA = type("GAMMA", (UnitType,), {}, __unit__="joule / hertz")
