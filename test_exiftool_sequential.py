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
for f in image_files:
    all_metadata.append(get_exif_data(f, debug=False))
end = time.time()
print(f"Time for 100 sequential: {end - start:.2f}s")
