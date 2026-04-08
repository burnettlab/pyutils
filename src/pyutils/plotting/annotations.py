""" Functions to manage text for plots """
from dataclasses import dataclass
from functools import wraps
from typing import Callable, Dict, List, Optional, Self

import matplotlib.pyplot as plt
from adjustText import adjust_text
from auto_all import public
from matplotlib.axes import Axes
from matplotlib.axis import Axis
from matplotlib.text import Text
from pyutils.units.utility import unit_str_addon


@public
def escape_latex(text: str, special_chars: Dict[str, str]={}):
    """
    Escapes LaTeX special characters in a string.
    """
    latex_special_chars = {
        # '\\': r'\textbackslash{}',
        '&': r'\&',
        '%': r'\%',
        # '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\textasciicircum{}',
        '>': r'\textgreater{}',
        '<': r'\textless{}',
    }
    latex_special_chars.update(special_chars)
    
    for char, replacement in latex_special_chars.items():
        text = text.replace(char, replacement)
    return text


@public
def axis_units(ax: Axes, *, x_format_wrapper: Optional[Callable[Callable, Callable]]=None, y_format_wrapper: Optional[Callable[Callable, Callable]]=None, format_wrapper: Callable[Callable, Callable]=lambda x: x):
    """ Adds automatic axis unit appending to axes x and y labels. Can optionally specify format wrapping functions for x axis, y axis, or both (e.g. for changing pint formatter)."""
    def append_units_wrapper(func: Optional[Callable]=None, *, ax: Optional[Axis]=None, format_wrapper: Callable[Callable, Callable]=lambda x: x):
        if func is None:
            return partial(append_units_wrapper, ax=ax, format_wrapper=format_wrapper)
        assert ax is not None, "Must provide the axis to be able to get units from"
        
        @wraps(func)
        def wrapper(s: str, *args, **kwargs):
            unit_str = f"{s}{format_wrapper(unit_str_addon)(ax.get_units())}"
            return func(unit_str, *args, **kwargs)
        
        return wrapper

    ax.set_xlabel = append_units_wrapper(ax.set_xlabel, ax=ax.xaxis, format_wrapper=x_format_wrapper or format_wrapper)     # type: ignore
    ax.set_xlabel(ax.get_ylabel())
    ax.set_ylabel = append_units_wrapper(ax.set_ylabel, ax=ax.yaxis, format_wrapper=y_format_wrapper or format_wrapper)     # type: ignore
    ax.set_ylabel(ax.get_ylabel())


@public
@dataclass
class TextPositioner:
    """
    Context manager to automatically position text on a plot. Call `annotate` for each matplotlib object to be positioned.
    
    Example usage:
    ```python
    with TextPositioner() as p:
        p.annotate(plt.text(x=0, y=0, s="This is text to be positioned"))
    ```

    Default arguments to adjust_text:
    ```python
    dict(
        ax=plt.gca(),
    )
    ```
    """
    texts: List[Text]
    kwargs: Dict

    def __init__(self, **kwargs) -> None:
        self.texts = []
        self.kwargs = dict(
            ax=plt.gca(),
        )
        self.kwargs.update(kwargs)

    def __enter__(self, **kwargs) -> Self:
        self.kwargs.update(kwargs)
        return self
    
    def annotate(self, obj) -> None:
        """
        Add an annotation to be automatically positioned on the plot.
        """
        self.texts.append(obj)

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type:
            print(exc_val)
            print(exc_tb)
            return False
        
        adjust_text(self.texts, **self.kwargs)
        return True
