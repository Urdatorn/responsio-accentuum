from lxml import etree
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from src.stats_comp import compatibility_canticum
from src.utils.utils import get_text_matrix

def canticum_with_at_least_two_strophes(xml_file, canticum_idx):
    tree = etree.parse(xml_file)
    root = tree.getroot()

    desired_canticum = root.find(f".//canticum[{canticum_idx}]")
    
    if desired_canticum is None:
        return False

    # Get all <strophe>-children of the <canticum>
    strophes = desired_canticum.findall(".//strophe")

    return len(strophes) >= 2

def canticum_number_of_strophes(xml_file: str, canticum_idx: int) -> int:
    '''
    canticum_idx: 1-based index of the canticum in the XML file
    '''
    tree = etree.parse(xml_file)
    root = tree.getroot()

    desired_canticum = root.find(f".//canticum[{canticum_idx}]")
    
    if desired_canticum is None:
        return 0

    # Get all <strophe>-children of the <canticum>
    strophes = desired_canticum.findall(".//strophe")

    return len(strophes)

def make_all_heatmaps(xml_file: str, prefix: str, suptitle: str):
    # First, count actual canticums in the file
    tree = etree.parse(xml_file)
    root = tree.getroot()
    canticums = root.findall(".//canticum")
    num_canticums = len(canticums)
    
    # Calculate grid dimensions
    cols = 5
    rows = (num_canticums + cols - 1) // cols  # Ceiling division
    
    # Create figure with subplots
    fig, axes = plt.subplots(rows, cols, figsize=(20, 4 * rows))
    fig.patch.set_facecolor('black')
    axes = axes.flatten()  # Flatten for easier indexing

    # Hide unused subplots
    for idx in range(num_canticums, rows * cols):
        axes[idx].set_visible(False)

    for idx in range(num_canticums):
        canticum_id = f"{prefix}{idx+1:02d}"
        canticum_idx = idx + 1
        ax = axes[idx]

        # Always set dark background first
        ax.set_facecolor("black")
        
        # Get number of strophes for the title
        num_strophes = canticum_number_of_strophes(xml_file, canticum_idx)
        title_text = f"{canticum_id} ({num_strophes})"
        
        if not canticum_with_at_least_two_strophes(xml_file, canticum_idx):
            # Style the skipped canticum with dark background and message
            ax.text(0.5, 0.5, f"Skipped: {canticum_id}\n(< 2 strophes)", 
                    ha='center', va='center', transform=ax.transAxes, 
                    color='white', fontsize=10)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_title(title_text, color="white", fontsize=12)
            continue
        
        try:
            # Get text matrix
            text_matrix, row_lengths = get_text_matrix(xml_file, canticum_index=canticum_idx)
            
            # Get compatibility data
            data_matrix = compatibility_canticum(xml_file, canticum_ID=canticum_id)
            
            # Pad numeric matrix for heatmap
            max_len = max(len(row) for row in data_matrix)
            padded_data = np.full((len(data_matrix), max_len), np.nan)
            for i, row in enumerate(data_matrix):
                padded_data[i, :len(row)] = row
            
            # Create heatmap
            sns.heatmap(
                padded_data,
                cmap="viridis",
                mask=np.isnan(padded_data),
                cbar=False,  # Disable individual colorbars
                ax=ax
            )
            
            # Dark styling
            ax.tick_params(colors="white", labelsize=8)
            ax.set_xlabel("")
            ax.set_ylabel("")
            ax.set_title(title_text, color="white", fontsize=12)
            
            # Overlay text (smaller font for subplots)
            for i, row in enumerate(text_matrix):
                for j, val in enumerate(row):
                    ax.text(
                        j + 0.5, i + 0.5,
                        val,
                        ha='center', va='center',
                        color='white', fontsize=6
                    )
            
            # Remove tick labels for cleaner look
            ax.set_xticks([])
            ax.set_yticks([])
            
        except Exception as e:
            # Handle cases where canticum might not exist
            ax.text(0.5, 0.5, f"Error: {canticum_id}\n{str(e)}", 
                    ha='center', va='center', transform=ax.transAxes, 
                    color='white', fontsize=10)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_title(title_text, color="white", fontsize=12)

    plt.suptitle(suptitle, 
                color="white", fontsize=16, y=0.98)
    plt.tight_layout()
    plt.show()