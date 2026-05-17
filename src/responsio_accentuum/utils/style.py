from cycler import cycler
import matplotlib.pyplot as plt
from matplotlib import font_manager
from pathlib import Path


def find_project_root(start: Path, markers=("pyproject.toml", ".git")):
    for p in [start] + list(start.parents):
        if any((p / m).exists() for m in markers):
            return p
    raise RuntimeError("Project root not found")


ROOT = find_project_root(Path(__file__))


# --- Font setup (Brill) ---
font_path = ROOT / "media" / "fonts" / "Brill-Roman.ttf"
font_manager.fontManager.addfont(font_path)
prop = font_manager.FontProperties(fname=font_path)
font_name = prop.get_name()


# --- Grayscale palette (print-safe) ---
GRAY_LEVELS = [
    "0.0",
    "0.25",
    "0.4",
    "0.55",
    "0.7",
]


# --- Markers ---
MARKERS = [
    "o",
    "s",
    "D",
    "^",
    "v",
    "x",
    "+",
]


# --- Hatches ---
HATCHES = [
    "",
    "/",
    "\\",
    "|",
    "-",
    "+",
    "x",
    "o",
    "O",
    ".",
]


def apply_bw_journal_style(shape="square"):
    """
    Apply black-and-white journal style (118 × 180 mm layout).
    
    Layouts: 'square' (118 × 118 mm), 'landscape' (118 × 59 mm), 'portrait' (118 × 180 mm)
    """

    plt.style.use("default")

    plt.rcParams["axes.prop_cycle"] = cycler(color=GRAY_LEVELS) # markers here lead to bugs

    # --- NEW: enforce stable line defaults ---
    plt.rcParams["lines.linestyle"] = "-"
    plt.rcParams["lines.marker"] = ""

    # --- Resolution ---
    plt.rcParams["figure.dpi"] = 600
    plt.rcParams["savefig.dpi"] = 600

    # --- Figure size (typesetting area is 118 mm x 180 mm) ---
    if shape == "square":
        plt.rcParams["figure.figsize"] = (11.8 / 2.54, 11.8 / 2.54)
        
    elif shape == "landscape":
        plt.rcParams["figure.figsize"] = (11.8 / 2.54, 11.8 / (2 * 2.54))
        
    elif shape == "portrait":
        plt.rcParams["figure.figsize"] = (11.8 / 2.54, 18.0 / 2.54)

    # --- Line robustness ---
    plt.rcParams["lines.linewidth"] = 1.2
    plt.rcParams["lines.markersize"] = 4
    plt.rcParams["lines.markeredgewidth"] = 0.5

    # --- Axes ---
    plt.rcParams["axes.linewidth"] = 0.8

    # --- Ticks ---
    plt.rcParams["xtick.major.width"] = 0.6
    plt.rcParams["ytick.major.width"] = 0.6

    # --- Fonts ---
    plt.rcParams["font.size"] = 9
    plt.rcParams["axes.titlesize"] = 10
    plt.rcParams["axes.labelsize"] = 9
    plt.rcParams["xtick.labelsize"] = 8
    plt.rcParams["ytick.labelsize"] = 8
    plt.rcParams["legend.fontsize"] = 8

    # --- Brill font ---
    plt.rcParams["font.family"] = "serif"
    plt.rcParams["font.serif"] = [font_name]

    # --- Math text ---
    plt.rcParams["mathtext.fontset"] = "cm"
    plt.rcParams["mathtext.rm"] = "cmr10"
    plt.rcParams["mathtext.it"] = "cmmi10"
    plt.rcParams["mathtext.bf"] = "cmb10"
    plt.rcParams["axes.formatter.use_mathtext"] = True

    # --- Grid ---
    plt.rcParams["axes.grid"] = True
    plt.rcParams["grid.color"] = "0.85"
    plt.rcParams["grid.linewidth"] = 0.5
    plt.rcParams["grid.linestyle"] = "-"

    # --- Font embedding ---
    plt.rcParams["pdf.fonttype"] = 42
    plt.rcParams["ps.fonttype"] = 42

    return {
        "grays": GRAY_LEVELS,
        "markers": MARKERS,
        "hatches": HATCHES,
    }


def apply_histogram_style(ax, n_series):
    for i, patch_container in enumerate(ax.containers):
        hatch = HATCHES[i % len(HATCHES)]

        for patch in patch_container:
            patch.set_hatch(hatch)
            patch.set_edgecolor("black")
            patch.set_facecolor("none")
            patch.set_linewidth(0.8)