import time
from pathlib import Path
from src.image_metadata_analyzer.reader import get_exif_data
from PIL import Image

# create dummy images as TIFF but pretend it's cr2
Path("test_images").mkdir(exist_ok=True)
for i in range(10):
    img = Image.new('RGB', (10, 10))
    img.save(f"test_images/{i}.tif")
    Path(f"test_images/{i}.tif").rename(f"test_images/{i}.cr2")

start = time.time()
for i in range(10):
    get_exif_data(Path(f"test_images/{i}.cr2"))
end = time.time()
print(f"Time for 10 sequential: {end - start:.2f}s")
