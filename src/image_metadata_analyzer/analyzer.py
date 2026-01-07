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
