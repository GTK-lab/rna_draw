import os
import time
import argparse
from pprint import pprint
import pandas as pd
from scipy.optimize import curve_fit
from pathlib import Path

from rna_draw import render_rna, parameters, colorer
from rna_draw.colorer import *

import matplotlib.cm
import matplotlib.pyplot as plt

import re
import numpy as np


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-ss", help="secondary structure in dot bracket notation", required=True
    )
    parser.add_argument("-seq", help="rna sequence", required=False)
    parser.add_argument(
        "-out", help="output png file", required=False, default="secstruct"
    )
    parser.add_argument(
        "-color_str",
        help="description of coloring, see docs for options",
        required=False,
    )
    parser.add_argument(
        "-render_type",
        help="scheme to color by: res_type,paired,motif,none",
        required=False,
    )
    parser.add_argument(
        "-color_palette",
        help="seaborn color palette. Optional",
        required=False
    )
    parser.add_argument(
        "-default_color", help="the color used when no other color is supplied"
    )
    parser.add_argument(
        "-data_str", help="data values by res seperated by ;", required=False
    )
    parser.add_argument("-data_file", help="path to data to color by", required=False)
    parser.add_argument(
        "-data_palette", help="matplotlib color palette", required=False
    )
    parser.add_argument(
        "-data_vmin",
        help="min data value everything lower than this will be set to this value",
        required=False,
    )
    parser.add_argument(
        "-data_vmax",
        help="max data value everything greater than this will be set to this value",
        required=False,
    )
    parser.add_argument(
        "-data_ignore_restype",
        help="data values will be ignored for these restypes, e.g. G and U for DMS",
        required=False,
    )
    return parser


def parse_args():
    parser = get_parser()
    args = parser.parse_args()
    return args


class RNADrawer(object):
    def __init__(self):
        self.__colorer = colorer.Colorer()
        self.__draw_params = parameters.DrawParameters()

    def draw(
        self,
        ss,
        seq=None,
        filename="secstruct",
        color_str=None,
        render_type=None,
        default_color=None,
        color_palette=None,
        data=None,
        draw_params=None,
    ):
        self.__setup(draw_params)
        if seq is None:
            seq = " " * len(ss)

        if color_palette is not None:
            self.__colorer.color_palette(color_palette)

        final_color_rbgs = self.__colorer.get_rgb_colors(
            seq, ss, color_str, data, render_type, default_color
        )

        return self.__render(seq, ss, final_color_rbgs, filename, self.__draw_params)

    def __setup(self, draw_params):
        if draw_params is not None:
            self.__draw_params = draw_params

    def __render(self, seq, ss, colors, filename, params):
        r = render_rna.RNARenderer()

        pairmap = render_rna.get_pairmap_from_secstruct(ss)
        pairs = []
        for i in range(len(pairmap)):
            if pairmap[i] > i:
                pairs.append(
                    {"from": i, "to": pairmap[i], "p": 1.0, "color": DEFAULT_COLORS["e"]}
                )

        r.setup_tree(ss, params.NODE_R, params.PRIMARY_SPACE, params.PAIR_SPACE)
        size = r.get_size()

        cell_size = max(size) + params.CELL_PADDING * 2

        r.ax.axis("off")
        r.ax.set_xlim([min(r.xarray_) + 40 - 15, max(r.xarray_) + 40 + 15])
        r.ax.set_ylim([min(r.yarray_) + 40 - 15, max(r.yarray_) + 40 + 15])

        # Print "area = (max(r.xarray_) - min(r.xarray_)) * (max(r.yarray_) - min(r.yarray_))" to get rna_area.
        # Adjust the r.fig.set_size_inches until the text size looks good and name it rna_figsize_variable for some
        # example RNA structures.
        # Plot rna_area vs rna_figsize_variable.
        # Fit the curve using scipy to get a good figure size for any size of RNA structure.
        data = {
            "rna_identity": ["hairpin", "t-RNA", "CO-VID19 5' UTR", "50S Ribosome"],
            "rna_area": [3781, 126207, 1150472, 4286761],
            "rna_figsize_variable": [25, 30, 35, 40],
        }
        df = pd.DataFrame(data)

        x = df["rna_area"]
        y = df["rna_figsize_variable"]

        def test(x, a, b, c):
            return a * (x - b) ** c

        param, param_cov = curve_fit(test, x, y)

        if min(r.xarray_) != max(r.yarray_):
            area = (max(r.xarray_) - min(r.xarray_)) * (max(r.yarray_) - min(r.yarray_))
            r.fig.set_size_inches(
                (max(r.xarray_) - min(r.xarray_))
                / ((param[0]) * (area - param[1]) ** (param[2])),
                (max(r.yarray_) - min(r.yarray_))
                / ((param[0]) * (area - param[1]) ** (param[2])),
            )
        r.draw(
            params.CELL_PADDING,
            params.CELL_PADDING,
            colors,
            pairs,
            seq,
            params.RENDER_IN_LETTERS,
        )
        r.fig.savefig(filename + ".png")
        return r.fig


def __get_data_from_args(args):
    if args.data_str is not None or args.data_file is not None:
        return Data(
            args.data_str,
            args.data_file,
            args.data_palette,
            args.data_vmin,
            args.data_vmax,
            args.data_ignore_restype,
        )
    else:
        return None


def __get_render_type(render_type_name):
    if render_type_name is None:
        return None
    render_type_name = render_type_name.lower()
    if render_type_name == "res_type":
        return colorer.RenderType.RES_TYPE
    elif render_type_name == "paired":
        return colorer.RenderType.PAIRED
    elif render_type_name == "strand":
        return colorer.RenderType.STRAND
    elif render_type_name == "none":
        return None
    else:
        raise ValueError("unknown render type: " + render_type_name)


def __rna_draw_from_args(args):
    data = __get_data_from_args(args)
    render_type = __get_render_type(args.render_type)
    default_color = None
    if args.default_color is not None:
        default_color = colorer.parse_color_code(args.default_color)

    rd = RNADrawer()
#    pprint(args.color_palette)
    return rd.draw(
        args.ss, seq=args.seq, filename=args.out,
        color_str=args.color_str, render_type=render_type,
        color_palette=args.color_palette,
        default_color=default_color, data=data
    )


def rna_draw(**kwargs):
    parser = get_parser()
    args = []
    for k, v in kwargs.items():
        args.append("-" + k)
        if isinstance(v, Path):
            v = str(v)
        args.append(v)
    args = parser.parse_args(args)
    return __rna_draw_from_args(args)


def main():
    args = parse_args()
    return __rna_draw_from_args(args)


if __name__ == "__main__":
    main()
