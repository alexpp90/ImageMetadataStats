import exiftool
import gc

et = exiftool.ExifToolHelper()
et.run()
print(et.running)
# Note: typically a context manager `with exiftool.ExifToolHelper() as et:` will close it,
# or calling et.terminate() will. Let's see if relying on ExifToolHelper connection pool works.
