import pandas as pd
from image_metadata_analyzer.analyzer import analyze_data


def test_analyze_data_runs(capsys):
    data = {
        'Shutter Speed': [0.01, 0.02, 0.01],
        'Aperture': [2.8, 5.6, 2.8],
        'Focal Length': [50, 85, 50],
        'ISO': [100, 200, 100],
        'Lens': ['Lens A', 'Lens B', 'Lens A']
    }
    df = pd.DataFrame(data)

    # Just check if it runs without error and prints something
    analyze_data(df)
    captured = capsys.readouterr()
    assert "Image Metadata Analysis" in captured.out
    assert "Top 5 Lenses" in captured.out
