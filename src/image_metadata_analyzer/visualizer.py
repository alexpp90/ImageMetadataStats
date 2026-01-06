import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
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


def get_shutter_speed_plot(df: pd.DataFrame) -> Optional[Figure]:
    if not df['Shutter Speed'].notna().any():
        return None

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

    fig = Figure(figsize=(12, 7))
    ax = fig.add_subplot(111)
    top_shutter_speeds.plot(kind='bar', rot=45, ax=ax)
    ax.set_xticklabels(plot_labels)
    ax.set_title('Top 25 Most Used Shutter Speeds')
    ax.set_xlabel('Shutter Speed')
    ax.set_ylabel('Count')
    fig.tight_layout()
    return fig


def get_aperture_plot(df: pd.DataFrame) -> Optional[Figure]:
    if not df['Aperture'].notna().any():
        return None

    fig = Figure(figsize=(12, 6))
    ax = fig.add_subplot(111)
    df['Aperture'].value_counts().sort_index().plot(kind='bar', rot=45, ax=ax)
    ax.set_title('Aperture (F-Number) Distribution')
    ax.set_xlabel('Aperture (f-stop)')
    ax.set_ylabel('Count')
    fig.tight_layout()
    return fig


def get_iso_plot(df: pd.DataFrame) -> Optional[Figure]:
    if not df['ISO'].notna().any():
        return None

    fig = Figure(figsize=(12, 6))
    ax = fig.add_subplot(111)
    df['ISO'].value_counts().sort_index().plot(kind='bar', rot=45, ax=ax)
    ax.set_title('ISO Distribution')
    ax.set_xlabel('ISO')
    ax.set_ylabel('Count')
    fig.tight_layout()
    return fig


def get_focal_length_plot(df: pd.DataFrame) -> Optional[Figure]:
    if not df['Focal Length'].notna().any():
        return None

    # Let's show a bar chart for the top 25 focal lengths for clarity
    top_focal_lengths = df['Focal Length'].value_counts().nlargest(25)
    fig = Figure(figsize=(12, 7))
    ax = fig.add_subplot(111)
    top_focal_lengths.sort_index().plot(kind='bar', rot=45, ax=ax)
    ax.set_title('Top 25 Most Used Focal Lengths')
    ax.set_xlabel('Focal Length (mm)')
    ax.set_ylabel('Count')
    fig.tight_layout()
    return fig


def get_lens_plot(df: pd.DataFrame) -> Optional[Figure]:
    if not df['Lens'].notna().any():
        return None

    # Adjust figure size to better accommodate long lens names
    fig = Figure(figsize=(12, max(6, len(df['Lens'].unique()) * 0.4)))
    ax = fig.add_subplot(111)
    df['Lens'].value_counts().sort_values().plot(kind='barh', ax=ax)
    ax.set_title('Lens Usage')
    ax.set_xlabel('Number of Photos')
    ax.set_ylabel('Lens Model')
    fig.tight_layout()
    return fig


def get_combination_plot(df: pd.DataFrame) -> Optional[Figure]:
    if not (df['Aperture'].notna().any() and df['Focal Length'].notna().any()):
        return None

    # Let's show a bar chart for the top 25 combinations for clarity
    combo_counts = df.dropna(
        subset=['Aperture', 'Focal Length']
    ).groupby(['Aperture', 'Focal Length']).size().nlargest(25)

    # Format labels for the plot
    combo_labels = [f"f/{aperture} @ {int(focal)}mm" for aperture, focal in combo_counts.index]

    fig = Figure(figsize=(12, max(8, len(combo_counts) * 0.4)))
    ax = fig.add_subplot(111)
    # Create a temporary series with string labels for plotting
    plot_series = pd.Series(combo_counts.values, index=combo_labels)
    plot_series.sort_values().plot(kind='barh', ax=ax)
    ax.set_title('Top 25 Most Used Aperture & Focal Length Combinations')
    ax.set_xlabel('Number of Photos')
    ax.set_ylabel('Combination (Aperture @ Focal Length)')
    fig.tight_layout()
    return fig


def create_plots(df: pd.DataFrame, output_dir: Path, show_plots: bool = False):
    """Generates and saves plots for the analyzed data, optionally opening them."""
    print(f"\nGenerating plots in '{output_dir}'...")
    output_dir.mkdir(parents=True, exist_ok=True)

    plt.style.use('seaborn-v0_8-whitegrid')

    # Shutter Speed
    fig = get_shutter_speed_plot(df)
    if fig:
        fig.savefig(output_dir / 'shutter_speed_distribution.png')
    else:
        print("Skipping Shutter Speed plot: No data available.")

    # Aperture
    fig = get_aperture_plot(df)
    if fig:
        aperture_path = output_dir / 'aperture_distribution.png'
        fig.savefig(aperture_path)
        if show_plots:
            _open_file_for_user(aperture_path)
    else:
        print("Skipping Aperture plot: No data available.")

    # ISO
    fig = get_iso_plot(df)
    if fig:
        fig.savefig(output_dir / 'iso_distribution.png')
    else:
        print("Skipping ISO plot: No data available.")

    # Focal Length
    fig = get_focal_length_plot(df)
    if fig:
        focal_length_path = output_dir / 'focal_length_distribution.png'
        fig.savefig(focal_length_path)
        if show_plots:
            _open_file_for_user(focal_length_path)
    else:
        print("Skipping Focal Length plot: No data available.")

    # Lens
    fig = get_lens_plot(df)
    if fig:
        lens_path = output_dir / 'lens_usage.png'
        fig.savefig(lens_path)
        if show_plots:
            _open_file_for_user(lens_path)
    else:
        print("Skipping Lens plot: No data available.")

    # Aperture & Focal Length Combinations
    fig = get_combination_plot(df)
    if fig:
        combo_path = output_dir / 'aperture_focal_length_combinations.png'
        fig.savefig(combo_path)
        if show_plots:
            _open_file_for_user(combo_path)
    else:
        print("Skipping Aperture & Focal Length combination plot: No data available.")

    print("Plots saved successfully.")
