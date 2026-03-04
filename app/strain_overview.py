"""
Strain Overview page — genomic profile from Kleborate output.

Sections
--------
1. Strain Overview       — species, ST, locus types, genome assembly stats, score metrics
2. Key Resistance        — acquired genes (by antibiotic class) + resistance mutations
3. Virulence Profile     — siderophore / hypervirulence loci with allele designations
4. Detailed tables       — full resistance gene list  |  virulence gene alleles
"""

import os
import sys

import pandas as pd
import streamlit as st

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.data_loading import read_tabular, load_csv, load_excel

# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

# Antibiotic class → Kleborate column name
RESISTANCE_CLASSES = {
    'Aminoglycosides':    'AGly_acquired',
    'Colistin (acq.)':   'Col_acquired',
    'Fosfomycin':        'Fcyn_acquired',
    'Fluoroquinolones':  'Flq_acquired',
    'Glycopeptides':     'Gly_acquired',
    'Macrolides / MLS':  'MLS_acquired',
    'Phenicols':         'Phe_acquired',
    'Rifamycins':        'Rif_acquired',
    'Sulfonamides':      'Sul_acquired',
    'Tetracyclines':     'Tet_acquired',
    'Tigecycline':       'Tgc_acquired',
    'Trimethoprim':      'Tmt_acquired',
    'β-lactamases':      'Bla_acquired',
    'β-lac. inhR':       'Bla_inhR_acquired',
    'ESBL':              'Bla_ESBL_acquired',
    'ESBL + inhR':       'Bla_ESBL_inhR_acquired',
    'Carbapenemases':    'Bla_Carb_acquired',
    'Chr. β-lactamase':  'Bla_chr',
}

RESISTANCE_MUTATIONS = {
    'SHV':               'SHV_mutations',
    'Porin (Omp)':       'Omp_mutations',
    'Colistin (mut.)':   'Col_mutations',
    'Fluoroquinolone':   'Flq_mutations',
}

# High-concern resistance classes (deeper red badge)
_HIGH_CONCERN = {'Carbapenemases', 'ESBL', 'ESBL + inhR'}

VIRULENCE_LOCI = {
    'Yersiniabactin': ('Yersiniabactin', 'YbST'),
    'Colibactin':     ('Colibactin',     'CbST'),
    'Aerobactin':     ('Aerobactin',     'AbST'),
    'Salmochelin':    ('Salmochelin',    'SmST'),
    'RmpADC':         ('RmpADC',         'RmST'),
    'rmpA2':          ('rmpA2',          None),
}

VIRULENCE_GENE_GROUPS = {
    'Yersiniabactin': ['ybtS', 'ybtX', 'ybtQ', 'ybtP', 'ybtA',
                       'irp2', 'irp1', 'ybtU', 'ybtT', 'ybtE', 'fyuA'],
    'Colibactin':     ['clbA', 'clbB', 'clbC', 'clbD', 'clbE', 'clbF',
                       'clbG', 'clbH', 'clbI', 'clbL', 'clbM', 'clbN',
                       'clbO', 'clbP', 'clbQ'],
    'Aerobactin':     ['iucA', 'iucB', 'iucC', 'iucD', 'iutA'],
    'Salmochelin':    ['iroB', 'iroC', 'iroD', 'iroN'],
    'Rmp':            ['rmpA', 'rmpD', 'rmpC', 'rmpA2'],
}

MLST_ALLELES = ['gapA', 'infB', 'mdh', 'pgi', 'phoE', 'rpoB', 'tonB']

_VSCORE_COLOUR = {0: '#27ae60', 1: '#f1c40f', 2: '#e67e22',
                  3: '#e74c3c', 4: '#c0392b', 5: '#922b21'}
_RSCORE_COLOUR = {0: '#27ae60', 1: '#f39c12', 2: '#e74c3c', 3: '#922b21'}


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _present(value: str) -> bool:
    return str(value).strip() not in ('-', '', 'nan', 'None')


def _badge(text: str, bg: str = '#e74c3c', fg: str = 'white') -> str:
    return (
        f'<span style="background:{bg};color:{fg};padding:3px 9px;'
        f'border-radius:12px;margin:2px 3px;display:inline-block;'
        f'font-size:12px;font-weight:500">{text}</span>'
    )


def _absent_chip(text: str) -> str:
    return (
        f'<span style="background:#ecf0f1;color:#aab;padding:3px 9px;'
        f'border-radius:12px;margin:2px 3px;display:inline-block;'
        f'font-size:12px;text-decoration:line-through">{text}</span>'
    )


def _score_box(label: str, score, colour_map: dict) -> str:
    try:
        idx = min(int(score), max(colour_map))
    except (ValueError, TypeError):
        idx = 0
    colour = colour_map.get(idx, '#95a5a6')
    return (
        f'<div style="background:{colour};color:white;border-radius:10px;'
        f'padding:12px 8px;text-align:center">'
        f'<div style="font-size:28px;font-weight:bold;line-height:1">{score}</div>'
        f'<div style="font-size:11px;margin-top:4px;opacity:.9">{label}</div></div>'
    )


def _locus_card(name: str, allele: str | None, st_val: str | None) -> str:
    if allele:
        body = f'<b>{name}</b><br><small>{allele}</small>'
        if st_val:
            body += f'<br><small style="opacity:.8">ST {st_val}</small>'
        return (
            f'<div style="background:#e74c3c;color:white;border-radius:8px;'
            f'padding:10px 6px;text-align:center;min-height:64px">{body}</div>'
        )
    return (
        f'<div style="background:#ecf0f1;color:#aab;border-radius:8px;'
        f'padding:10px 6px;text-align:center;min-height:64px">'
        f'<b>{name}</b><br><small>absent</small></div>'
    )


def _parse_genes(raw) -> list[str]:
    s = str(raw).strip()
    if s in ('-', '', 'nan', 'None'):
        return []
    return [g.strip() for g in s.split(';') if g.strip()]


def _fmt_int(val) -> str:
    try:
        return f'{int(val):,}'
    except (ValueError, TypeError):
        return str(val)


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

def render_strain_overview(r) -> None:
    """Section 1: scores and key identity fields."""
    st.header("Strain Overview")

    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.markdown(_score_box("Virulence Score",  r['virulence_score'],  _VSCORE_COLOUR),
                 unsafe_allow_html=True)
    sc2.markdown(_score_box("Resistance Score", r['resistance_score'], _RSCORE_COLOUR),
                 unsafe_allow_html=True)
    sc3.metric("Resistance Classes", r['num_resistance_classes'])
    sc4.metric("Resistance Genes",   r['num_resistance_genes'])

    st.write("")

    info = {
        'Species':      r['species'],
        'ST (MLST)':    r['ST'],
        'K-type':       r['K_type'],
        'K-locus (KL)': r['K_locus'],
        'O-type':       r['O_type'],
    }
    st.table(pd.DataFrame(info.items(), columns=['', 'Value']).set_index(''))


def render_resistance(r) -> None:
    """Section 2: acquired resistance genes and mutations."""
    st.header("Key Resistance Determinants")

    st.subheader("Acquired resistance genes")
    acq_parts: list[str] = []
    for class_name, col in RESISTANCE_CLASSES.items():
        genes = _parse_genes(r.get(col, '-'))
        if genes:
            bg = '#922b21' if class_name in _HIGH_CONCERN else '#c0392b'
            for g in genes:
                acq_parts.append(_badge(f"{class_name} — {g}", bg=bg))

    if acq_parts:
        st.markdown(' '.join(acq_parts), unsafe_allow_html=True)
    else:
        st.success("No acquired resistance genes detected.")

    st.write("")
    st.subheader("Resistance mutations")
    mut_parts: list[str] = []
    for label, col in RESISTANCE_MUTATIONS.items():
        for m in _parse_genes(r.get(col, '-')):
            mut_parts.append(_badge(f"{label} — {m}", bg='#6c3483'))

    if mut_parts:
        st.markdown(' '.join(mut_parts), unsafe_allow_html=True)
    else:
        st.success("No resistance mutations detected.")


def render_virulence(r) -> None:
    """Section 3: virulence locus cards and K/O locus detail."""
    st.header("Virulence Profile")

    locus_cols = st.columns(len(VIRULENCE_LOCI))
    for i, (display_name, (locus_col, st_col)) in enumerate(VIRULENCE_LOCI.items()):
        allele = str(r.get(locus_col, '-')).strip()
        allele = allele if _present(allele) else None
        st_val = str(r.get(st_col, '-')).strip() if st_col else None
        st_val = st_val if st_val and _present(st_val) else None
        locus_cols[i].markdown(_locus_card(display_name, allele, st_val),
                               unsafe_allow_html=True)

    st.write("")

    with st.expander("Locus details"):
        locus_info = {
            'K-locus':         r['K_locus'],
            'K-type':          r['K_type'],
            'K confidence':    r['K_locus_confidence'],
            'K identity':      r['K_locus_identity'],
            'K missing genes': r['K_locus_missing_genes'] if _present(r['K_locus_missing_genes']) else '—',
            'O-locus':         r['O_locus'],
            'O-type':          r['O_type'],
            'O confidence':    r['O_locus_confidence'],
            'O identity':      r['O_locus_identity'],
            'O missing genes': r['O_locus_missing_genes'] if _present(r['O_locus_missing_genes']) else '—',
        }
        st.table(pd.DataFrame(locus_info.items(), columns=['', 'Value']).set_index(''))


def render_detailed_tables(r) -> None:
    """Section 4: full resistance and virulence gene tables."""
    st.header("Detailed Gene Tables")

    tab_res, tab_vir = st.tabs(["Resistance genes (full list)", "Virulence gene alleles"])

    with tab_res:
        res_rows = []
        for class_name, col in RESISTANCE_CLASSES.items():
            for g in _parse_genes(r.get(col, '-')):
                res_rows.append({'Antibiotic class': class_name, 'Gene / allele': g, 'Type': 'Acquired'})
        for label, col in RESISTANCE_MUTATIONS.items():
            for m in _parse_genes(r.get(col, '-')):
                res_rows.append({'Antibiotic class': label, 'Gene / allele': m, 'Type': 'Mutation'})
        for g in _parse_genes(r.get('truncated_resistance_hits', '-')):
            res_rows.append({'Antibiotic class': '—', 'Gene / allele': g, 'Type': 'Truncated'})

        if res_rows:
            st.dataframe(pd.DataFrame(res_rows).sort_values(['Antibiotic class', 'Type']),
                         hide_index=True, use_container_width=True)
        else:
            st.info("No resistance genes detected for this strain.")

    with tab_vir:
        vir_rows = []
        for system, genes in VIRULENCE_GENE_GROUPS.items():
            for gene in genes:
                raw = str(r.get(gene, '-')).strip()
                allele = raw if _present(raw) else None
                vir_rows.append({'System': system, 'Gene': gene,
                                 'Allele': allele if allele else '—',
                                 'Present': '✓' if allele else '✗'})

        def _highlight(row):
            colour = 'background-color:#fde8e8' if row['Present'] == '✓' else ''
            return [colour] * len(row)

        st.dataframe(pd.DataFrame(vir_rows).style.apply(_highlight, axis=1),
                     hide_index=True, use_container_width=True)


def render_strain_data(r) -> None:
    """Render all sections for a single strain row (used by standalone page)."""
    render_strain_overview(r)
    st.divider()
    res_col, vir_col = st.columns(2)
    with res_col:
        render_resistance(r)
    with vir_col:
        render_virulence(r)
    st.divider()
    render_detailed_tables(r)


def run_strain_overview(config: dict) -> None:
    st.title("Strain Overview")

    kleb = read_tabular(config['files']['kleborate_file'], sep='\t')

    try:
        strain_map = load_excel(config['files']['strain_file'])
    except Exception:
        strain_map = load_csv(config['files']['strain_file'])

    if 'overview_strain' not in st.session_state:
        st.session_state.overview_strain = (
            strain_map['ID'].iloc[0] if not strain_map.empty else None
        )

    st.sidebar.selectbox("Select Strain", strain_map['ID'], key='overview_strain')
    strain_id = st.session_state.overview_strain

    hit = kleb[kleb['strain'] == strain_id]
    if hit.empty:
        st.warning(
            f"No Kleborate data found for **{strain_id}**. "
            "Check that the strain ID matches the `strain` column in `kleborate_all.tsv`."
        )
        return

    render_strain_data(hit.iloc[0])
