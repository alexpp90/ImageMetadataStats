import statistics
from collections import Counter

from image_metadata_analyzer.utils import aggregate_focal_lengths


def analyze_data(data: list[dict]):
    """Prints a formatted statistical summary of the metadata."""
    print("\n--- Image Metadata Analysis ---")
    print(f"Total images with EXIF data analyzed: {len(data)}")

    if not data:
        print("No data to analyze.")
        return

    # Calculate fallback statistics
    fallback_count = sum(1 for d in data if d.get("Is Fallback"))
    fallback_percent = (fallback_count / len(data)) * 100
    if fallback_count > 0:
        print(
            f"Images using fallback focal length (original): {fallback_count} ({fallback_percent:.1f}%)"
        )
    else:
        print("All images had valid 35mm equivalent focal length metadata.")

    print("\n--- Basic Statistics ---")

    # Helper to extract values
    def get_values(key):
        return [d[key] for d in data if d.get(key) is not None]

    for key in ["Shutter Speed", "Aperture", "Focal Length", "ISO"]:
        values = get_values(key)
        if values:
            print(f"\n{key}:")
            print(f"  Count: {len(values)}")
            print(f"  Mean:  {statistics.mean(values):.2f}")
            if len(values) > 1:
                print(f"  Std:   {statistics.stdev(values):.2f}")
            print(f"  Min:   {min(values)}")
            print(f"  Max:   {max(values)}")
        else:
            print(f"\n{key}: No data")

    print("\n--- Most Common Settings ---")

    print("\nTop 5 Lenses:")
    lenses = get_values("Lens")
    for name, count in Counter(lenses).most_common(5):
        print(f"  {name}: {count}")

    print("\n\nTop Focal Lengths (mm):")
    focal_lengths = get_values("Focal Length")
    # Use aggregation logic
    aggregated_fls = aggregate_focal_lengths(focal_lengths)
    # Sort by count descending
    aggregated_fls.sort(key=lambda x: x[1], reverse=True)
    # Display top 15 of the aggregated buckets
    for label, count, _ in aggregated_fls[:15]:
        print(f"  {label}: {count}")

    print("\n\nTop 15 Equivalent Focal Lengths (35mm):")
    focal_lengths_35 = get_values("Focal Length (35mm)")
    # Round to nearest integer for cleaner display
    focal_lengths_35_rounded = [int(round(fl)) for fl in focal_lengths_35]
    for fl, count in Counter(focal_lengths_35_rounded).most_common(15):
        print(f"  {fl}mm: {count}")

    print("\n\nTop 15 Equivalent Focal Lengths (APS-C):")
    # APS-C is 35mm / 1.5
    focal_lengths_apsc = [int(round(fl / 1.5)) for fl in focal_lengths_35]
    for fl, count in Counter(focal_lengths_apsc).most_common(15):
        print(f"  {fl}mm: {count}")

    print("\n\nTop 25 Aperture & Focal Length Combinations:")
    combinations = []
    for d in data:
        if d.get("Aperture") is not None and d.get("Focal Length") is not None:
            combinations.append((d["Aperture"], d["Focal Length"]))

    for (ap, fl), count in Counter(combinations).most_common(25):
        print(f"  f/{ap} @ {fl}mm: {count}")

    print("\n\nTop 5 Apertures (f-stop):")
    apertures = get_values("Aperture")
    for ap, count in Counter(apertures).most_common(5):
        print(f"  {ap}: {count}")

    print("\n\nTop 5 ISOs:")
    isos = get_values("ISO")
    for iso, count in Counter(isos).most_common(5):
        print(f"  {iso}: {count}")
    print("\n----------------------------")
