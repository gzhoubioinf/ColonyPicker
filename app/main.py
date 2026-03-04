import sys
import os
import yaml
import streamlit as st

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from app.colony_picker import run_colony_viewer


def load_config(config_path="config/config.yaml"):
    with open(config_path, "r") as fh:
        return yaml.safe_load(fh)


_ACCENT       = "#0d9488"
_ACCENT_BG    = "rgba(13,148,136,0.08)"
_ACCENT_MID   = "rgba(13,148,136,0.18)"
_FONT_IMPORT  = "@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');"

_WORKFLOW_CSS = f"""
<style>
{_FONT_IMPORT}
.wf-row {{ display:flex; align-items:stretch; gap:0; width:100%; }}
.wf-step {{
    flex:1; text-align:center; padding:1.4rem 1rem;
    border:1px solid rgba(128,128,128,0.2); border-radius:12px;
    background:{_ACCENT_BG};
}}
.wf-arrow {{
    display:flex; align-items:center; justify-content:center;
    flex:0 0 2.5rem;
    font-family:'Material Symbols Outlined'; font-size:1.8rem;
    color:{_ACCENT}; opacity:0.5;
}}
.wf-icon {{
    font-family:'Material Symbols Outlined'; font-size:2.8rem;
    font-weight:200; display:block; margin-bottom:0.5rem; color:{_ACCENT};
}}
.wf-num {{
    display:inline-block; font-size:0.68rem; font-weight:700;
    letter-spacing:0.1em; text-transform:uppercase;
    color:{_ACCENT}; background:{_ACCENT_MID};
    border-radius:20px; padding:0.1rem 0.55rem; margin-bottom:0.4rem;
}}
.wf-title {{ font-weight:700; font-size:0.95rem; margin-bottom:0.4rem; }}
.wf-desc  {{ font-size:0.82rem; opacity:0.8; line-height:1.45; }}
</style>
"""

_FEATURE_CSS = f"""
<style>
{_FONT_IMPORT}
.fc-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:0.75rem; width:100%; }}
.fc {{
    border:1px solid rgba(128,128,128,0.2); border-top:3px solid {_ACCENT};
    border-radius:10px; padding:1rem 1.1rem;
}}
.fc-icon {{
    font-family:'Material Symbols Outlined'; font-size:1.6rem;
    font-weight:300; margin-bottom:0.3rem; color:{_ACCENT}; display:block;
}}
.fc-title {{ font-weight:700; font-size:0.97rem; margin-bottom:0.25rem; }}
.fc-desc  {{ font-size:0.85rem; opacity:0.85; line-height:1.45; }}
</style>
"""

_FEATURES = [
    ("manage_search", "Dual-Mode Navigation",
     "Search by biological Strain ID or by exact Grid Position (Row/Column) on the plate."),
    ("grid_on", "High-Density Plate Mapping",
     "Automatically maps 384-well coordinates to 1536-well format, isolating the 2×2 "
     "quadruplicate block (replicates A–D) for any strain."),
    ("crop_free", "Dynamic Image Processing",
     "Uses OpenCV to calculate the plate grid layout via IRIS metadata or active image "
     "detection, then crops the exact colony footprint."),
    ("monitoring", "Phenotypic Metric Extraction",
     "Toggle colony size, circularity, opacity, color intensity, and biofilm area metrics "
     "displayed alongside each cropped image."),
    ("biotech", "Genomic Integration",
     "Renders a full strain overview from Kleborate — antibiotic resistance genes, "
     "virulence factors, and sequence type."),
    ("download", "Data Export",
     "Export cropped colony images in one click for presentations or downstream "
     "machine learning tasks."),
]


def render_home():
    import base64
    _pic_path = os.path.join(_project_root, "app", "assets", "Picture.png")
    with open(_pic_path, "rb") as _f:
        _pic_b64 = base64.b64encode(_f.read()).decode()
    st.markdown(
        f'<div style="text-align:center;margin:-1.5rem 0 -1rem;">'
        f'<img src="data:image/png;base64,{_pic_b64}" style="max-width:520px;width:100%;">'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        "A genotype–phenotype browser for *Klebsiella pneumoniae* — "
        "linking macroscopic plate images with IRIS morphology measurements "
        "and Kleborate genomic data."
    )
    st.divider()
    st.markdown("#### Workflow and Methodology")

    _WORKFLOW = [
        ("analytics", "Step 1", "Phenotypic Data Generation",
         "Clinical strains are arrayed and grown on agar plates during high-throughput chemical genomics screening. "
         "The resulting macroscopic plate images are processed using IRIS software to extract quantitative morphology "
         "metrics for each colony."),
        ("genetics", "Step 2", "Genotypic Data Generation",
         "In parallel, the genomes of these same clinical strains are analyzed using Kleborate to identify sequence "
         "types, antimicrobial resistance genes, and virulence determinants."),
        ("hub", "Step 3", "Data Integration",
         "ColonyPicker brings these two streams together. The application seamlessly links the physical colony "
         "measurements from IRIS with the genomic profiles from Kleborate, allowing researchers to explore "
         "genotype–phenotype relationships interactively."),
    ]

    wf_steps = ""
    for i, (icon, num, title, desc) in enumerate(_WORKFLOW):
        if i > 0:
            wf_steps += '<div class="wf-arrow material-symbols-outlined">arrow_forward</div>'
        wf_steps += (
            f'<div class="wf-step">'
            f'<span class="wf-icon material-symbols-outlined">{icon}</span>'
            f'<span class="wf-num">{num}</span>'
            f'<div class="wf-title">{title}</div>'
            f'<div class="wf-desc">{desc}</div>'
            f'</div>'
        )
    st.html(_WORKFLOW_CSS + f'<div class="wf-row">{wf_steps}</div>')

    st.divider()
    st.markdown("#### Key features")

    fc_items = "".join(
        f'<div class="fc">'
        f'<span class="fc-icon material-symbols-outlined">{icon}</span>'
        f'<div class="fc-title">{title}</div>'
        f'<div class="fc-desc">{desc}</div>'
        f'</div>'
        for icon, title, desc in _FEATURES
    )
    st.html(_FEATURE_CSS + f'<div class="fc-grid">{fc_items}</div>')

    st.divider()
    st.info("Use the **navigation panel on the left** to get started.")


def render_about():
    st.title("About")
    st.markdown(
        """

        This application links macroscopic plate images with detailed metadata
        (IRIS measurements and Kleborate genomic data). It allows researchers to
        seamlessly navigate high-density microplates, inspect physical colony
        traits, and correlate them with genomic profiles such as antibiotic
        resistance and virulence.

        This application was developed to support high-throughput phenotypic
        screening of *Klebsiella pneumoniae* clinical isolates.  Colony images
        are captured with a flatbed scanner, quantified with
        [IRIS](https://github.com/critichu/Iris), and linked to whole-genome
        sequence data processed with
        [Kleborate](https://github.com/klebgenomics/Kleborate).

        ### References
    
       If you use ColonyPicker in your research, please cite our work:
       * 
    
       This application relies on the following foundational workflows and tools. Please also consider citing them:
    
       * **High-Throughput Phenotypic Screening Pipeline:**
       Williams G., Ahmad H., Sutherland S., et al. (2025). High-throughput chemical genomic screening: a step-by-step workflow from plate to phenotype. *mSystems*, 10(12), e00885-25. DOI: [10.1128/msystems.00885-25](https://doi.org/10.1128/msystems.00885-25)
    
       * **Kleborate (Genomic Profiling):**
       Lam, M. M. C., et al. (2021). A genomic surveillance framework and genotyping tool for *Klebsiella pneumoniae* and its related species complex. *Nature Communications*, 12(1), 4188. DOI: [10.1038/s41467-021-24448-3](https://doi.org/10.1038/s41467-021-24448-3)
    
       * **IRIS (Phenotypic Image Analysis):**
       Kritikos, G., Banzhaf, M., Herrera-Dominguez, L., et al. (2017). A tool named Iris for versatile high-throughput phenotyping in microorganisms. *Nature Microbiology*, 2(5), 17014. DOI: [10.1038/nmicrobiol.2017.14](https://doi.org/10.1038/nmicrobiol.2017.14)

        ### Data
        * **Plate Images:** 1536-format agar plates imaged across multiple chemical conditions.
        * **Morphology Metrics:** Size, circularity, opacity, biofilm area, and more (extracted via IRIS).
        * **Genomic Metadata:** Sequence type, AMR genes, and virulence loci (analyzed via Kleborate).

        ### Contact and Collaboration

        ColonyPicker is a joint project developed by the **[Infectious Disease Epidemiology Lab](https://ide.kaust.edu.sa/)** (KAUST) and the **Banzhaf Lab** (Newcastle University).

        **Support and Inquiries:**

        | Name | Email |
        | :--- | :--- |
        | **Ge Zhou** | [ge.zhou@kaust.edu.sa](mailto:ge.zhou@kaust.edu.sa) |
        | **Danesh Moradigaravand** | [danesh.moradigaravand@kaust.edu.sa](mailto:danesh.moradigaravand@kaust.edu.sa) |
        | **Manuel Banzhaf** | [manuel.banzhaf@newcastle.ac.uk](mailto:manuel.banzhaf@newcastle.ac.uk) |
        """
    )


def render_help():
    st.title("Help Guide")
    st.markdown("Welcome to the ColonyPicker Help Guide. Expand the sections below to learn how to navigate the app, interpret results, and format your data.")

    with st.expander("🚀 Getting started", expanded=True):
        st.info(
        """
        1. Use the **navigation panel on the left** to move between pages.
        2. Go to **Colony Viewer** to inspect a specific strain or plate position.
        3. Select your lookup method, choose a condition and plate/batch, then click **Analyse**.
        """, 
        icon="💡"
    )

    with st.expander("🔍 Colony Viewer — step by step"):
        st.markdown(
    """
    **Follow these steps to extract and analyze colony morphology:**

    1. **Select lookup method:** Choose **Search by strain ID** or **Enter grid position** in the sidebar.
    2. **Define target:** Select the specific strain ID from the dropdown (or enter row/column numbers).
    3. **Set condition:** Pick an experimental condition (e.g., *Ceftazidime-1ugml*).
    4. **Choose replicate:** Select a **Plate / Batch** run.
    5. **Filter metrics:** Optionally add or remove the morphological **Metrics** you want to display.
    6. **Run analysis:** Click the red **Analyse** button to load the plate image and extract colony crops.
    """
    )

    with st.expander("📊 Understanding the results"):
        st.markdown(
    """
    Once the analysis is complete, the dashboard displays several key areas:

    * **Grid overlay:** Shows the full 1536-well plate with the 2×2 quadruplicate block (replicates A–D) highlighted in blue.
    * **Colony images:** Four high-resolution, cropped images of the extracted colonies.
    * **Genomic panel:** Displays sequence type, AMR genes, and virulence loci directly pulled from Kleborate.

    **Key Morphology Metrics (from IRIS):**
    * **Colony size:** Total colony area measured in pixels.
    * **Circularity:** How perfectly round the colony is (1.0 = perfect circle).
    * **Opacity:** Optical density proxy representing colony thickness/density.
    * **Biofilm area ratio:** The fraction of the colony footprint covered by biofilm.
    """
    )

    with st.expander("💾 Saving colony images"):
        st.markdown("You can easily export the extracted colony images for presentations or external machine learning workflows.")
        st.success(
            "Click **Save colony images** (at the bottom of the results page) to export the four replicate crops as `.png` files into a `saved_colonies/` folder in your working directory.",
            icon="✅"
        )

    with st.expander("📁 File & data requirements"):
        st.markdown("ColonyPicker relies on specific file structures defined in your `config.yaml` file.")

    st.markdown("**Required Files:**")
    st.markdown(
        """
        | Configuration Key | Expected Content |
        | :--- | :--- |
        | `image_directory` | Folder containing `.JPG.grid.jpg` plate images. |
        | `iris_directory` | Folder containing `.JPG.iris` measurement files. |
        | `strain_file` | CSV or Excel mapping file with `ID`, `Row`, and `Column` columns. |
        | `kleborate_file` | TSV output from Kleborate containing a `strain` column. |
        """
    )

    st.divider()
    st.markdown("**Image Naming Convention:**")
    st.markdown("To ensure the app links conditions to the correct plates, your image filenames **must** follow this exact pattern:")
    st.code("<Condition>-<plate>-<batch>_A.JPG.grid.jpg", language="text")
    st.caption("Example: `Ceftazidime-1ugml-1-1_A.JPG.grid.jpg`")


_SIDEBAR_CSS = """
<style>
[data-testid="stSidebar"] > div:first-child {
    padding-top: 0.5rem;
}
.sidebar-title {
    font-size: 2.8rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    line-height: 1.3;
    margin-bottom: 0.15rem;
    text-align: center;
}
.sidebar-subtitle {
    font-size: 0.78rem;
    opacity: 0.6;
    margin-bottom: 0;
    text-align: center;
}
/* Nav buttons: full width, left-aligned, no border */
[data-testid="stSidebar"] .stButton > button {
    width: 100%;
    text-align: left;
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 0.45rem 0.75rem;
    font-size: 0.95rem;
    color: inherit;
    transition: background 0.15s;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(13, 148, 136, 0.1);
    border: none;
}
[data-testid="stSidebar"] .stButton > button:focus:not(:active) {
    border: none;
    box-shadow: none;
}
/* Active page button */
[data-testid="stSidebar"] .stButton > button[data-active="true"] {
    background: rgba(13, 148, 136, 0.15);
    color: #0d9488;
    font-weight: 600;
}
/* Analyse (primary) button — red */
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: #c0392b !important;
    color: #ffffff !important;
    border: none !important;
    text-align: center !important;
    font-weight: 600 !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
    background: #a93226 !important;
}
</style>
"""

_NAV_PAGES = ["Home", "Colony Viewer", "Help", "About"]


def main():
    st.set_page_config(page_title="ColonyPicker", layout="wide")

    config = load_config()

    if "page" not in st.session_state:
        st.session_state.page = "Home"

    st.html(_SIDEBAR_CSS)
    import base64
    with open(os.path.join(_project_root, "app", "assets", "logo.png"), "rb") as _f:
        _logo_b64 = base64.b64encode(_f.read()).decode()
    st.sidebar.markdown(
        f'<div style="text-align:center;margin-bottom:0.5rem;">'
        f'<img src="data:image/png;base64,{_logo_b64}" width="80"></div>',
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        '<p style="font-size:0.78rem;opacity:0.6;margin:0;text-align:center;">'
        'Genotype-phenotype colony viewer.</p>',
        unsafe_allow_html=True,
    )
    st.sidebar.divider()

    for nav_page in _NAV_PAGES:
        label = f"**{nav_page}**" if st.session_state.page == nav_page else nav_page
        if st.sidebar.button(label, key=f"nav_{nav_page}"):
            st.session_state.page = nav_page

    page = st.session_state.page

    if page == "Home":
        render_home()
    elif page == "Colony Viewer":
        run_colony_viewer(config)
    elif page == "Help":
        render_help()
    else:
        render_about()


if __name__ == "__main__":
    main()
