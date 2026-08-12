import base64
import json
import logging
import re
import urllib.request
from urllib.error import URLError
import io
import threading
from pathlib import Path
from typing import Any, Tuple


from photo_selector_toolbox.tools.registry import AnalysisTool
from photo_selector_toolbox.core.utils import load_image_preview, NoRedirectHandler

from photo_selector_toolbox.core.config import DEFAULT_CONFIG, load_config

logger = logging.getLogger(__name__)


# NOTE: This tool is intentionally NOT registered under the "aesthetic" name.
# The registered "aesthetic" tool is ``AestheticTool`` in ``aesthetic_tool.py``,
# which delegates here only when the Ollama engine is selected (the optional
# "advanced / deep critique" mode). Keeping this as a plain, directly-callable
# engine avoids two tools claiming the same registry key.
class OllamaAestheticTool(AnalysisTool):
    """
    Optional analysis engine that queries a local Ollama VLM (e.g., LLaVA)
    to estimate the aesthetic score of an image.

    Retained as an advanced, opt-in engine. Prefer the lighter Apple Vision or
    NIMA ONNX engines for routine scoring (see ``aesthetic_tool.py``).
    """

    name = "aesthetic"
    display_name = "AI Aesthetic Evaluation (Ollama)"

    # Class-level lock to serialize local Ollama inference requests
    _lock = threading.Lock()

    def analyze(self, filepath: Path, **kwargs: Any) -> Tuple[float, str]:
        from photo_selector_toolbox.core.config import is_ollama_url_external

        config = load_config()
        ollama_url = config.get("ollama_url", DEFAULT_CONFIG["ollama_url"])
        model_name = config.get("ollama_model", DEFAULT_CONFIG["ollama_model"])
        prompt = config.get("ollama_prompt", DEFAULT_CONFIG["ollama_prompt"])

        # Warn if sending images to a non-localhost server
        if is_ollama_url_external(ollama_url):
            logger.warning(
                f"Ollama URL '{ollama_url}' is not localhost. "
                "Images will be sent over the network. "
                "Set ollama_url to http://localhost:11434 to keep photos on-device."
            )

        # 1. Resize and convert image to base64 JPEG
        try:
            rgb_img = load_image_preview(filepath, max_size=(400, 400))
            if rgb_img is None:
                raise RuntimeError("load_image_preview returned None")

            buffer = io.BytesIO()
            rgb_img.save(buffer, format="JPEG", quality=85)
            img_bytes = buffer.getvalue()
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        except Exception as e:
            raise RuntimeError(f"Failed to process image bytes: {e}")

        # 2. Query Ollama REST API
        if not ollama_url.lower().startswith(('http://', 'https://')):
            raise RuntimeError("Ollama URL must start with http:// or https://")

        from urllib.parse import urlparse
        import socket
        import ipaddress

        hostname = urlparse(ollama_url).hostname or ""
        # Handle IPv6 literals by stripping brackets
        clean_hostname = hostname.strip("[]")

        def is_forbidden_ip(ip_str):
            try:
                ip_obj = ipaddress.ip_address(ip_str)
                if ip_obj.is_link_local:
                    return True
                if ip_obj.is_unspecified:
                    return True
                if getattr(ip_obj, "ipv4_mapped", None):
                    mapped = ip_obj.ipv4_mapped
                    if mapped.is_link_local or mapped.is_unspecified:
                        return True
                return False
            except ValueError:
                return False

        if is_forbidden_ip(clean_hostname):
            raise RuntimeError("SSRF Protection: Cloud metadata IPs are not allowed.")

        try:
            # Attempt to resolve. socket.getaddrinfo handles more formats than gethostbyname
            addr_info = socket.getaddrinfo(clean_hostname, None)
            safe_ips = []
            for res in addr_info:
                ip_str = res[4][0]
                if is_forbidden_ip(ip_str):
                    raise RuntimeError("SSRF Protection: Cloud metadata IPs are not allowed.")
                safe_ips.append(ip_str)
        except socket.gaierror as e:
            raise RuntimeError(f"SSRF Protection: Could not resolve hostname {clean_hostname}: {e}")

        url = f"{ollama_url.rstrip('/')}/api/generate"
        payload = {
            "model": model_name,
            "prompt": prompt,
            "images": [img_b64],
            "stream": False,
        }

        try:
            from photo_selector_toolbox.core.utils import SafeSSRFHTTPHandler, SafeSSRFHTTPSHandler
            opener = urllib.request.build_opener(
                NoRedirectHandler,
                SafeSSRFHTTPHandler(safe_ips),
                SafeSSRFHTTPSHandler(safe_ips),
            )
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            # Serialize requests to avoid overloading local Ollama server
            with self._lock:
                with opener.open(req, timeout=60) as response:
                    res_data = json.loads(response.read().decode("utf-8"))
                    response_text = res_data.get("response", "")
        except URLError as e:
            raise RuntimeError(
                f"Ollama server connection error at {ollama_url}. Is Ollama running? ({e})"
            )
        except Exception as e:
            raise RuntimeError(f"Ollama API request failed: {e}")

        # 3. Parse score and analysis tag from output
        match_score = re.search(r"\[SCORE:\s*(\d+(?:\.\d+)?)\]", response_text, re.IGNORECASE)
        if match_score:
            score = float(match_score.group(1))
        else:
            # Fallback to parsing first numeric score found
            matches = re.findall(r"\d+(?:\.\d+)?", response_text)
            if not matches:
                raise RuntimeError(f"Could not parse a numeric score from Ollama output: '{response_text}'")
            score = float(matches[0])

        score = max(1.0, min(10.0, score))

        match_analysis = re.search(r"\[ANALYSIS:\s*([^\]]+)\]", response_text, re.IGNORECASE)
        analysis_tag = "N/A"
        if match_analysis:
            analysis_tag = match_analysis.group(1).strip()
            if len(analysis_tag) > 30:
                analysis_tag = analysis_tag[:27] + "..."

        return score, analysis_tag

