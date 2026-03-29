import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import time
from image_metadata_analyzer.controllers import ImageCacheManager
import image_metadata_analyzer.controllers as ctrl


@pytest.fixture
def mock_load_image():
    with patch.object(ctrl, "load_image_preview") as mock:
        mock.return_value = MagicMock()
        yield mock


def test_image_cache_manager_queues(mock_load_image):
    manager = ImageCacheManager(preview_cache_limit=2, full_res_cache_limit=2)
    p1 = Path("/tmp/1.jpg")
    p2 = Path("/tmp/2.jpg")

    manager.queue_preview(p1)
    manager.queue_full_res(p2)

    # give threads a moment to process
    for _ in range(50):
        if p1 in manager.preview_cache and p2 in manager.full_res_cache:
            break
        time.sleep(0.05)

    assert p1 in manager.preview_cache
    assert p2 in manager.full_res_cache
    assert manager.get_preview(p1) is not None
    assert manager.get_full_res(p2) is not None


def test_image_cache_manager_limits(mock_load_image):
    manager = ImageCacheManager(preview_cache_limit=2)
    paths = [Path(f"/tmp/{i}.jpg") for i in range(5)]

    for p in paths:
        manager.queue_preview(p)

    for _ in range(50):
        if not manager.preview_queue.empty():
            time.sleep(0.05)
        else:
            time.sleep(0.05) # one more for processing
            break

    # the cache limit is 2
    assert len(manager.preview_cache) <= 2


def test_image_cache_manager_clear(mock_load_image):
    manager = ImageCacheManager()
    p1 = Path("/tmp/1.jpg")
    manager.queue_preview(p1)
    for _ in range(50):
        if p1 in manager.preview_cache:
            break
        time.sleep(0.05)

    assert p1 in manager.preview_cache
    manager.clear()
    assert len(manager.preview_cache) == 0
