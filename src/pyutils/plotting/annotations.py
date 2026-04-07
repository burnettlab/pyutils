""" Functions to manage text for plots """
from dataclasses import dataclass
from functools import wraps
from typing import Dict, List, Self

import matplotlib.pyplot as plt
from adjustText import adjust_text
from matplotlib.axes import Axes
from matplotlib.text import Text

from pyutils.units.utility import unit_str_addon
from auto_all import public


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
def axis_units(ax: Axes):
    """ Automatically append units to axis label string (when given) """
    def append_units_wrapper(func, ax):
        @wraps(func)
        def wrapper(s: str, *args, **kwargs):
            return func(f"{s}{unit_str_addon(ax.get_units())}", *args, **kwargs)
        return wrapper

    ax.set_xlabel = append_units_wrapper(ax.set_xlabel, ax.xaxis)       # type: ignore
    ax.set_xlabel(ax.get_ylabel())
    ax.set_ylabel = append_units_wrapper(ax.set_ylabel, ax.yaxis)       # type: ignore
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
