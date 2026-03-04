"""
I/O utilities for loading phenotype and measurement data with Streamlit caching.
"""
import re
from pathlib import Path

import pandas as pd
import streamlit as st

# Column schema for IRIS plate-reader output files
MEASUREMENT_FIELDS = (
    'row', 'column',
    'colony size', 'circularity', 'colony color intensity',
    'biofilm area size', 'biofilm color intensity', 'biofilm area ratio',
    'size normalized color intensity', 'mean sampled color intensity',
    'average pixel saturation', 'opacity', 'max 10% opacity',
)


@st.cache_data(show_spinner=False)
def read_spreadsheet(filepath, **kwargs):
    """Load an Excel workbook into a DataFrame (cached)."""
    return pd.read_excel(filepath, **kwargs)


@st.cache_data(show_spinner=False)
def read_tabular(filepath, **kwargs):
    """Load a delimited text file into a DataFrame (cached)."""
    path = Path(filepath)
    sep = kwargs.pop('sep', '\t' if path.suffix in ('.tsv', '.txt') else ',')
    return pd.read_csv(path, sep=sep, **kwargs)


# Aliases expected by colony_picker
load_csv = read_tabular
load_excel = read_spreadsheet


@st.cache_data(show_spinner=False)
def load_iris(filepath):
    """
    Parse an IRIS plate-reader measurement file.

    IRIS files are whitespace-delimited with comment lines starting with '#'.
    The first non-comment line is a header row that is replaced by the fixed
    schema defined in MEASUREMENT_FIELDS.

    Returns
    -------
    pd.DataFrame
        One row per colony with typed numeric columns.
    """
    rows = []
    header_consumed = False
    with Path(filepath).open() as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            if not header_consumed:
                header_consumed = True   # discard the file's own header
                continue
            rows.append(re.split(r'\s+', stripped))

    df = pd.DataFrame(rows, columns=list(MEASUREMENT_FIELDS))

    for field in MEASUREMENT_FIELDS:
        if field in ('row', 'column'):
            df[field] = pd.to_numeric(df[field], errors='coerce').astype('Int64')
        else:
            df[field] = pd.to_numeric(df[field], errors='coerce')

    return df


@st.cache_data(show_spinner=False)
def parse_iris_grid(filepath):
    """
    Extract grid boundary coordinates from an IRIS file header.

    IRIS writes lines like:
        #top left of the grid found at (0 , 7)
        #bottom right of the grid found at (4848 , 3200)

    Returns
    -------
    dict with keys 'top_left' and 'bottom_right' as (x, y) int tuples,
    or None if the header lines are absent.
    """
    tl = br = None
    _coord = re.compile(r'\((\d+)\s*,\s*(\d+)\)')
    with Path(filepath).open() as fh:
        for line in fh:
            if not line.startswith('#'):
                break
            if 'top left' in line:
                m = _coord.search(line)
                if m:
                    tl = (int(m.group(1)), int(m.group(2)))
            elif 'bottom right' in line:
                m = _coord.search(line)
                if m:
                    br = (int(m.group(1)), int(m.group(2)))
    if tl is not None and br is not None:
        return {'top_left': tl, 'bottom_right': br}
    return None
