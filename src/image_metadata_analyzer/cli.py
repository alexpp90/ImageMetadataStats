import argparse
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from image_metadata_analyzer.reader import get_exif_data
from image_metadata_analyzer.analyzer import analyze_data
from image_metadata_analyzer.visualizer import create_plots


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
