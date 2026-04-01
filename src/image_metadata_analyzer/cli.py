import argparse
import concurrent.futures
import os
from pathlib import Path

from tqdm import tqdm

from image_metadata_analyzer.reader import get_exif_data, SUPPORTED_EXTENSIONS
from image_metadata_analyzer.analyzer import analyze_data
from image_metadata_analyzer.visualizer import create_plots


def main():
    """Main function to orchestrate the script execution."""
    parser = argparse.ArgumentParser(
        description="Analyze image metadata from a folder."
    )
    parser.add_argument(
        "root_folder", type=str, help="The root folder to search for images."
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="analysis_results",
        help="The folder to save graphs.",
    )
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

    print(f"Scanning for images in '{root_path}'...")

    image_files = [
        f for f in root_path.rglob("*") if f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not image_files:
        print("No supported image files found.")
        return

    print(f"Found {len(image_files)} image files. Extracting metadata...")

    # Parallelize EXIF extraction to speed up I/O-bound processing.
    # We use a ThreadPoolExecutor with a worker count optimized for I/O operations.
    all_metadata = []
    max_workers = min(32, (os.cpu_count() or 1) + 4)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # We use executor.map with a lambda to preserve the original image order and update tqdm.
        # However, to easily skip None results and keep tqdm responsive, we'll use submit/as_completed.
        futures = {
            executor.submit(get_exif_data, f, debug=args.debug): f for f in image_files
        }

        with tqdm(total=len(image_files), desc="Processing images") as pbar:
            for future in concurrent.futures.as_completed(futures):
                data = future.result()
                if data:
                    all_metadata.append(data)
                pbar.update(1)

    if not all_metadata:
        print("Could not extract any valid EXIF metadata from the found images.")
        return

    analyze_data(all_metadata)
    create_plots(all_metadata, output_path, show_plots=args.show_plots)


if __name__ == "__main__":
    main()
