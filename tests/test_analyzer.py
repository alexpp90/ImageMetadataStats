
def test_analyzer_no_data(capsys):
    from image_metadata_analyzer.analyzer import analyze_data
    analyze_data([])
    captured = capsys.readouterr()
    assert "No data to analyze" in captured.out

def test_analyzer_basic_stats(capsys):
    from image_metadata_analyzer.analyzer import analyze_data
    data = [
        {'Shutter Speed': 0.01, 'Aperture': 2.8, 'Focal Length': 50, 'ISO': 100, 'Lens': 'Lens A'},
        {'Shutter Speed': 0.02, 'Aperture': 4.0, 'Focal Length': 50, 'ISO': 200, 'Lens': 'Lens A'},
        {'Shutter Speed': 0.01, 'Aperture': 2.8, 'Focal Length': 85, 'ISO': 100, 'Lens': 'Lens B'},
    ]
    analyze_data(data)
    captured = capsys.readouterr()
    assert "Total images with EXIF data analyzed: 3" in captured.out
    assert "Top 5 Lenses:" in captured.out
    assert "Lens A: 2" in captured.out
    assert "Lens B: 1" in captured.out
    assert "Top 5 ISOs:" in captured.out
    assert "100: 2" in captured.out
    assert "200: 1" in captured.out
    assert "f/2.8 @ 50mm: 1" in captured.out
