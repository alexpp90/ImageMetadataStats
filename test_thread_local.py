import time
import threading
import concurrent.futures
from pathlib import Path
import exiftool

local_data = threading.local()

def get_et():
    if not hasattr(local_data, "et"):
        local_data.et = exiftool.ExifToolHelper()
        local_data.et.run()
    return local_data.et

def cleanup_et():
    if hasattr(local_data, "et"):
        local_data.et.terminate()
        del local_data.et

def process_file(filepath):
    et = get_et()
    try:
        res = et.get_tags(str(filepath), tags=["Composite:ShutterSpeed"])
        return res
    except Exception as e:
        return e

image_files = [Path(f"test_images/{i}.cr2") for i in range(100)]

start = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
    futures = [executor.submit(process_file, f) for f in image_files]
    # We shouldn't cleanup in the main thread, the thread pool threads need to cleanup.
    # actually let's just see how long it takes to process without explicit cleanup for benchmarking.
    results = [f.result() for f in concurrent.futures.as_completed(futures)]
end = time.time()

print(f"Time with thread-local: {end - start:.2f}s")
