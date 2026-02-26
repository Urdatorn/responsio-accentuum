import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np

def plot_dict(play_dict, y_start=0.8, y_end=0.84):
    # Extract keys and values
    plays = list(play_dict.keys())
    stats = list(play_dict.values())

    # Determine unique prefix groups
    prefixes = [key[:-2] for key in plays]
    unique_prefixes = sorted(set(prefixes))

    # Assign a unique color to each prefix group
    cmap = cm.get_cmap('tab20', len(unique_prefixes))  # or 'viridis', 'Set3', etc.
    prefix_to_color = {prefix: cmap(i) for i, prefix in enumerate(unique_prefixes)}

    # Map each play to its group color
    colors = [prefix_to_color[key[:-2]] for key in plays]

    # Create the bar chart
    plt.figure(figsize=(10, 6))
    plt.bar(plays, stats, color=colors)

    # Add labels and title
    plt.xlabel('Play (abbreviations)', fontsize=12)
    plt.ylabel('Compatibility Metrics', fontsize=12)
    plt.title('Compatibility Metric by Play', fontsize=14)
    plt.xticks(rotation=45)

    # Adjust y-axis limits
    plt.ylim(y_start, y_end)

    plt.tight_layout()
    plt.show()