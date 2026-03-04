"""
Streamlit interface for visualising colony morphology across imaging conditions.
"""
import glob
import os
import re
import sys

import cv2
import pandas as pd
import streamlit as st

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.data_loading import load_csv, load_excel, load_iris, parse_iris_grid, read_tabular
from app.utils.image_handling import load_plate_image, extract_colony, find_grid_params
from app.strain_overview import render_strain_overview, render_resistance, render_virulence, render_detailed_tables

ALL_METRICS = [
    'colony size', 'circularity', 'colony color intensity', 'biofilm area size',
    'biofilm color intensity', 'biofilm area ratio', 'size normalized color intensity',
    'mean sampled color intensity', 'average pixel saturation', 'opacity', 'max 10% opacity',
]
DEFAULT_METRICS = ['circularity', 'colony size', 'opacity', 'biofilm color intensity']

_LOOKUP_BY_ID  = "Search by strain ID"
_LOOKUP_BY_POS = "Enter grid position"

_CSS = """
<style>
  ul  { margin-top: 0; margin-bottom: 0; padding-left: 18px; }
  li  { margin-bottom: 2px; }
  table { width: 100%; border-collapse: collapse; background: transparent; }
  th, td { background: transparent; text-align: left;
            padding: 5px; vertical-align: top; border: none; }
</style>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def list_conditions(img_dir: str) -> list[str]:
    """Return sorted unique condition names found in *img_dir*."""
    names = set()
    for fpath in glob.glob(os.path.join(img_dir, "*.JPG.grid.jpg")):
        m = re.match(r'^(.*)-(\d+)-(\d+)_A\.JPG\.grid\.jpg$', os.path.basename(fpath))
        if m:
            names.add(m.group(1))
    return sorted(names)


def find_available_runs(img_dir: str, condition: str) -> list[tuple[int, int]]:
    """
    Return sorted (plate, batch) pairs available on disk for *condition*.
    Each pair corresponds to a single image file.
    """
    runs: set[tuple[int, int]] = set()
    esc = re.escape(condition)
    for fpath in glob.glob(os.path.join(img_dir, f"{condition}-*-*_A.JPG.grid.jpg")):
        m = re.match(fr'^{esc}-(\d+)-(\d+)_A\.JPG\.grid\.jpg$', os.path.basename(fpath))
        if m:
            runs.add((int(m.group(1)), int(m.group(2))))
    return sorted(runs)


def _well_positions_1536(source_row: int, source_col: int) -> dict[str, dict[str, int]]:
    """
    Map a 384-well coordinate to the four corresponding 1536-well positions.
    Each 384-well position expands to a 2×2 block of quadruplicates (A–D).
    """
    r = (source_row * 2) - 1
    c = (source_col * 2) - 1
    return {
        'A': {'row': r,     'col': c},
        'B': {'row': r,     'col': c + 1},
        'C': {'row': r + 1, 'col': c},
        'D': {'row': r + 1, 'col': c + 1},
    }


def _init_state(strain_map: pd.DataFrame, conditions: list[str]) -> None:
    """Populate session state keys that are not yet set."""
    defaults = {
        'lookup_mode':    _LOOKUP_BY_ID,
        'active_strain':  strain_map['ID'].iloc[0] if not strain_map.empty else None,
        'grid_row':       1,
        'grid_col':       1,
        'condition':      conditions[0] if conditions else None,
        'plate_batch':    None,
        'active_metrics': DEFAULT_METRICS,
        'results':        None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def run_colony_viewer(config: dict) -> None:
    st.title("Colony Viewer")
    st.markdown(_CSS, unsafe_allow_html=True)

    img_dir  = config['directories']['image_directory']
    iris_dir = config['directories']['iris_directory']

    try:
        strain_map = load_excel(config['files']['strain_file'])
    except Exception:
        strain_map = load_csv(config['files']['strain_file'])

    conditions = list_conditions(img_dir)
    _init_state(strain_map, conditions)

    def run_analysis() -> None:
        # Re-validate plate_batch for the current condition + strain (handles on_change calls)
        cur_runs = find_available_runs(img_dir, st.session_state.condition)
        sp = st.session_state.get('strain_plate_num')
        cur_filtered = [pb for pb in cur_runs if pb[0] == sp] if sp is not None else cur_runs
        if st.session_state.plate_batch not in cur_filtered:
            st.session_state.plate_batch = cur_filtered[0] if cur_filtered else None

        run = st.session_state.plate_batch
        if run is None:
            st.error("No plate/batch available.")
            st.session_state.results = None
            return

        plate_num, batch_num = run

        if st.session_state.lookup_mode == _LOOKUP_BY_ID:
            strain_row = strain_map[strain_map['ID'] == st.session_state.active_strain]
        else:
            strain_row = strain_map[
                (strain_map['Row'] == st.session_state.grid_row) &
                (strain_map['Column'] == st.session_state.grid_col) &
                (strain_map['Plate'] == plate_num)
            ]

        if strain_row.empty:
            st.error("Strain not found in the coordinate map.")
            st.session_state.results = None
            return

        fname = f"{st.session_state.condition}-{plate_num}-{batch_num}_A.JPG.grid.jpg"
        img_path = os.path.join(img_dir, fname)
        if not os.path.exists(img_path):
            st.warning(f"Image not found: {fname}")
            st.session_state.results = None
            return

        plate_img = load_plate_image(img_path)
        if plate_img is None:
            st.error(f"Could not load image: {img_path}")
            st.session_state.results = None
            return

        iris_stem = os.path.basename(img_path).replace('.JPG.grid.jpg', '.JPG')
        iris_path = os.path.join(iris_dir, f"{iris_stem}.iris")
        measurements = None
        iris_grid_params = None
        if os.path.exists(iris_path):
            try:
                measurements = load_iris(iris_path)
                iris_grid_params = parse_iris_grid(iris_path)
            except Exception as exc:
                st.warning(f"IRIS parse error: {exc}")

        src_r = int(strain_row.iloc[0]['Row'])
        src_c = int(strain_row.iloc[0]['Column'])
        well_map = _well_positions_1536(src_r, src_c)

        img_h, img_w = plate_img.shape[:2]
        if iris_grid_params is not None:
            tl = iris_grid_params['top_left']
            br = iris_grid_params['bottom_right']
            scale_x = img_w / br[0] if br[0] else 1.0
            scale_y = img_h / br[1] if br[1] else 1.0
            grid_origin = (int(round(tl[0] * scale_x)), int(round(tl[1] * scale_y)))
            cell_w = (br[0] - tl[0]) * scale_x / 48
            cell_h = (br[1] - tl[1]) * scale_y / 32
            cell_size = (cell_w, cell_h)
        else:
            grid_origin, cell_size = find_grid_params(plate_img)

        colony_crops = {
            label: extract_colony(
                plate_img,
                pos['row'] - 1, pos['col'] - 1,
                grid_origin=grid_origin, cell_size=cell_size,
            )
            for label, pos in well_map.items()
        }

        st.session_state.results = {
            'img_path':     img_path,
            'plate_img':    plate_img,
            'well_map':     well_map,
            'measurements': measurements,
            'colony_crops': colony_crops,
            'grid_origin':  grid_origin,
            'cell_size':    cell_size,
        }

    # ---- Sidebar Controls ----
    st.sidebar.divider()

    st.sidebar.radio("Lookup method", (_LOOKUP_BY_ID, _LOOKUP_BY_POS), key='lookup_mode')

    strain_plate = None
    if st.session_state.lookup_mode == _LOOKUP_BY_ID:
        st.sidebar.selectbox("Strain", strain_map['ID'], key='active_strain')
        hit = strain_map.loc[
            strain_map['ID'] == st.session_state.active_strain, ['Row', 'Column', 'Plate']
        ]
        if not hit.empty:
            st.session_state.grid_row = int(hit.iloc[0]['Row'])
            st.session_state.grid_col = int(hit.iloc[0]['Column'])
            strain_plate = int(hit.iloc[0]['Plate'])
            st.session_state.strain_plate_num = strain_plate
        st.sidebar.markdown(
            f"<p style='font-size:13px;margin-top:2px;opacity:0.7;'>"
            f"Position: ({st.session_state.grid_row}, {st.session_state.grid_col})"
            f" &nbsp;·&nbsp; Plate {strain_plate}</p>",
            unsafe_allow_html=True,
        )
    else:
        st.session_state.strain_plate_num = None
        st.sidebar.number_input("Row (1–32)",    min_value=1, max_value=32, step=1, key='grid_row')
        st.sidebar.number_input("Column (1–48)", min_value=1, max_value=48, step=1, key='grid_col')
        cur_plate = st.session_state.plate_batch[0] if st.session_state.plate_batch else None
        match = strain_map[
            (strain_map['Row'] == st.session_state.grid_row) &
            (strain_map['Column'] == st.session_state.grid_col) &
            (strain_map['Plate'] == cur_plate)
        ] if cur_plate else pd.DataFrame()
        label = match.iloc[0]['ID'] if not match.empty else "unknown"
        st.sidebar.markdown(
            f"<p style='font-size:13px;margin-top:2px;opacity:0.7;'>Strain: <b>{label}</b></p>",
            unsafe_allow_html=True,
        )

    st.sidebar.selectbox("Condition", conditions, key='condition', on_change=run_analysis,
                         format_func=lambda c: c.rstrip('-'))
    available_runs = find_available_runs(img_dir, st.session_state.condition)
    # When looking up by strain ID, restrict Plate/Batch to the strain's plate
    filtered_runs = (
        [pb for pb in available_runs if pb[0] == strain_plate]
        if strain_plate is not None else available_runs
    )
    if st.session_state.plate_batch not in filtered_runs:
        st.session_state.plate_batch = filtered_runs[0] if filtered_runs else None
    if filtered_runs:
        st.sidebar.selectbox(
            "Plate / Batch",
            options=filtered_runs,
            format_func=lambda pb: f"Plate {pb[0]}, Batch {pb[1]}",
            key='plate_batch',
            on_change=run_analysis,
        )
    else:
        st.sidebar.warning("No images found for this condition.")

    st.sidebar.multiselect("Metrics", options=ALL_METRICS, key='active_metrics')
    st.sidebar.button("Analyse", on_click=run_analysis, type="primary")

    # ---- Results ----
    if not st.session_state.results:
        return

    res            = st.session_state.results
    plate_img      = res['plate_img']
    well_map       = res['well_map']
    measurements   = res['measurements']
    colony_crops   = res['colony_crops']
    grid_origin    = res['grid_origin']
    cell_size      = res['cell_size']
    active_metrics = st.session_state.active_metrics

    img_col, _ = st.columns(2)
    with img_col:
        st.info(f"Plate image: **{os.path.basename(res['img_path'])}**")
        with st.expander("Grid overlay", expanded=False):
            if plate_img is not None:
                overlay = cv2.cvtColor(plate_img, cv2.COLOR_BGR2RGB).copy()
                ox, oy = grid_origin
                cw, ch = cell_size
                px1, py1 = ox, oy
                px2 = int(round(ox + 48 * cw))
                py2 = int(round(oy + 32 * ch))
                for pos in well_map.values():
                    r0, c0 = pos['row'] - 1, pos['col'] - 1
                    x1 = int(round(ox + c0 * cw))
                    y1 = int(round(oy + r0 * ch))
                    cv2.rectangle(overlay, (x1, y1),
                                  (int(round(x1 + cw)), int(round(y1 + ch))),
                                  (255, 0, 0), 2)
                overlay_cropped = overlay[py1:py2, px1:px2]
                st.image(overlay_cropped, caption="Replicate locations",
                         use_container_width=True)

    st.write("---")

    if st.session_state.get('lookup_mode') == _LOOKUP_BY_ID:
        strain_id = st.session_state.active_strain
    else:
        plate_num_res = st.session_state.plate_batch[0] if st.session_state.plate_batch else None
        pos_match = strain_map[
            (strain_map['Row'] == st.session_state.grid_row) &
            (strain_map['Column'] == st.session_state.grid_col) &
            (strain_map['Plate'] == plate_num_res)
        ] if strain_map is not None and plate_num_res is not None else pd.DataFrame()
        strain_id = pos_match.iloc[0]['ID'] if not pos_match.empty else None

    left_col, right_col = st.columns(2)

    kleb_row = None
    if strain_id is not None:
        kleb = read_tabular(config['files']['kleborate_file'], sep='\t')
        hit = kleb[kleb['strain'] == strain_id]
        if not hit.empty:
            kleb_row = hit.iloc[0]
        else:
            with left_col:
                st.info(f"No genomic data found for **{strain_id}** in kleborate file.")

    if kleb_row is not None:
        with left_col:
            render_strain_overview(kleb_row)

    with right_col:
        st.header("Colony images and measurements")
        cols = st.columns(4)
        for i, (label, pos) in enumerate(well_map.items()):
            with cols[i]:
                crop = colony_crops.get(label)
                if crop is not None:
                    st.image(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB),
                             caption=f"Rep {label}  R{pos['row']} C{pos['col']}",
                             use_container_width=True)
                else:
                    st.warning(f"No image for replicate {label}")

        if active_metrics:
            if measurements is not None:
                def _fmt(v) -> str:
                    if v is None or not pd.notna(v):
                        return "—"
                    s = f"{float(v):.4f}".rstrip('0').rstrip('.')
                    return s

                reps = list(well_map.items())
                th_style = "padding:6px 12px;text-align:center;font-weight:600;border-bottom:2px solid #000;white-space:nowrap;"
                td_style = "padding:5px 12px;text-align:center;border-bottom:1px solid rgba(128,128,128,0.15);"
                td_label = "padding:5px 12px;text-align:left;font-weight:500;border-bottom:1px solid rgba(128,128,128,0.15);white-space:nowrap;"

                header = "".join(f"<th style='{th_style}'>Rep {lbl}</th>" for lbl, _ in reps)
                rows_html = ""
                for metric in active_metrics:
                    cells = ""
                    for _, pos in reps:
                        row_hit = measurements[
                            (measurements['row'] == pos['row']) &
                            (measurements['column'] == pos['col'])
                        ]
                        v = row_hit[metric].iloc[0] if (not row_hit.empty and metric in row_hit.columns) else None
                        cells += f"<td style='{td_style}'>{_fmt(v)}</td>"
                    rows_html += f"<tr><td style='{td_label}'>{metric.title()}</td>{cells}</tr>"

                html_table = (
                    f"<table style='width:100%;border-collapse:collapse;font-size:0.85rem;'>"
                    f"<thead><tr><th style='{th_style}text-align:left;'>Metric</th>{header}</tr></thead>"
                    f"<tbody>{rows_html}</tbody></table>"
                )
                st.html(html_table)
            else:
                st.info("No IRIS measurements available for this plate.")
               

        if st.button("Save colony images"):
            out_dir = "saved_colonies"
            os.makedirs(out_dir, exist_ok=True)
            tag = (st.session_state.active_strain
                   if st.session_state.lookup_mode == _LOOKUP_BY_ID
                   else f"R{st.session_state.grid_row}C{st.session_state.grid_col}")
            cond_tag = st.session_state.condition.replace("/", "_").replace("\\", "_")
            saved = 0
            for rep, img_arr in colony_crops.items():
                if img_arr is not None:
                    out_path = os.path.join(out_dir, f"{tag}_{cond_tag}_{rep}.png")
                    if cv2.imwrite(out_path, img_arr):
                        saved += 1
            if saved:
                st.success(f"Saved {saved} images to '{out_dir}/'")
            else:
                st.warning("No images to save.")

    if kleb_row is not None:
        st.write("")
        st.divider()
        render_resistance(kleb_row)

        st.write("")
        st.divider()
        render_virulence(kleb_row)

        st.write("")
        st.divider()
        render_detailed_tables(kleb_row)


colonypicker = run_colony_viewer
