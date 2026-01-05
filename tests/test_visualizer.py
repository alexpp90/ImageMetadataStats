import pandas as pd
from image_metadata_analyzer.visualizer import create_plots


def test_create_plots(tmp_path):
    data = {
        'Shutter Speed': [0.01, 0.02, 0.01],
        'Aperture': [2.8, 5.6, 2.8],
        'Focal Length': [50, 85, 50],
        'ISO': [100, 200, 100],
        'Lens': ['Lens A', 'Lens B', 'Lens A']
    }
    df = pd.DataFrame(data)

    output_dir = tmp_path / "plots"
    create_plots(df, output_dir, show_plots=False)

    assert output_dir.exists()
    assert (output_dir / 'shutter_speed_distribution.png').exists()
    assert (output_dir / 'aperture_distribution.png').exists()
    assert (output_dir / 'iso_distribution.png').exists()
    assert (output_dir / 'focal_length_distribution.png').exists()
    assert (output_dir / 'lens_usage.png').exists()
    assert (output_dir / 'aperture_focal_length_combinations.png').exists()
