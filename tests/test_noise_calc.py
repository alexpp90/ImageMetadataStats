import numpy as np
import cv2
from image_metadata_analyzer.sharpness import calculate_noise


def test_noise_calc(tmp_path):
    img_path = tmp_path / "test.jpg"
    img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    cv2.imwrite(str(img_path), img)

    score = calculate_noise(img_path)
    print(score)
    assert isinstance(score, float)
    assert score > 0
