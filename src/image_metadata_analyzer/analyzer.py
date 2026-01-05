import pandas as pd


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
