from lxml import etree
from text_matrix_ol02_strophes import text_matrix
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from fractions import Fraction
from src.stats_comp import compatibility_canticum

def make_one_heatmap(xml_file: str, responsion_attribute: str, title: str, representative_strophe: int, save: bool, show: bool = True):

    # -----------------------------
    # Prepare text matrix
    # -----------------------------

    #text_matrix, row_lengths = get_text_matrix(xml_file, responsion_attribute, representative_strophe)
    num_rows_text = len(text_matrix)

    # -----------------------------
    # Plot heatmap with text
    # -----------------------------

    data_matrix = compatibility_canticum(xml_file, responsion_attribute)
    row_lengths_data = [len(row) for row in data_matrix]
    num_rows_data = len(data_matrix)

    print("Length of each row (data matrix):", row_lengths_data)

    # -----------------------------
    # Shape check
    # -----------------------------

    if num_rows_text != num_rows_data:
        raise ValueError(f"Number of rows mismatch: text_matrix={num_rows_text}, data_matrix={num_rows_data}")

    max_len_text = max(len(row) for row in text_matrix)
    max_len_data = max(len(row) for row in data_matrix)

    if max_len_text != max_len_data:
        raise ValueError(f"Max row length mismatch: max text length={max_len_text}, max data length={max_len_data}")

    # -----------------------------
    # Pad numeric matrix for heatmap
    # -----------------------------
    max_len = max_len_data
    padded_data = np.full((len(data_matrix), max_len), np.nan)
    for i, row in enumerate(data_matrix):
        padded_data[i, :len(row)] = row


    min_val = np.nanmin(padded_data)
    min_frac = Fraction(min_val).limit_denominator()  # exact rational

    # denominator b
    den = min_frac.denominator
    start = min_frac.numerator

    # Generate fractions from a/b to b/b
    fractions = [Fraction(n, den) for n in range(start, den + 1)]
    tick_positions = [float(fr) for fr in fractions]
    tick_labels = [str(fr) for fr in fractions]

    # -----------------------------
    # Plot heatmap
    # -----------------------------
    plt.figure(figsize=(12, 8))
    ax = sns.heatmap(
        padded_data,
        cmap="viridis",
        mask=np.isnan(padded_data),
        cbar=True,
        cbar_kws={'ticks': tick_positions}
    )

    # Set fraction labels
    colorbar = ax.collections[0].colorbar
    colorbar.set_ticklabels(tick_labels)

    # Overlay text
    for i, row in enumerate(text_matrix):
        for j, val in enumerate(row):
            ax.text(
                j + 0.5, i + 0.5,
                val,
                ha='center', va='center',
                color='white', fontsize=10
            )

    plt.xlabel("Metrical position (resolutions merged)")
    plt.ylabel("Line ordinal")
    plt.title(title)
    plt.yticks(
        ticks=np.arange(len(data_matrix)) + 0.5,
        labels=np.arange(1, len(data_matrix) + 1)
    )

    out_file = f"media/heatmaps/strophes/text/{responsion_attribute}.png"

    if save:
        plt.savefig(out_file, dpi=600, bbox_inches="tight")
    if show:
        plt.show()

make_one_heatmap("data/compiled/strophes/ht_olympians_strophes.xml", "ol02", "Mel. Comp. Heatmap of Olympia 2 (Strophic-Antistrophic)", representative_strophe=1, save=True, show=True)

