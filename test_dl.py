import urllib.request
import sys
try:
    urllib.request.urlretrieve("https://exiftool.org/exiftool-13.57_64.zip", "test.zip")
    print("Download successful")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
