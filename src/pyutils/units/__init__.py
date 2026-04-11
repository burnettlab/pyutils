""" units: Extensions of pint package for adding unit values"""
import glob
import importlib
import os
import sys
import re
from itertools import chain
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml
from pint import UnitRegistry, set_application_registry

package_path = Path(__file__).parent


NUMBER_RE = re.compile(r"([-+]?(\d+(\.\d*)?|\.\d+))\s*\w*")


unit_yaml = Path(globals().get("UNITS_DEF", os.getenv("UNITS_DEF", package_path / "default.cfg")))
assert unit_yaml.exists(), "No pint config yaml exists!"
# Load pint configuration from yaml
with open(unit_yaml, 'r') as f:
    cfg: Dict = yaml.safe_load(f)

unit_defs_file = cfg["UnitRegistry"].pop("filename", None)
UREG = UnitRegistry(**cfg["UnitRegistry"])
UREG.default_preferred_units = list(map(lambda k: getattr(UREG, k), cfg.get("default_preferred_units", [])))     # type: ignore
if cfg.get("Matplotlib") is not None:
    UREG.setup_matplotlib(enable=cfg["Matplotlib"])
if unit_defs_file is not None:
    if unit_yaml == package_path / "default.cfg":
        unit_defs_file = unit_yaml.parent / unit_defs_file
    else:
        unit_defs_file = Path(unit_defs_file).resolve()
    assert unit_defs_file.exists(), f"Unit definitions file {unit_defs_file} does not exist!"
    UREG.load_definitions(unit_defs_file)
if (default_format := cfg.get("formatter", {}).get("default_format", None)) is not None:
    UREG.formatter.default_format = default_format

noncfg_keys = {("UnitRegistry",), ("Matplotlib",), ('default_preferred_units',), ('set_application_registry',), ('formatter', 'default_format')}
def setup_from_dict(d: Dict, keys: Tuple[Any]=()):
    for k, v in filter(lambda e: keys+(e[0],) not in noncfg_keys, d.items()):
        if isinstance(v, dict):
            setup_from_dict(v, keys + (k,))
        else:
            c = UREG
            for k in keys:
                c = getattr(c, k)
            
            setattr(c, k, v)
            assert getattr(c, k) == v, f"Failed to set {'.'.join(keys + (k,))} to {v}"

setup_from_dict(cfg)
if cfg.get("set_application_registry"):
    set_application_registry(UREG)

__all__ = ["UREG"]

ordered_imports = ["unit_types"]
for module in list(map(lambda m: Path(__file__).parent / m, ordered_imports)) + glob.glob(f"{package_path}/*.py") + list(map(lambda s: s.replace("/__init__.py", ""), glob.glob(f"{package_path}/*/__init__.py"))):
    mod_name = str(Path(module).relative_to(package_path).with_suffix('')).replace("/", ".")
    if not mod_name.startswith("__") and not mod_name.endswith("__") and f"{__package__}.{mod_name}" not in sys.modules:
        __all__.append(mod_name)
        mod = importlib.import_module(f".{mod_name}", package=__package__)
        vars().update(filter(lambda e: e[0] in getattr(mod, "__all__", []), vars(mod).items()))

__all__.extend(chain.from_iterable(map(lambda m: getattr(m, "__all__", []), filter(lambda m: getattr(m, "__package__", None) == __package__, vars().copy().values()))))		# type: ignore
