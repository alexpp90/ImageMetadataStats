from image_metadata_analyzer.formatting import format_score, format_meta


def test_format_score():
    assert format_score("N/A") == "N/A"
    assert format_score(None) == "N/A"
    assert format_score(3.14159, 2) == "3.14"
    assert format_score(5) == "5"
    assert format_score("Invalid") == "Invalid"


def test_format_meta():
    assert format_meta("N/A") == "N/A"
    assert format_meta(None) == "N/A"
    assert format_meta(0.5, "s") == "1/2s"
    assert format_meta(0.333, "s") == "1/3s"
    assert format_meta(1.0, "s") == "1.0s"
    assert format_meta(0.0, "s") == "0.0s"
    assert format_meta(2.5, "s") == "2.5s"
    assert format_meta(50.0, "mm") == "50mm"
    assert format_meta(50.4, "mm") == "50mm"
    assert format_meta(2.8, "f/") == "f/2.8"
    assert format_meta(100.0) == "100.0"
    assert format_meta("Hello") == "Hello"
    assert format_meta((1, 2)) == "(1, 2)"
