import json
import urllib.error
from unittest.mock import MagicMock, patch
import pytest
from PIL import Image

from photo_selector_toolbox.tools.ollama import (
    OllamaAestheticTool,
)
from photo_selector_toolbox.core.config import save_config



@pytest.fixture
def temp_config_dir(tmp_path):
    """Fixture to mock CONFIG_DIR and CONFIG_FILE to a temporary path."""
    import photo_selector_toolbox.core.config as cfg_mod
    with patch.object(cfg_mod, "CONFIG_DIR", tmp_path), \
         patch.object(cfg_mod, "CONFIG_FILE", tmp_path / "settings.json"):
        yield tmp_path



@pytest.fixture
def dummy_image_file(tmp_path):
    """Create a temporary dummy JPEG image."""
    img_path = tmp_path / "test_photo.jpg"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(img_path, format="JPEG")
    return img_path


@patch("urllib.request.OpenerDirector.open")
def test_ollama_tool_success(mock_open, dummy_image_file, temp_config_dir):
    # Mock Ollama HTTP response payload
    mock_resp_payload = {"response": "[SCORE: 8.5] [ANALYSIS: Great lighting] The photo has nice lighting."}

    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(mock_resp_payload).encode("utf-8")
    mock_response.__enter__.return_value = mock_response
    mock_open.return_value = mock_response

    tool = OllamaAestheticTool()
    score, tag = tool.analyze(dummy_image_file)

    assert score == 8.5
    assert tag == "Great lighting"
    mock_open.assert_called_once()
    # Check that URL used default
    req = mock_open.call_args[0][0]
    assert req.full_url == "http://localhost:11434/api/generate"
    assert req.method == "POST"


@patch("urllib.request.OpenerDirector.open")
def test_ollama_tool_custom_config(mock_open, dummy_image_file, temp_config_dir):
    # Setup custom configuration
    custom_config = {
        "ollama_url": "http://192.168.1.50:11434/",
        "ollama_model": "qwen-vl",
        "ollama_prompt": "Rate the aesthetics of the photo. Score: ",
    }
    save_config(custom_config)

    # Mock response
    mock_resp_payload = {"response": "[SCORE: 9.3] [ANALYSIS: Sharp] Score: 9.3 out of 10"}
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(mock_resp_payload).encode("utf-8")
    mock_response.__enter__.return_value = mock_response
    mock_open.return_value = mock_response

    tool = OllamaAestheticTool()
    score, tag = tool.analyze(dummy_image_file)

    assert score == 9.3
    assert tag == "Sharp"
    req = mock_open.call_args[0][0]
    assert req.full_url == "http://192.168.1.50:11434/api/generate"

    # Assert JSON payload parameters match config
    body = json.loads(req.data.decode("utf-8"))
    assert body["model"] == "qwen-vl"
    assert body["prompt"] == "Rate the aesthetics of the photo. Score: "


@patch("urllib.request.OpenerDirector.open")
def test_ollama_tool_connection_error(mock_open, dummy_image_file, temp_config_dir):
    # Mock connection failure (URLError)
    mock_open.side_effect = urllib.error.URLError("Connection refused")

    tool = OllamaAestheticTool()
    with pytest.raises(RuntimeError) as exc_info:
        tool.analyze(dummy_image_file)

    assert "Ollama server connection error" in str(exc_info.value)


@patch("urllib.request.OpenerDirector.open")
def test_ollama_tool_parsing_error(mock_open, dummy_image_file, temp_config_dir):
    # Mock response with no float scores in text
    mock_resp_payload = {"response": "This is a photo of a sunset, it looks great but I can't give a number."}

    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(mock_resp_payload).encode("utf-8")
    mock_response.__enter__.return_value = mock_response
    mock_open.return_value = mock_response

    tool = OllamaAestheticTool()
    with pytest.raises(RuntimeError) as exc_info:
        tool.analyze(dummy_image_file)

    assert "Could not parse a numeric score from Ollama output" in str(exc_info.value)



@patch("urllib.request.OpenerDirector.open")
def test_ollama_tool_fallback_analysis(mock_open, dummy_image_file, temp_config_dir):
    # Mock response with SCORE but no ANALYSIS tag
    mock_resp_payload = {"response": "The aesthetic quality score of this photo is 8.5."}

    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(mock_resp_payload).encode("utf-8")
    mock_response.__enter__.return_value = mock_response
    mock_open.return_value = mock_response

    tool = OllamaAestheticTool()
    score, tag = tool.analyze(dummy_image_file)

    assert score == 8.5
    assert tag == "N/A"





@pytest.mark.parametrize("malicious_url,expected_error", [
    ("http://0.0.0.0:11434/", "SSRF Protection: Cloud metadata IPs are not allowed."),
    ("http://[::ffff:0.0.0.0]:11434/", "SSRF Protection: Cloud metadata IPs are not allowed."),
    ("http://169.254.169.254:11434/", "SSRF Protection: Cloud metadata IPs are not allowed."),
    ("http://[::ffff:169.254.169.254]:11434/", "SSRF Protection: Cloud metadata IPs are not allowed.")
])
def test_ollama_tool_ssrf_protection(dummy_image_file, temp_config_dir, malicious_url, expected_error):
    custom_config = {
        "ollama_url": malicious_url,
    }
    save_config(custom_config)

    tool = OllamaAestheticTool()
    with pytest.raises(RuntimeError) as exc_info:
        tool.analyze(dummy_image_file)

    assert expected_error in str(exc_info.value)
