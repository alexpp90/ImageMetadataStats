import time
from pathlib import Path
from src.image_metadata_analyzer.reader import get_exif_data

image_files = [Path(f"test_images/{i}.cr2") for i in range(100)]

start = time.time()
for f in image_files:
    get_exif_data(f, debug=False)
end = time.time()
print(f"Time: {end - start:.2f}s")
