import matplotlib.pyplot as plt

def plot_dict(play_dict, y_start=0.8, y_end=0.84):
    # Extract keys and values from the dictionary
    plays = list(play_dict.keys())
    stats = list(play_dict.values())

    # Create a bar chart
    plt.figure(figsize=(10, 6))
    plt.bar(plays, stats, color='skyblue')

    # Add labels and title
    plt.xlabel('Play (abbreviations)', fontsize=12)
    plt.ylabel('Compatibility Metrics', fontsize=12)
    plt.title('Compatibility Metric by Play', fontsize=14)
    plt.xticks(rotation=45)

    # Adjust y-axis limits to focus on the range of interest
    plt.ylim(y_start, y_end)

    plt.tight_layout()

    # Show the plot
    plt.show()

