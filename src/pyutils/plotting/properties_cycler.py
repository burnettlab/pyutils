""" Cycle through properties by keys """
import itertools
import operator
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from functools import reduce
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import matplotlib as mpl
import matplotlib.lines as mlines
import matplotlib.patches as mpatches
from auto_all import public
from cycler import Cycler, cycler
from matplotlib.artist import Artist

from .colors import GOOD_COLORS


@public
@dataclass
class PropertiesCycler:
    """
    Cycles through properties for plotting.
    Indexing with a list of keys will return properties for those keys.
    Each key depth uses a separate cycler.
    """
    properties_list: List[Dict[str, Any]]
    depth_cyclers: Dict[int, Cycler | Iterable] = field(init=False, repr=False)
    key_properties: Dict[str, Dict] = field(default_factory=dict)

    def __post_init__(self) -> None:
        depth_cycle = itertools.cycle(self.properties_list)

        def create_cycler(cycler_dict: Dict) -> Cycler:
            # Create an ordered dict from the cycler_dict, sorted by the length of the values
            cycler_dict = OrderedDict(sorted(cycler_dict.items(), key=lambda item: len(item[1]), reverse=True))

            # Compose all of the cyclers of the same length together using addition
            cyclers = []
            for key, value in cycler_dict.items():
                cy = cycler(**{key: value})
                if not cyclers or len(value) != len(cyclers[-1]):
                    cyclers.append(cy)
                else:
                    cyclers[-1] += cy

            return reduce(operator.mul, cyclers)

        self.depth_cyclers = defaultdict(lambda: create_cycler(next(depth_cycle)))

    def __getitem__(self, keys: Union[str, Iterable[str]]) -> Dict[str, Any]:
        """
        Get properties for the given keys.
        """
        if not isinstance(keys, Iterable):
            keys = iter(keys)
        elif isinstance(keys, str):
            keys = [keys]
        
        props = {}
        cmap = None
        # key = ""
        for depth, key in enumerate(keys):
            # key += new_key
            if (depth, key) not in self.key_properties:
                cy = self.depth_cyclers[depth]
                if isinstance(cy, Cycler):
                    if cmap:
                        # If a colormap was previously set, add it to the cycler
                        if cmap in GOOD_COLORS:
                            colors = GOOD_COLORS[cmap](len(cy))
                        else:
                            colors = mpl.colormaps[key].resampled(len(cy)).colors   # type: ignore
                        
                        cy = cycler(color=colors) + cy

                    # Initialize the cycler
                    cy = cy()
                    self.depth_cyclers[depth] = cy
                
                self.key_properties[depth, key] = next(cy)

            props.update(self.key_properties[depth, key])
            cmap = props.pop("cmap", None)
            # key += ","

        assert cmap is None, "Colormap should not be set at the end of the properties cycler."
        return props

    def get_table_legend(self, default_style: Optional[Dict]=None) -> Tuple[str, List[Artist], int]:
        """Get a list of legend artists for the properties cycler.
        
        Formatted as a table with the properties for each key depth.
        """
        line_props = [
            "linewidth", "lw",
            "linestyle", "ls",
            "marker", "markerfacecolor", "markeredgecolor", "markersize", "markeredgewidth",
            "markevery",
        ]
        patch_props = [
            "linewidth", "lw",
            "linestyle", "ls",
            "edgecolor", "ec", "facecolor", "fc",
            "hatch", "hatch_linewidth",
        ]

        if default_style is None:
            default_style = dict(
                color="black",
                linestyle="solid",
                marker="none",
            )

        legend_artists = []
        column_artists = {}

        for (depth, key), depth_props in self.key_properties.items():
            depth_key = key.split(",")[-1]
            try:
                title, value = depth_key.split("=")
            except ValueError:
                continue  # Skip if depth_key does not contain an '='

            if depth not in column_artists:
                column_artists[depth] = [title]
            
            # depth_props.pop("color", None)  # Remove color if present
            depth_props.pop("cmap", None)  # Remove colormap if present
            
            legend_props = {**default_style, **depth_props}
            patch_keys = set(patch_props) & set(legend_props.keys())
            line_keys = set(line_props) & set(legend_props.keys())
            if not patch_keys and not line_keys:
                raise ValueError(f"Properties for {depth_key} do not match any known legend style: {legend_props}")
            
            # Choose the appropriate artist type based on the properties
            if len(patch_keys) >= len(line_keys):
                column_artists[depth].append(
                    mpatches.Patch(**dict(filter(lambda item: item[0] in patch_props or item[0] not in line_props, legend_props.items())), label=value)
                )
            else:
                column_artists[depth].append(
                    mlines.Line2D([], [], **dict(filter(lambda item: item[0] in line_props or item[0] not in patch_props, legend_props.items())), label=value)
                )
                
        legend_title = r"   $\mid$   ".join(map(lambda e: e[1][0], sorted(column_artists.items(), key=lambda e: e[0])))
                
        # Create the legend artists in a table format
        max_len = max(map(len, column_artists.values()), default=0)
        for col_artists in map(lambda e: e[1], sorted(column_artists.items(), key=lambda e: e[0])):
            legend_artists.extend(col_artists[1:] + [mpatches.Patch(color='none', label='')] * (max_len - len(col_artists)))
            
        return legend_title, legend_artists, len(column_artists)
