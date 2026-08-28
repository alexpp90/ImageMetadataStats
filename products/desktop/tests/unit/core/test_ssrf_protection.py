import pytest
from unittest.mock import patch
from photo_selector_toolbox.tools.ollama import OllamaAestheticTool
from PIL import Image

@pytest.fixture
def dummy_image_file(tmp_path):
    img_path = tmp_path / "test_photo.jpg"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(img_path, format="JPEG")
    return img_path

@pytest.fixture
def temp_config_dir(tmp_path):
    from photo_selector_toolbox.core import config


    import photo_selector_toolbox.core.cache as cache

    orig_dir = config.CONFIG_DIR
    orig_file = config.CONFIG_FILE

    config.CONFIG_DIR = tmp_path
    config.CONFIG_FILE = tmp_path / "settings.json"
    cache._DEFAULT_DB_PATH = tmp_path / "test_cache.db"

    yield tmp_path

    config.CONFIG_DIR = orig_dir
    config.CONFIG_FILE = orig_file
    cache._DEFAULT_DB_PATH = None

@patch("urllib.request.OpenerDirector.open")
def test_ollama_tool_blocks_metadata_ip(mock_open, dummy_image_file, temp_config_dir):
    from photo_selector_toolbox.core.config import save_config
    save_config({
        "ollama_url": "http://169.254.169.254/latest/meta-data/",
        "ollama_model": "test",
        "ollama_prompt": "test"
    })
    tool = OllamaAestheticTool()
    with pytest.raises(RuntimeError, match="SSRF Protection: Cloud metadata IPs are not allowed."):
        tool.analyze(dummy_image_file)

@patch("urllib.request.OpenerDirector.open")
@patch("socket.getaddrinfo")
def test_ollama_tool_blocks_metadata_ip_hex_bypass(mock_getaddrinfo, mock_open, dummy_image_file, temp_config_dir):
    import socket
    # Simulate a successful resolution of the hex IP to the metadata IP, overriding OS-specific behaviors
    mock_getaddrinfo.return_value = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('169.254.169.254', 0))
    ]

    from photo_selector_toolbox.core.config import save_config
    save_config({
        "ollama_url": "http://0xa9fea9fe/latest/meta-data/",
        "ollama_model": "test",
        "ollama_prompt": "test"
    })
    tool = OllamaAestheticTool()
    with pytest.raises(RuntimeError, match="SSRF Protection: Cloud metadata IPs are not allowed."):
        tool.analyze(dummy_image_file)

@patch("urllib.request.OpenerDirector.open")
def test_ollama_tool_blocks_metadata_ipv6_literal(mock_open, dummy_image_file, temp_config_dir):
    from photo_selector_toolbox.core.config import save_config
    save_config({
        "ollama_url": "http://[::ffff:169.254.169.254]/latest/meta-data/",
        "ollama_model": "test",
        "ollama_prompt": "test"
    })
    tool = OllamaAestheticTool()
    with pytest.raises(RuntimeError, match="SSRF Protection: Cloud metadata IPs are not allowed."):
        tool.analyze(dummy_image_file)

@patch("urllib.request.OpenerDirector.open")
def test_ollama_tool_blocks_unspecified_ipv6_literal(mock_open, dummy_image_file, temp_config_dir):
    import json
    with open(temp_config_dir / "settings.json", "w") as f:
        json.dump({
            "ollama_url": "http://[::ffff:0.0.0.0]/latest/meta-data/",
            "ollama_model": "test",
            "ollama_prompt": "test"
        }, f)
    tool = OllamaAestheticTool()
    with pytest.raises(RuntimeError, match="SSRF Protection: Cloud metadata IPs are not allowed."):
        tool.analyze(dummy_image_file)
