import logging
import queue
import threading
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, Optional, Callable, List, Union
from pathlib import Path
from PIL import Image

from image_metadata_analyzer.utils import load_image_preview
from image_metadata_analyzer.models import ScanResult
from image_metadata_analyzer.sharpness import calculate_sharpness, calculate_noise
from image_metadata_analyzer.reader import get_exif_data

logger = logging.getLogger(__name__)


class ImageCacheManager:
    """
    Manages background loading and caching of image previews and full-resolution images.
    Decouples threading and cache state from the GUI.
    """

    def __init__(
        self,
        preview_cache_limit: int = 30,
        full_res_cache_limit: int = 10,
        preview_size: tuple[int, int] = (800, 800),
    ):
        self.preview_cache_limit = preview_cache_limit
        self.full_res_cache_limit = full_res_cache_limit
        self.preview_size = preview_size

        # Queues
        self.preview_queue: queue.Queue = queue.Queue()
        self.full_res_queue: queue.Queue = queue.Queue()

        # Caches
        self.preview_cache: Dict[Path, Image.Image] = {}
        self.full_res_cache: Dict[Path, Image.Image] = {}

        # Locks
        self.preview_lock = threading.Lock()
        self.full_res_lock = threading.Lock()

        # Threads
        self.preview_thread: Optional[threading.Thread] = None
        self.full_res_thread: Optional[threading.Thread] = None

        self._start_threads()

    def _start_threads(self) -> None:
        self.preview_thread = threading.Thread(
            target=self._run_preview_worker, daemon=True
        )
        self.full_res_thread = threading.Thread(
            target=self._run_full_res_worker, daemon=True
        )
        # Ensure they are not None before starting (satisfy type checker)
        if self.preview_thread:
            self.preview_thread.start()
        if self.full_res_thread:
            self.full_res_thread.start()

    def queue_preview(self, path: Path):
        self.preview_queue.put(path)

    def queue_full_res(self, path: Path):
        self.full_res_queue.put(path)

    def get_preview(self, path: Path) -> Optional[Image.Image]:
        with self.preview_lock:
            return self.preview_cache.get(path)

    def get_full_res(self, path: Path) -> Optional[Image.Image]:
        with self.full_res_lock:
            return self.full_res_cache.get(path)

    def clear(self):
        with self.preview_lock:
            self.preview_cache.clear()
        with self.full_res_lock:
            self.full_res_cache.clear()
        self.clear_queues()

    def clear_queues(self):
        # Empty queues if possible
        while not self.preview_queue.empty():
            try:
                self.preview_queue.get_nowait()
            except queue.Empty:
                break
        self.clear_full_res_queue()

    def clear_full_res_queue(self):
        while not self.full_res_queue.empty():
            try:
                self.full_res_queue.get_nowait()
            except queue.Empty:
                break

    def _run_preview_worker(self):
        while True:
            try:
                path = self.preview_queue.get()
                if path is None:
                    continue

                with self.preview_lock:
                    if path in self.preview_cache:
                        continue

                # Use load_image_preview from utils
                img = load_image_preview(path, max_size=self.preview_size)
                if img:
                    with self.preview_lock:
                        self.preview_cache[path] = img
                        # FIFO pruning
                        if len(self.preview_cache) > self.preview_cache_limit:
                            first = next(iter(self.preview_cache))
                            self.preview_cache.pop(first, None)
            except Exception as e:
                # 'path' might not be defined if get() fails
                path_str = str(path) if "path" in locals() else "unknown"
                logger.debug(f"Preview load error for {path_str}: {e}")

    def _run_full_res_worker(self):
        while True:
            try:
                path = self.full_res_queue.get()
                if path is None:
                    continue

                with self.full_res_lock:
                    if path in self.full_res_cache:
                        continue

                # Load full resolution
                img = load_image_preview(path, full_res=True)
                if img:
                    with self.full_res_lock:
                        self.full_res_cache[path] = img
                        # FIFO pruning
                        if len(self.full_res_cache) > self.full_res_cache_limit:
                            first = next(iter(self.full_res_cache))
                            self.full_res_cache.pop(first, None)
            except Exception as e:
                path_str = str(path) if "path" in locals() else "unknown"
                logger.debug(f"Full res load error for {path_str}: {e}")


def _process_single_file(f: Path, grid_size: int, tools: Dict[str, bool]) -> ScanResult:
    """Helper module function to process a single image for parallel execution."""
    score: Union[float, str] = "N/A"
    if tools.get("sharpness", False):
        score = calculate_sharpness(f, grid_size=grid_size)

    noise_score: Union[float, str] = "N/A"
    if tools.get("noise", False):
        noise_score = calculate_noise(f)

    # Fetch EXIF
    exif = get_exif_data(f) or {}

    return ScanResult(
        path=f,
        score=score,
        noise_score=noise_score,
        exif=exif,
    )


class ScanController:
    """
    Handles background scanning of images for sharpness and noise.
    Decouples scanning logic from the GUI.
    """

    def __init__(self):
        self.stop_event = threading.Event()
        self.is_scanning = False

    def run_scan(
        self,
        files: List[Path],
        grid_size: int,
        tools: Dict[str, bool],
        progress_callback: Callable[[ScanResult, int, int], None],
        finished_callback: Callable[[], None],
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        """Starts the scan in a background thread."""
        self.is_scanning = True
        self.stop_event.clear()

        thread = threading.Thread(
            target=self._scan_worker,
            args=(
                files,
                grid_size,
                tools,
                progress_callback,
                finished_callback,
                log_callback,
            ),
            daemon=True,
        )
        thread.start()

    def cancel(self):
        if self.is_scanning:
            self.stop_event.set()

    def _scan_worker(
        self,
        files: List[Path],
        grid_size: int,
        tools: Dict[str, bool],
        progress_callback: Callable[[ScanResult, int, int], None],
        finished_callback: Callable[[], None],
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        def log(msg: str):
            if log_callback:
                log_callback(msg)

        try:
            total = len(files)
            if total == 0:
                log("No images to scan.")
                return

            log(f"Scanning {total} images. Starting analysis...")

            with ProcessPoolExecutor() as executor:
                # Submit all tasks
                futures = {
                    executor.submit(_process_single_file, f, grid_size, tools): f
                    for f in files
                }

                completed_count = 0
                for future in as_completed(futures):
                    if self.stop_event.is_set():
                        log("Scan cancelled.")
                        # Attempt to cancel pending futures
                        for pending_future in futures:
                            pending_future.cancel()
                        break

                    f = futures[future]
                    log(f"Analyzed {f.name}...")

                    try:
                        res = future.result()
                        completed_count += 1
                        # Notify progress
                        progress_callback(res, completed_count, total)
                    except Exception as e:
                        log(f"Error processing {f.name}: {e}")
                        logger.exception(f"Error processing {f.name}")

            log("Scan complete.")

        except Exception as e:
            log(f"Error during scan: {e}")
            logger.exception("Scan worker error")
        finally:
            self.is_scanning = False
            finished_callback()
