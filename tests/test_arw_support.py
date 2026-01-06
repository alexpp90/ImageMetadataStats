from pathlib import Path
from image_metadata_analyzer.reader import get_exif_data

def test_arw_extraction():
    """
    Verifies that metadata can be correctly extracted from a Sony ARW file.
    Uses the sample file downloaded to tests/data/sony_a6700_sample.arw.
    """
    arw_path = Path("tests/data/sony_a6700_sample.arw")

    if not arw_path.exists():
        # Skip test if file is not present (e.g. in CI environments without internet)
        import pytest
        pytest.skip("ARW sample file not found in tests/data")

    data = get_exif_data(arw_path)

    assert data is not None, "Failed to extract metadata from ARW file"
    assert "Shutter Speed" in data
    assert "Aperture" in data
    assert "ISO" in data
    assert "Focal Length" in data
    assert "Lens" in data

    # Verify specific values from the known sample
    # Note: Float comparison might need tolerance, but these seem exact in the reproduction
    assert data["ISO"] == 200
    assert data["Aperture"] == 4.0
    assert data["Focal Length"] == 20.0
