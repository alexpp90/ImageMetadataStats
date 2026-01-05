import os
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def _open_file_for_user(filepath: Path):
    """Opens a file in the default application in a cross-platform way."""
    try:
        if sys.platform == "win32":
            os.startfile(filepath)
        elif sys.platform == "darwin":
            subprocess.run(['open', str(filepath)], check=True)
        else:
            subprocess.run(['xdg-open', str(filepath)], check=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"Could not open file '{filepath}'. Please open it manually.")
        print(f"Error: {e}")


def create_plots(df: pd.DataFrame, output_dir: Path, show_plots: bool = False):
    """Generates and saves plots for the analyzed data, optionally opening them."""
    print(f"\nGenerating plots in '{output_dir}'...")
    output_dir.mkdir(parents=True, exist_ok=True)

    plt.style.use('seaborn-v0_8-whitegrid')

    # Shutter Speed (Bar Chart)
    if df['Shutter Speed'].notna().any():
        top_shutter_speeds = df['Shutter Speed'].value_counts().nlargest(25)

        # Sort by shutter speed value (the index) before plotting
        top_shutter_speeds = top_shutter_speeds.sort_index()

        def format_shutter(val):
            if val >= 1:
                return f"{val:.1f}s" if val % 1 != 0 else f"{int(val)}s"
            denominator = 1 / val
            if abs(denominator - round(denominator)) < 0.01:
                return f"1/{int(round(denominator))}s"
            return f"{val:.5f}s"

        # Create new labels for the plot from the float index
        plot_labels = top_shutter_speeds.index.map(format_shutter)

        plt.figure(figsize=(12, 7))
        ax = top_shutter_speeds.plot(kind='bar', rot=45)
        ax.set_xticklabels(plot_labels)
        plt.title('Top 25 Most Used Shutter Speeds')
        plt.xlabel('Shutter Speed')
        plt.ylabel('Count')
        plt.tight_layout()
        plt.savefig(output_dir / 'shutter_speed_distribution.png')
        plt.close()
    else:
        print("Skipping Shutter Speed plot: No data available.")

    # Aperture (Bar Chart)
    if df['Aperture'].notna().any():
        plt.figure(figsize=(12, 6))
        df['Aperture'].value_counts().sort_index().plot(kind='bar', rot=45)
        plt.title('Aperture (F-Number) Distribution')
        plt.xlabel('Aperture (f-stop)')
        plt.ylabel('Count')
        plt.tight_layout()
        aperture_path = output_dir / 'aperture_distribution.png'
        plt.savefig(aperture_path)
        plt.close()
        if show_plots:
            _open_file_for_user(aperture_path)
    else:
        print("Skipping Aperture plot: No data available.")

    # ISO (Bar Chart)
    if df['ISO'].notna().any():
        plt.figure(figsize=(12, 6))
        df['ISO'].value_counts().sort_index().plot(kind='bar', rot=45)
        plt.title('ISO Distribution')
        plt.xlabel('ISO')
        plt.ylabel('Count')
        plt.tight_layout()
        plt.savefig(output_dir / 'iso_distribution.png')
        plt.close()
    else:
        print("Skipping ISO plot: No data available.")

    # Focal Length (Bar Chart)
    if df['Focal Length'].notna().any():
        # Let's show a bar chart for the top 25 focal lengths for clarity
        top_focal_lengths = df['Focal Length'].value_counts().nlargest(25)
        plt.figure(figsize=(12, 7))
        top_focal_lengths.sort_index().plot(kind='bar', rot=45)
        plt.title('Top 25 Most Used Focal Lengths')
        plt.xlabel('Focal Length (mm)')
        plt.ylabel('Count')
        plt.tight_layout()
        focal_length_path = output_dir / 'focal_length_distribution.png'
        plt.savefig(focal_length_path)
        plt.close()
        if show_plots:
            _open_file_for_user(focal_length_path)
    else:
        print("Skipping Focal Length plot: No data available.")

    # Lens (Horizontal Bar Chart)
    if df['Lens'].notna().any():
        # Adjust figure size to better accommodate long lens names
        plt.figure(figsize=(12, max(6, len(df['Lens'].unique()) * 0.4)))
        df['Lens'].value_counts().sort_values().plot(kind='barh')
        plt.title('Lens Usage')
        plt.xlabel('Number of Photos')
        plt.ylabel('Lens Model')
        plt.tight_layout()
        lens_path = output_dir / 'lens_usage.png'
        plt.savefig(lens_path)
        plt.close()
        if show_plots:
            _open_file_for_user(lens_path)
    else:
        print("Skipping Lens plot: No data available.")

    # Aperture & Focal Length Combinations (Bar Chart)
    if df['Aperture'].notna().any() and df['Focal Length'].notna().any():
        # Let's show a bar chart for the top 25 combinations for clarity
        combo_counts = df.dropna(
            subset=['Aperture', 'Focal Length']
        ).groupby(['Aperture', 'Focal Length']).size().nlargest(25)

        # Format labels for the plot
        combo_labels = [f"f/{aperture} @ {int(focal)}mm" for aperture, focal in combo_counts.index]

        plt.figure(figsize=(12, max(8, len(combo_counts) * 0.4)))
        # Create a temporary series with string labels for plotting
        plot_series = pd.Series(combo_counts.values, index=combo_labels)
        plot_series.sort_values().plot(kind='barh')
        plt.title('Top 25 Most Used Aperture & Focal Length Combinations')
        plt.xlabel('Number of Photos')
        plt.ylabel('Combination (Aperture @ Focal Length)')
        plt.tight_layout()
        combo_path = output_dir / 'aperture_focal_length_combinations.png'
        plt.savefig(combo_path)
        plt.close()
        if show_plots:
            _open_file_for_user(combo_path)
    else:
        print("Skipping Aperture & Focal Length combination plot: No data available.")

    print("Plots saved successfully.")
