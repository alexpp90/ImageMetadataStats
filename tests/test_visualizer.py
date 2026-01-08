from image_metadata_analyzer.visualizer import (get_aperture_plot,
                                                get_combination_plot,
                                                get_focal_length_plot,
                                                get_iso_plot, get_lens_plot,
                                                get_shutter_speed_plot)


def test_get_shutter_speed_plot():
    data = [{"Shutter Speed": 0.01}, {"Shutter Speed": 0.02}, {"Shutter Speed": 0.01}]
    fig = get_shutter_speed_plot(data)
    assert fig is not None


def test_get_shutter_speed_plot_empty():
    data: list = []
    fig = get_shutter_speed_plot(data)
    assert fig is None


def test_get_aperture_plot():
    data = [{"Aperture": 2.8}, {"Aperture": 4.0}]
    fig = get_aperture_plot(data)
    assert fig is not None


def test_get_iso_plot():
    data = [{"ISO": 100}, {"ISO": 200}]
    fig = get_iso_plot(data)
    assert fig is not None


def test_get_focal_length_plot():
    data = [{"Focal Length": 50}, {"Focal Length": 85}]
    fig = get_focal_length_plot(data)
    assert fig is not None


def test_get_lens_plot():
    data = [{"Lens": "Lens A"}, {"Lens": "Lens B"}]
    fig = get_lens_plot(data)
    assert fig is not None


def test_get_combination_plot():
    data = [{"Aperture": 2.8, "Focal Length": 50}]
    fig = get_combination_plot(data)
    assert fig is not None
