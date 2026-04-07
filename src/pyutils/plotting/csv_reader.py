""" Read data from CSV to be plotted, or plots a dict read from a CSV file. """
import csv
import re
from collections import defaultdict
from inspect import signature
from itertools import cycle
from math import ceil, floor, sqrt
from os import PathLike
from typing import Callable, Dict, Generator, List, Tuple, Union

import matplotlib.pyplot as plt
from auto_all import public
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from .properties_cycler import PropertiesCycler


@public
def csv_to_plot(p: PathLike, col_strs: List[str], dtype=float) -> dict:
    """
    Reads a CSV, following Cadence export format, into a dict ready to be plotted

    Cadence labels each column with a string representing the data for the column, e.g "Name (parameter 1,parameter 2,...) Axis".
    This function reads that CSV, uses parameters to index into nested dictionaries, with the deepest level being the axis, indexing the list of values for that axis.
    
    Arguments:
        p: Path to CSV file
        dtype: Data type of data being plotted. Will attempt to use this to parse the CSV.
    Returns:
        dict: Dictionary containing data to plot    
    """
    
    def add_data(data_dict, keys, val):
        if len(keys) == 1:
            data_dict[keys[0]].append(val)
        else:
            if keys[0] not in data_dict:
                data_dict[keys[0]] = defaultdict(list)
            add_data(data_dict[keys[0]], keys[1:], val)

    # Regex to match the column strings
    col_regex = re.compile(r"(?P<name>[^(]*)\s+\((?P<parameters>.*)\)\s+(?P<axis>\S*)")
    # parameter_regex = re.compile(r"(?P<p_name>[^()=]*)=(?P<p_val>[^()=,]*),?")

    out_dict = defaultdict(list)
    col_keys = {}
    store_data = False

    with open(p, "r") as f:
        for ix, row in enumerate(csv.reader(f)):
            for col_ix, col in enumerate(row):
                if ix == 0:
                    # First row is the header, parse it
                    if col_match := re.search(col_regex, col):
                        col_name = col_match.group("name")
                        parameters = col_match.group("parameters").split(",")
                        axis = col_match.group("axis")

                        # Create the key for this column
                        col_key = [col_name] + parameters + [axis]
                        col_keys[col_ix] = col_key
                else:
                    curr_keys = col_keys[col_ix]
                    try:
                        col = dtype(col)
                    except ValueError:
                        pass

                    add_data(out_dict, curr_keys, col)

    return out_dict


@public
def plot_dict(
    data_dict: Dict,
    same_figure: bool = True,
    same_axes: bool = False,
    plot_functions: Union[Dict[str, Callable], Callable] = plt.plot,
    cycler_lists: List[Dict] = [],
    subplot_kw: Dict = {},
    **kwargs
) -> Generator[Tuple[Figure, Dict[str, Axes], Dict[str, PropertiesCycler]], None, None]:
    """ Plots a dictionary, formatted in the same way as the output of csv_reader. 
    
    Args:
        data_dict (dict): Dictionary with keys as column names and values as lists of data.
        same_axes (bool): If True, all data will be plotted on the same axes. If False, each first-level key will have its own axes.
    Returns:
        Tuple[Figure, dict[Axes], dict[PropertiesCycler]]: The matplotlib Figure and mapping of Axes objects, and properties used to create them.
    """

    num_plots = 1 if same_axes or not same_figure else len(data_dict)

    if "nrows" in subplot_kw and "ncols" in subplot_kw:
        nrows = subplot_kw.pop("nrows")
        ncols = subplot_kw.pop("ncols")
    elif "nrows" in subplot_kw:
        nrows = subplot_kw.pop("nrows")
        ncols = ceil(num_plots / nrows)
    elif "ncols" in subplot_kw:
        ncols = subplot_kw.pop("ncols")
        nrows = ceil(num_plots / ncols)
    else:
        # Find the largest factor of num_plots <= the square root of num_plots
        largest_factor = floor(sqrt(num_plots))
        while num_plots % largest_factor != 0:
            largest_factor -= 1

        ncols = largest_factor
        nrows = num_plots // ncols


    def plot_subdict(data: Dict, prev_keys: List=[], **kwargs):
        """ Recursively plots sub-dictionaries. """
        if not isinstance(data, dict):
            raise TypeError("Data must be a dictionary.")
        
        if axes_data := dict(filter(lambda e: not isinstance(e[1], dict), data.items())):
            plot_kwargs = kwargs.copy()
            plot_key = prev_keys[0] if prev_keys else None
            full_key = ",".join(prev_keys) if prev_keys else "Data"

            plt.sca(axes_mapping[plot_key])
            plot_kwargs.update(properties[plot_key][prev_keys])
            
            if axes_data := {k: v for k, v in axes_data.items() if v is not None}:
                if isinstance(plot_functions, dict):
                    try:
                        plot_function = plot_functions[plot_key]
                    except KeyError:
                        plot_function = plt.plot
                else:
                    plot_function = plot_functions

                pf_sig = signature(plot_function)

                ax_args = [v for k, v in sorted(axes_data.items(), key=lambda e: e[0]) if k not in pf_sig.parameters]
                ax_kwargs = {k: v for k, v in axes_data.items() if k in pf_sig.parameters}

                plot_function(*ax_args, **ax_kwargs, label=full_key, **plot_kwargs)

        for key, value in filter(lambda e: isinstance(e[1], dict), data.items()):
            plot_subdict(value, prev_keys + [key], **kwargs)
    
    if same_figure:
        # Prepare the figure and axes
        fig, axes = plt.subplots(nrows, ncols, squeeze=False, **subplot_kw)
        axes_iter = cycle(axes.flatten())
        axes_mapping = defaultdict(lambda: next(axes_iter))
        properties = defaultdict(lambda: PropertiesCycler(cycler_lists))

        plot_subdict(data_dict, **kwargs)

        for title, ax in axes_mapping.items():
            if title:
                ax.set_title(title)

        yield (fig, axes_mapping, properties)
    else:
        for key, data in data_dict.items():
            # Prepare the figure and axes
            fig, axes = plt.subplots(nrows, ncols, squeeze=False, **subplot_kw)
            axes_iter = cycle(axes.flatten())
            axes_mapping = defaultdict(lambda: next(axes_iter))
            properties = defaultdict(lambda: PropertiesCycler(cycler_lists))

            plot_subdict(data, [key], **kwargs)

            for title, ax in axes_mapping.items():
                if title:
                    ax.set_title(title)

            yield (fig, axes_mapping, properties)
