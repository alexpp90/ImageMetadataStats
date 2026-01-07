import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from image_metadata_analyzer.utils import aggregate_focal_lengths


def _open_file_for_user(filepath: Path):
    """Opens a file in the default application in a cross-platform way."""
    try:
        if sys.platform == "win32":
            os.startfile(filepath)
        elif sys.platform == "darwin":
            subprocess.run(["open", str(filepath)], check=True)
        else:
            subprocess.run(["xdg-open", str(filepath)], check=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"Could not open file '{filepath}'. Please open it manually.")
        print(f"Error: {e}")


def get_shutter_speed_plot(data: List[Dict]) -> Optional[Figure]:
    values = [d["Shutter Speed"] for d in data if d.get("Shutter Speed") is not None]
    if not values:
        return None

    # Increase default font size for better readability on high-res screens
    plt.rcParams.update({"font.size": 12, "axes.titlesize": 14, "axes.labelsize": 12})

    counter = Counter(values)
    top_shutter_speeds = dict(counter.most_common(25))

    # Sort by shutter speed value (the key)
    sorted_items = sorted(top_shutter_speeds.items(), key=lambda x: x[0])
    x_vals = [x[0] for x in sorted_items]
    y_vals = [x[1] for x in sorted_items]

    def format_shutter(val):
        if val >= 1:
            return f"{val:.1f}s" if val % 1 != 0 else f"{int(val)}s"
        denominator = 1 / val
        if abs(denominator - round(denominator)) < 0.01:
            return f"1/{int(round(denominator))}s"
        return f"{val:.5f}s"

    plot_labels = [format_shutter(v) for v in x_vals]

    fig = Figure(figsize=(12, 7), dpi=100)
    ax = fig.add_subplot(111)
    ax.bar(range(len(x_vals)), y_vals)
    ax.set_xticks(range(len(x_vals)))
    ax.set_xticklabels(plot_labels, rotation=45)
    ax.set_title("Top 25 Most Used Shutter Speeds")
    ax.set_xlabel("Shutter Speed")
    ax.set_ylabel("Count")
    fig.tight_layout()
    return fig


def get_aperture_plot(data: List[Dict]) -> Optional[Figure]:
    values = [d["Aperture"] for d in data if d.get("Aperture") is not None]
    if not values:
        return None

    counter = Counter(values)
    sorted_items = sorted(counter.items())  # Sort by aperture value
    x_vals = [str(x[0]) for x in sorted_items]
    y_vals = [x[1] for x in sorted_items]

    fig = Figure(figsize=(12, 6), dpi=100)
    ax = fig.add_subplot(111)
    ax.bar(x_vals, y_vals)
    ax.tick_params(axis="x", rotation=45)
    ax.set_title("Aperture (F-Number) Distribution")
    ax.set_xlabel("Aperture (f-stop)")
    ax.set_ylabel("Count")
    fig.tight_layout()
    return fig


def get_iso_plot(data: List[Dict]) -> Optional[Figure]:
    values = [d["ISO"] for d in data if d.get("ISO") is not None]
    if not values:
        return None

    counter = Counter(values)
    sorted_items = sorted(counter.items())  # Sort by ISO value
    x_vals = [str(x[0]) for x in sorted_items]
    y_vals = [x[1] for x in sorted_items]

    fig = Figure(figsize=(12, 6), dpi=100)
    ax = fig.add_subplot(111)
    ax.bar(x_vals, y_vals)
    ax.tick_params(axis="x", rotation=45)
    ax.set_title("ISO Distribution")
    ax.set_xlabel("ISO")
    ax.set_ylabel("Count")
    fig.tight_layout()
    return fig


def get_focal_length_plot(data: List[Dict]) -> Optional[Figure]:
    values = [d["Focal Length"] for d in data if d.get("Focal Length") is not None]
    if not values:
        return None

    # Use aggregation logic
    aggregated_fls = aggregate_focal_lengths(values)

    # Sort by the representative value (sort_key) to ensure X-axis is ordered
    aggregated_fls.sort(key=lambda x: x[2])

    x_vals = [x[0] for x in aggregated_fls]
    y_vals = [x[1] for x in aggregated_fls]

    fig = Figure(figsize=(12, 7), dpi=100)
    ax = fig.add_subplot(111)
    ax.bar(x_vals, y_vals)
    ax.tick_params(axis="x", rotation=45)
    ax.set_title("Focal Length Distribution")
    ax.set_xlabel("Focal Length (mm)")
    ax.set_ylabel("Count")
    fig.tight_layout()
    return fig


def get_equivalent_focal_length_plot(data: List[Dict]) -> Optional[Figure]:
    values = [d["Focal Length (35mm)"] for d in data if d.get("Focal Length (35mm)") is not None]
    if not values:
        return None

    # Round to nearest integer for cleaner plotting
    values = [int(round(v)) for v in values]

    counter = Counter(values)
    top_items = dict(counter.most_common(25))
    sorted_items = sorted(top_items.items())  # Sort by focal length value
    x_vals = [str(x[0]) for x in sorted_items]
    y_vals = [x[1] for x in sorted_items]

    fig = Figure(figsize=(12, 7), dpi=100)
    ax = fig.add_subplot(111)
    ax.bar(x_vals, y_vals)
    ax.tick_params(axis="x", rotation=45)
    ax.set_title("Top 25 Most Used Equivalent Focal Lengths (35mm)")
    ax.set_xlabel("Equivalent Focal Length (mm)")
    ax.set_ylabel("Count")
    fig.tight_layout()
    return fig


def get_apsc_equivalent_focal_length_plot(data: List[Dict]) -> Optional[Figure]:
    # Calculate APS-C equivalent: 35mm_eq / 1.5
    values = []
    for d in data:
        val_35 = d.get("Focal Length (35mm)")
        if val_35 is not None:
            values.append(val_35 / 1.5)

    if not values:
        return None

    # Round to nearest integer
    values = [int(round(v)) for v in values]

    counter = Counter(values)
    top_items = dict(counter.most_common(25))
    sorted_items = sorted(top_items.items())  # Sort by focal length value
    x_vals = [str(x[0]) for x in sorted_items]
    y_vals = [x[1] for x in sorted_items]

    fig = Figure(figsize=(12, 7), dpi=100)
    ax = fig.add_subplot(111)
    ax.bar(x_vals, y_vals)
    ax.tick_params(axis="x", rotation=45)
    ax.set_title("Top 25 Most Used Equivalent Focal Lengths (APS-C)")
    ax.set_xlabel("Equivalent Focal Length (mm)")
    ax.set_ylabel("Count")
    fig.tight_layout()
    return fig


def get_equivalent_focal_length_plot(data: List[Dict]) -> Optional[Figure]:
    values = [d['Focal Length (35mm)'] for d in data if d.get('Focal Length (35mm)') is not None]
    if not values:
        return None

    # Round to nearest integer for cleaner plotting
    values = [int(round(v)) for v in values]

    counter = Counter(values)
    top_items = dict(counter.most_common(25))
    sorted_items = sorted(top_items.items()) # Sort by focal length value
    x_vals = [str(x[0]) for x in sorted_items]
    y_vals = [x[1] for x in sorted_items]

    fig = Figure(figsize=(12, 7), dpi=100)
    ax = fig.add_subplot(111)
    ax.bar(x_vals, y_vals)
    ax.tick_params(axis='x', rotation=45)
    ax.set_title('Top 25 Most Used Equivalent Focal Lengths (35mm)')
    ax.set_xlabel('Equivalent Focal Length (mm)')
    ax.set_ylabel('Count')
    fig.tight_layout()
    return fig


def get_apsc_equivalent_focal_length_plot(data: List[Dict]) -> Optional[Figure]:
    # Calculate APS-C equivalent: 35mm_eq / 1.5
    values = []
    for d in data:
        val_35 = d.get('Focal Length (35mm)')
        if val_35 is not None:
             values.append(val_35 / 1.5)

    if not values:
        return None

    # Round to nearest integer
    values = [int(round(v)) for v in values]

    counter = Counter(values)
    top_items = dict(counter.most_common(25))
    sorted_items = sorted(top_items.items()) # Sort by focal length value
    x_vals = [str(x[0]) for x in sorted_items]
    y_vals = [x[1] for x in sorted_items]

    fig = Figure(figsize=(12, 7), dpi=100)
    ax = fig.add_subplot(111)
    ax.bar(x_vals, y_vals)
    ax.tick_params(axis='x', rotation=45)
    ax.set_title('Top 25 Most Used Equivalent Focal Lengths (APS-C)')
    ax.set_xlabel('Equivalent Focal Length (mm)')
    ax.set_ylabel('Count')
    fig.tight_layout()
    return fig


def get_lens_plot(data: List[Dict]) -> Optional[Figure]:
    values = [d["Lens"] for d in data if d.get("Lens") is not None]
    if not values:
        return None

    counter = Counter(values)
    # Sort by count ascending for horizontal bar chart
    sorted_items = sorted(counter.items(), key=lambda x: x[1])
    labels = [x[0] for x in sorted_items]
    counts = [x[1] for x in sorted_items]

    fig = Figure(figsize=(12, max(6, len(sorted_items) * 0.4)), dpi=100)
    ax = fig.add_subplot(111)
    ax.barh(labels, counts)
    ax.set_title("Lens Usage")
    ax.set_xlabel("Number of Photos")
    ax.set_ylabel("Lens Model")
    fig.tight_layout()
    return fig


def get_combination_plot(data: List[Dict]) -> Optional[Figure]:
    values = []
    for d in data:
        if d.get("Aperture") is not None and d.get("Focal Length") is not None:
            values.append((d["Aperture"], d["Focal Length"]))

    if not values:
        return None

    counter = Counter(values)
    top_items = counter.most_common(25)
    # Sort by count ascending for horizontal bar chart
    top_items.sort(key=lambda x: x[1])

    labels = [f"f/{ap} @ {int(fl)}mm" for (ap, fl), _ in top_items]
    counts = [c for _, c in top_items]

    fig = Figure(figsize=(12, max(8, len(top_items) * 0.4)), dpi=100)
    ax = fig.add_subplot(111)
    ax.barh(labels, counts)
    ax.set_title("Top 25 Most Used Aperture & Focal Length Combinations")
    ax.set_xlabel("Number of Photos")
    ax.set_ylabel("Combination (Aperture @ Focal Length)")
    fig.tight_layout()
    return fig


def create_plots(data: List[Dict], output_dir: Path, show_plots: bool = False):
    """Generates and saves plots for the analyzed data, optionally opening them."""
    print(f"\nGenerating plots in '{output_dir}'...")
    output_dir.mkdir(parents=True, exist_ok=True)

    plt.style.use("seaborn-v0_8-whitegrid")

    # Shutter Speed
    fig = get_shutter_speed_plot(data)
    if fig:
        fig.savefig(output_dir / "shutter_speed_distribution.png")
    else:
        print("Skipping Shutter Speed plot: No data available.")

    # Aperture
    fig = get_aperture_plot(data)
    if fig:
        aperture_path = output_dir / "aperture_distribution.png"
        fig.savefig(aperture_path)
        if show_plots:
            _open_file_for_user(aperture_path)
    else:
        print("Skipping Aperture plot: No data available.")

    # ISO
    fig = get_iso_plot(data)
    if fig:
        fig.savefig(output_dir / "iso_distribution.png")
    else:
        print("Skipping ISO plot: No data available.")

    # Focal Length
    fig = get_focal_length_plot(data)
    if fig:
        focal_length_path = output_dir / "focal_length_distribution.png"
        fig.savefig(focal_length_path)
        if show_plots:
            _open_file_for_user(focal_length_path)
    else:
        print("Skipping Focal Length plot: No data available.")

    # Equivalent Focal Length (35mm)
    fig = get_equivalent_focal_length_plot(data)
    if fig:
        eq_fl_path = output_dir / "equivalent_focal_length_35mm_distribution.png"
        fig.savefig(eq_fl_path)
        if show_plots:
            _open_file_for_user(eq_fl_path)
    else:
        print("Skipping Equivalent Focal Length (35mm) plot: No data available.")

    # Equivalent Focal Length (APS-C)
    fig = get_apsc_equivalent_focal_length_plot(data)
    if fig:
        apsc_fl_path = output_dir / "equivalent_focal_length_apsc_distribution.png"
        fig.savefig(apsc_fl_path)
        if show_plots:
            _open_file_for_user(apsc_fl_path)
    else:
        print("Skipping Equivalent Focal Length (APS-C) plot: No data available.")

    # Lens
    fig = get_lens_plot(data)
    if fig:
        lens_path = output_dir / "lens_usage.png"
        fig.savefig(lens_path)
        if show_plots:
            _open_file_for_user(lens_path)
    else:
        print("Skipping Lens plot: No data available.")

    # Aperture & Focal Length Combinations
    fig = get_combination_plot(data)
    if fig:
        combo_path = output_dir / "aperture_focal_length_combinations.png"
        fig.savefig(combo_path)
        if show_plots:
            _open_file_for_user(combo_path)
    else:
        print("Skipping Aperture & Focal Length combination plot: No data available.")

    print("Plots saved successfully.")
