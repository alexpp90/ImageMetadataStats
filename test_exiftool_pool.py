import time
import shutil
from pathlib import Path
from src.image_metadata_analyzer.reader import get_exif_data
import concurrent.futures

image_files = [Path(f"test_images/{i}.cr2") for i in range(100)]
for i in range(10, 100):
    shutil.copy(f"test_images/0.cr2", f"test_images/{i}.cr2")

start = time.time()
all_metadata = []
max_workers = 16
with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = {
        executor.submit(get_exif_data, f, debug=False): f for f in image_files
    }
    for future in concurrent.futures.as_completed(futures):
        all_metadata.append(future.result())
end = time.time()
print(f"Time for 100 threaded: {end - start:.2f}s")
