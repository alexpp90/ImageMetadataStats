"""
Image Metadata Analyzer

This script reads metainformation of image files from a given root folder,
including all subfolders. It provides statistics and generates graphs for:
- Shutter Speed
- Aperture (F-Number)
- ISO
- Focal Length
- Lens Model

Dependencies:
pip install Pillow pandas matplotlib tqdm exifread

Usage:
python script.py /path/to/your/photos
python script.py /path/to/your/photos --output my-photo-stats
"""
import argparse
import os
import subprocess
import sys
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image, ExifTags
from tqdm import tqdm

# Suppress specific warnings from Pillow about potentially corrupt EXIF data
# which it often handles gracefully anyway.
warnings.filterwarnings("ignore", "(Possibly )?corrupt EXIF data", UserWarning)


def get_exif_data(image_path: Path, debug: bool = False) -> dict | None:
    """
    Extracts relevant EXIF data from a single image file.
    Tries to use the `exifread` library for raw files, falling back to Pillow.

    Args:
        image_path: Path object for the image file.
        debug: If True, prints detailed debug information for failed files.

    Returns:
        A dictionary containing the desired metadata, or None if data is
        missing or corrupt.
    """
    # For raw files, Pillow is often unreliable. Try exifread first.
    raw_extensions = {'.arw', '.nef', '.cr2', '.dng', '.raw'}
    if image_path.suffix.lower() in raw_extensions:
        try:
            import exifread

            with open(image_path, 'rb') as f:
                tags = exifread.process_file(f, details=False)

            if tags:
                # Helper to extract and convert values from exifread tags
                def get_tag_float(tag_name):
                    tag = tags.get(tag_name)
                    if not tag or not tag.values:
                        return None
                    val = tag.values[0]
                    if hasattr(val, 'num'):  # It's a Ratio object
                        if val.den == 0:
                            return None
                        return float(val.num) / float(val.den)
                    try:
                        return float(val)
                    except (TypeError, ValueError):
                        return None

                shutter_speed = get_tag_float('EXIF ExposureTime')
                aperture = get_tag_float('EXIF FNumber')
                focal_length = get_tag_float('EXIF FocalLength')
                iso_tag = tags.get('EXIF ISOSpeedRatings')
                iso = iso_tag.values[0] if iso_tag and iso_tag.values else None

                lens_model_tag = tags.get('EXIF LensModel') or tags.get('MakerNote LensModel')
                lens_model = str(lens_model_tag.values).strip() if lens_model_tag else "Unknown"

                if all(v is not None for v in [shutter_speed, aperture, focal_length, iso]):
                    if debug:
                        print(f"Successfully processed {image_path.name} with exifread.")
                    return {
                        'Shutter Speed': shutter_speed,
                        'Aperture': aperture,
                        'Focal Length': focal_length,
                        'ISO': iso,
                        'Lens': lens_model,
                    }
        except ImportError:
            if debug:
                print("\nWarning: `exifread` library not found. "
                      "Falling back to Pillow for raw files. "
                      "For better raw file support, `pip install exifread`")
        except Exception as e:
            if debug:
                print(f"\nexifread failed on {image_path.name}: {e}")

    # Fallback to Pillow for all file types, or as primary for JPG/TIF
    try:
        img = Image.open(image_path)
        # Use the recommended getexif() method which returns an Exif object
        try:
            exif_data_raw = img.getexif()
        except AttributeError:
            # Fallback for older Pillow versions that use the private method
            exif_data_raw = img._getexif()

        if not exif_data_raw:
            if debug:
                # This debug message will now primarily appear for non-raw files
                # or as a fallback.
                print(f"\n--- Debugging failed extraction for: {image_path.name} ---")
                print("  Reason: No EXIF data found in the image file.")
                print("----------------------------------------------------")
            return None

        # The main camera settings are often in a nested Exif IFD.
        # We'll try to get it and merge it with the top-level IFD.
        # Tag 34665 (0x8769) is for the Exif IFD pointer.
        try:
            exif_ifd = exif_data_raw.get_ifd(34665)
        except KeyError:
            exif_ifd = {}

        # Create a more readable dictionary from the raw EXIF data
        # The .get(k, k) handles unknown tags gracefully.
        exif_data = {ExifTags.TAGS.get(k, k): v for k, v in exif_data_raw.items()}
        exif_ifd_data = {ExifTags.TAGS.get(k, k): v for k, v in exif_ifd.items()}
        # Merge them, with the more specific Exif IFD taking precedence
        exif_data.update(exif_ifd_data)

        if not exif_data:
            if debug:
                print(f"\n--- Debugging (Pillow) failed extraction for: {image_path.name} ---")
                print("  Reason: EXIF data was found, but it contains no known tags after merging.")
                print("----------------------------------------------------")
            return None

        # Helper to robustly convert EXIF values to a float
        def get_float(value):
            if value is None:
                return None
            # Handle PIL's IFDRational type which has numerator/denominator
            if hasattr(value, 'numerator') and hasattr(value, 'denominator'):
                if value.denominator == 0:
                    return None
                return float(value.numerator) / float(value.denominator)
            # Handle tuple type for some rational values, e.g. (28, 10) for 2.8
            if isinstance(value, tuple) and len(value) == 2:
                num, den = value
                if den == 0:
                    return None
                return float(num) / float(den)
            # Handle byte strings which might be null-terminated
            if isinstance(value, bytes):
                try:
                    return float(value.strip(b'\x00').decode('utf-8', errors='ignore'))
                except (ValueError, UnicodeDecodeError):
                    return None
            # Handle simple numeric types
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        shutter_speed_raw = exif_data.get('ExposureTime')
        aperture_raw = exif_data.get('FNumber')
        focal_length_raw = exif_data.get('FocalLength')
        # ISO can sometimes be a tuple (e.g., (100, 0)), take the first element
        iso_raw = exif_data.get('ISOSpeedRatings')
        lens_model_raw = exif_data.get('LensModel')

        shutter_speed = get_float(shutter_speed_raw)
        aperture = get_float(aperture_raw)
        focal_length = get_float(focal_length_raw)
        iso = get_float(iso_raw[0] if isinstance(iso_raw, tuple) else iso_raw)
        lens_model = lens_model_raw or "Unknown"

        # We will accept the file if at least one piece of essential metadata is found.
        if all(v is None for v in [shutter_speed, aperture, focal_length, iso, lens_model_raw]):
            if debug:
                print(f"\n--- Debugging (Pillow) failed extraction for: {image_path.name} ---")
                print(f"  Raw Shutter Speed: {shutter_speed_raw!r} (Type: {type(shutter_speed_raw).__name__}) -> Parsed: {shutter_speed}")
                print(f"  Raw Aperture:      {aperture_raw!r} (Type: {type(aperture_raw).__name__}) -> Parsed: {aperture}")
                print(f"  Raw Focal Length:  {focal_length_raw!r} (Type: {type(focal_length_raw).__name__}) -> Parsed: {focal_length}")
                print(f"  Raw ISO:           {iso_raw!r} (Type: {type(iso_raw).__name__}) -> Parsed: {iso}")
                print(f"  Lens Model:        {lens_model!r}")
                print("  Reason: None of the essential metadata fields could be found or parsed.")
                # Add this new part to show all available keys
                if exif_data:
                    import textwrap
                    # Show all keys from the merged dictionary
                    available_keys = ", ".join(sorted([str(k) for k in exif_data.keys()]))
                    print("\n  Available EXIF keys found in this file (merged):")
                    print(textwrap.fill(available_keys, width=80, initial_indent="    ", subsequent_indent="    "))
                else:
                    # This case is already handled above, but for safety.
                    print("\n  No known EXIF keys were found in this file.")
                print("----------------------------------------------------")
            return None

        return {
            'Shutter Speed': shutter_speed,
            'Aperture': aperture,
            'Focal Length': focal_length,
            'ISO': iso,
            'Lens': lens_model,
        }
    except Exception as e:
        # Catch all other exceptions from opening/reading files (e.g., not an image, corrupt file)
        if debug:
            print(f"\n--- Debugging (Pillow) failed extraction for: {image_path.name} ---")
            print(f"  An unexpected error occurred: {e}")
            print("----------------------------------------------------")
        return None


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


def analyze_data(df: pd.DataFrame):
    """Prints a formatted statistical summary of the metadata."""
    print("\n--- Image Metadata Analysis ---")
    print(f"Total images with EXIF data analyzed: {len(df)}")

    print("\n--- Basic Statistics ---")
    # Only describe numerical columns
    print(df[['Shutter Speed', 'Aperture', 'Focal Length', 'ISO']].describe())

    print("\n--- Most Common Settings ---")
    print("\nTop 5 Lenses:")
    print(df['Lens'].value_counts().head(5).to_string())

    print("\n\nTop 15 Focal Lengths (mm):")
    print(df['Focal Length'].value_counts().head(15).to_string())

    print("\n\nTop 25 Aperture & Focal Length Combinations:")
    if 'Aperture' in df and 'Focal Length' in df:
        combo_counts = df.dropna(
            subset=['Aperture', 'Focal Length']
        ).groupby(['Aperture', 'Focal Length']).size().nlargest(25)
        print(combo_counts.to_string())

    print("\n\nTop 5 Apertures (f-stop):")
    print(df['Aperture'].value_counts().head(5).to_string())

    print("\n\nTop 5 ISOs:")
    print(df['ISO'].value_counts().head(5).to_string())
    print("\n----------------------------")

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


def main():
    """Main function to orchestrate the script execution."""
    parser = argparse.ArgumentParser(description="Analyze image metadata from a folder.")
    parser.add_argument("root_folder", type=str, help="The root folder to search for images.")
    parser.add_argument("-o", "--output", type=str, default="analysis_results", help="The folder to save graphs.")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable detailed debug output for files that could not be processed.",
    )
    parser.add_argument(
        "--show-plots",
        action="store_true",
        help="Automatically open the aperture, focal length, lens, and combination plots after creation.",
    )
    args = parser.parse_args()

    root_path = Path(args.root_folder)
    output_path = Path(args.output)

    if not root_path.is_dir():
        print(f"Error: Folder not found at '{root_path}'")
        return

    image_extensions = {'.jpg', '.jpeg', '.tif', '.tiff', '.nef', '.cr2', '.arw', '.dng', '.raw'}
    print(f"Scanning for images in '{root_path}'...")

    image_files = [f for f in root_path.rglob('*') if f.suffix.lower() in image_extensions]

    if not image_files:
        print("No supported image files found.")
        return

    print(f"Found {len(image_files)} image files. Extracting metadata...")

    all_metadata = [
        data for f in tqdm(image_files, desc="Processing images")
        if (data := get_exif_data(f, debug=args.debug))
    ]

    if not all_metadata:
        print("Could not extract any valid EXIF metadata from the found images.")
        return

    df = pd.DataFrame(all_metadata)

    if df.empty:
        print("Could not extract any valid EXIF metadata from the found images.")
        return

    # Clean data for better grouping in plots
    # Convert columns to numeric, coercing errors, then round/cast.
    # This prevents TypeErrors if some EXIF values are non-numeric.
    df['Shutter Speed'] = pd.to_numeric(df['Shutter Speed'], errors='coerce')
    df['Aperture'] = pd.to_numeric(df['Aperture'], errors='coerce').round(1)
    # Use nullable integer type 'Int64' to handle potential NaNs after coercion.
    # This is a robust way to convert floats (with potential NaNs) to nullable
    # integers, avoiding TypeErrors from direct casting.
    focal_length_series = pd.to_numeric(df['Focal Length'], errors='coerce')
    not_na_mask = focal_length_series.notna()
    integer_series = pd.Series(pd.NA, index=df.index, dtype='Int64')
    integer_series[not_na_mask] = focal_length_series[not_na_mask].round().astype(int)
    df['Focal Length'] = integer_series

    df['ISO'] = pd.to_numeric(df['ISO'], errors='coerce').astype('Int64')

    analyze_data(df)
    create_plots(df, output_path, show_plots=args.show_plots)


if __name__ == "__main__":
    main()
