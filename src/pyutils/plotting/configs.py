""" Matplotlib rcParam Configurations """
from abc import ABC
from dataclasses import InitVar, dataclass, field
from typing import Any, Dict, Optional, Callable
from functools import reduce, partial

import matplotlib as mpl
from auto_all import public


@public
@dataclass
class mplConfig(ABC):
    """ Helper class that adds inheritance to matplotlib rcParam configuration. Can be used as a context manager or decorator. """
    decorates: InitVar[Optional[Callable]] = None
    special_params: InitVar[Dict[str, Any]] = dict()
    _decorates: Optional[Callable] = None
    _default_params: Dict[str, Any] = field(default_factory=lambda: dict(mpl.rcParamsDefault))
    _special_params: Dict[str, Any] = field(default_factory=dict)
    _rc_context: Optional[Dict[str, Any]] = field(default=None, repr=False)

    @property
    def default_params(self) -> Dict[str, Any]:
        return self._default_params
    
    @property
    def config_params(self) -> Dict[str, Any]:
        params = reduce(lambda d, o: dict(map(lambda k: (k, d.get(k, o.get(k))), set((*d.keys(), *o.keys())))), map(lambda c: c().default_params, filter(lambda c: issubclass(c, mplConfig), type(self).mro())), {})
        params.update(self._special_params)
        return params
    
    def __post_init__(self, decorates: Optional[Callable], special_params: Dict[str, Any], *args, **kwargs):
        if isinstance(decorates, dict):
            decorates, special_params = special_params, decorates       # type: ignore
            
        self._decorates = decorates if callable(decorates) else None
        self._special_params = special_params
    
    def __call__(self, *args, **kwargs) -> Any:
        def wrapper(*args, func: Callable, **kwargs):
            with mpl.rc_context(self.config_params):
                return func(*args, **kwargs)
            
        if args and callable(args[0]):
            func = args[0]
            args = args[1:] if len(args) > 1 else ()
            return partial(wrapper, func=func)
        else:
            return wrapper(*args, func=self._decorates, **kwargs)
    
    def __enter__(self) -> None:
        assert self._rc_context is None, "Cannot enter an existing config"
        self._rc_context = mpl.rcParams.copy()
        cfg_params = self.config_params
        print(list(filter(lambda k: cfg_params[k] != mpl.rcParamsDefault[k], cfg_params.keys())))
        mpl.rcParams.update(cfg_params)

    def __exit__(self, *_):
        assert self._rc_context is not None, "Cannot exit non-existing config"
        mpl.rcParams.update(self._rc_context)
        self._rc_context = None
        

@public
class DefaultConfig(mplConfig):
    """ A 'good' default matplotlib configuration. """
    @property
    def default_params(self) -> Dict[str, Any]:
        return  {
            "lines.linewidth": 2,
            "savefig.dpi": 400, # Save with extra resolution
            "figure.dpi": 300, # Higher resolution by default
            "figure.figsize": [4.8, 3.2], # Slightly smaller default figure size
            "axes.grid": True, # Enable grid by default
            "axes.grid.axis": "both", # Enable grid on both axes
            "axes.grid.which": "both", # Enable grid on major and minor ticks
            "grid.linestyle": "--", # Dashed grid lines
            "grid.linewidth": 0.5, # Thinner grid lines
        }


@public
class LatexConfig(DefaultConfig):
    """ Configure matplotlib to render using LaTeX """
    @property
    def default_params(self) -> Dict[str, Any]:
        return {
            "text.usetex": True,
            "mathtext.fontset": "cm",
            "axes.unicode_minus": False,  # Ensure minus signs are rendered correctly
        }


@public
class IEEEConfig(LatexConfig):
    """ Format plots in an IEEE-compatible style """
    @property
    def default_params(self) -> Dict[str, Any]:
        return {
            "font.family": "serif",
            "font.serif": ["Computer Modern"],
        }


@public
class ACMConfig(LatexConfig):
    """ Format plots in an ACM-compatible style """
    @property
    def default_params(self) -> Dict[str, Any]:
        return {
            "font.family": "serif",
            "font.size": 12,
            "text.latex.preamble": r"\usepackage{libertine}"
        }
