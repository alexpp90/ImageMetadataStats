import warnings
from pathlib import Path
from PIL import Image, ExifTags
from image_metadata_analyzer.utils import get_exiftool_path

# Suppress specific warnings from Pillow about potentially corrupt EXIF data
# which it often handles gracefully anyway.
warnings.filterwarnings("ignore", "(Possibly )?corrupt EXIF data", UserWarning)

# Extensions that should be processed with ExifTool if available, as they often contain
# complex metadata or are not well-supported by Pillow/exifread.
FORCE_EXIFTOOL_EXTENSIONS = {
    # Existing RAW formats
    '.arw', '.nef', '.cr2', '.dng', '.raw',
    # New RAW formats
    '.cr3', '.raf', '.orf', '.rw2', '.pef', '.srw', '.sr2',
    # High Efficiency formats
    '.heic', '.heif',
    # Web/Lossless formats (better metadata support in ExifTool)
    '.png', '.webp'
}

# All supported extensions. Includes the above plus standard formats handled well by Pillow.
SUPPORTED_EXTENSIONS = FORCE_EXIFTOOL_EXTENSIONS | {'.jpg', '.jpeg', '.tif', '.tiff'}


def get_exif_data(image_path: Path, debug: bool = False) -> dict | None:
    """
    Extracts relevant EXIF data from a single image file.
    Tries to use the `exifread` library for raw files, falling back to Pillow.

    Args:
        image_path: Path object for the image file.
        debug: If True, prints detailed debug information for failed files.

    Returns:
        A dictionary containing the desired metadata, or None if data is
        missing or corrupt.
    """
    # For raw/complex files, Pillow is often unreliable. Try exiftool first, then exifread.
    if image_path.suffix.lower() in FORCE_EXIFTOOL_EXTENSIONS:
        # Try exiftool first
        try:
            import exiftool
            exiftool_path = get_exiftool_path()

            # Configure ExifToolHelper with the custom path if found
            kwargs = {'executable': exiftool_path} if exiftool_path else {}

            with exiftool.ExifToolHelper(**kwargs) as et:
                # We fetch specific tags to avoid fetching everything
                tags_to_fetch = [
                    "Composite:ShutterSpeed", "Composite:Aperture",
                    "Composite:ISO", "EXIF:ISO",
                    "Composite:FocalLength", "EXIF:FocalLength",
                    "Composite:LensID", "LensModel", "LensType"
                ]
                metadata = et.get_tags(str(image_path), tags=tags_to_fetch)

                if metadata:
                    data = metadata[0]  # get_tags returns a list

                    # Helper to convert ExifTool strings to floats
                    def parse_val(val):
                        if val is None:
                            return None
                        if isinstance(val, (int, float)):
                            return float(val)
                        if isinstance(val, str):
                            # Handle things like "21.8 mm"
                            val = val.split(' ')[0]
                            # Handle fractions like "1/320"
                            if '/' in val:
                                try:
                                    n, d = val.split('/')
                                    return float(n) / float(d)
                                except ValueError:
                                    pass
                            try:
                                return float(val)
                            except ValueError:
                                return None
                        return None

                    # Prioritize Composite tags as they are usually calculated/normalized
                    shutter_speed = parse_val(data.get("Composite:ShutterSpeed"))
                    aperture = parse_val(data.get("Composite:Aperture"))

                    # ISO might be in different places
                    iso_val = data.get("Composite:ISO") or data.get("EXIF:ISO")
                    iso = parse_val(iso_val)

                    # Focal Length
                    fl_val = data.get("Composite:FocalLength") or data.get("EXIF:FocalLength")
                    focal_length = parse_val(fl_val)

                    # Lens Model
                    lens_model = (data.get("Composite:LensID") or
                                  data.get("LensModel") or
                                  data.get("LensType") or
                                  "Unknown")

                    if all(v is not None for v in [shutter_speed, aperture, focal_length, iso]):
                        if debug:
                            print(f"Successfully processed {image_path.name} with exiftool.")
                        return {
                            'Shutter Speed': shutter_speed,
                            'Aperture': aperture,
                            'Focal Length': focal_length,
                            'ISO': iso,
                            'Lens': lens_model,
                        }

        except ImportError:
            if debug:
                print("PyExifTool not installed or found.")
        except Exception as e:
            if debug:
                print(f"exiftool failed on {image_path.name}: {e}")

        # Fallback to exifread
        try:
            import exifread

            with open(image_path, 'rb') as f:
                tags = exifread.process_file(f, details=False)

            if tags:
                # Helper to extract and convert values from exifread tags
                def get_tag_float(tag_name):
                    tag = tags.get(tag_name)
                    if not tag or not tag.values:
                        return None
                    val = tag.values[0]
                    if hasattr(val, 'num'):  # It's a Ratio object
                        if val.den == 0:
                            return None
                        return float(val.num) / float(val.den)
                    try:
                        return float(val)
                    except (TypeError, ValueError):
                        return None

                shutter_speed = get_tag_float('EXIF ExposureTime')
                aperture = get_tag_float('EXIF FNumber')
                focal_length = get_tag_float('EXIF FocalLength')
                iso_tag = tags.get('EXIF ISOSpeedRatings')
                iso = iso_tag.values[0] if iso_tag and iso_tag.values else None

                lens_model_tag = tags.get('EXIF LensModel') or tags.get('MakerNote LensModel')
                lens_model = str(lens_model_tag.values).strip() if lens_model_tag else "Unknown"

                if all(v is not None for v in [shutter_speed, aperture, focal_length, iso]):
                    if debug:
                        print(f"Successfully processed {image_path.name} with exifread.")
                    return {
                        'Shutter Speed': shutter_speed,
                        'Aperture': aperture,
                        'Focal Length': focal_length,
                        'ISO': iso,
                        'Lens': lens_model,
                    }
        except ImportError:
            if debug:
                print("\nWarning: `exifread` library not found. "
                      "Falling back to Pillow for raw files. "
                      "For better raw file support, `pip install exifread`")
        except Exception as e:
            if debug:
                print(f"\nexifread failed on {image_path.name}: {e}")

    # Fallback to Pillow for all file types, or as primary for JPG/TIF
    try:
        img = Image.open(image_path)
        # Use the recommended getexif() method which returns an Exif object
        try:
            exif_data_raw = img.getexif()
        except AttributeError:
            # Fallback for older Pillow versions that use the private method
            exif_data_raw = img._getexif()

        if not exif_data_raw:
            if debug:
                # This debug message will now primarily appear for non-raw files
                # or as a fallback.
                print(f"\n--- Debugging failed extraction for: {image_path.name} ---")
                print("  Reason: No EXIF data found in the image file.")
                print("----------------------------------------------------")
            return None

        # The main camera settings are often in a nested Exif IFD.
        # We'll try to get it and merge it with the top-level IFD.
        # Tag 34665 (0x8769) is for the Exif IFD pointer.
        try:
            exif_ifd = exif_data_raw.get_ifd(34665)
        except KeyError:
            exif_ifd = {}

        # Create a more readable dictionary from the raw EXIF data
        # The .get(k, k) handles unknown tags gracefully.
        exif_data = {ExifTags.TAGS.get(k, k): v for k, v in exif_data_raw.items()}
        exif_ifd_data = {ExifTags.TAGS.get(k, k): v for k, v in exif_ifd.items()}
        # Merge them, with the more specific Exif IFD taking precedence
        exif_data.update(exif_ifd_data)

        if not exif_data:
            if debug:
                print(f"\n--- Debugging (Pillow) failed extraction for: {image_path.name} ---")
                print("  Reason: EXIF data was found, but it contains no known tags after merging.")
                print("----------------------------------------------------")
            return None

        # Helper to robustly convert EXIF values to a float
        def get_float(value):
            if value is None:
                return None
            # Handle PIL's IFDRational type which has numerator/denominator
            if hasattr(value, 'numerator') and hasattr(value, 'denominator'):
                if value.denominator == 0:
                    return None
                return float(value.numerator) / float(value.denominator)
            # Handle tuple type for some rational values, e.g. (28, 10) for 2.8
            if isinstance(value, tuple) and len(value) == 2:
                num, den = value
                if den == 0:
                    return None
                return float(num) / float(den)
            # Handle byte strings which might be null-terminated
            if isinstance(value, bytes):
                try:
                    return float(value.strip(b'\x00').decode('utf-8', errors='ignore'))
                except (ValueError, UnicodeDecodeError):
                    return None
            # Handle simple numeric types
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        shutter_speed_raw = exif_data.get('ExposureTime')
        aperture_raw = exif_data.get('FNumber')
        focal_length_raw = exif_data.get('FocalLength')
        # ISO can sometimes be a tuple (e.g., (100, 0)), take the first element
        iso_raw = exif_data.get('ISOSpeedRatings')
        lens_model_raw = exif_data.get('LensModel')

        shutter_speed = get_float(shutter_speed_raw)
        aperture = get_float(aperture_raw)
        focal_length = get_float(focal_length_raw)
        iso = get_float(iso_raw[0] if isinstance(iso_raw, tuple) else iso_raw)
        lens_model = lens_model_raw or "Unknown"

        # We will accept the file if at least one piece of essential metadata is found.
        if all(v is None for v in [shutter_speed, aperture, focal_length, iso, lens_model_raw]):
            if debug:
                print(f"\n--- Debugging (Pillow) failed extraction for: {image_path.name} ---")
                print(f"  Raw Shutter Speed: {shutter_speed_raw!r} (Type: {type(shutter_speed_raw).__name__}) -> "
                      f"Parsed: {shutter_speed}")
                print(f"  Raw Aperture:      {aperture_raw!r} (Type: {type(aperture_raw).__name__}) -> "
                      f"Parsed: {aperture}")
                print(f"  Raw Focal Length:  {focal_length_raw!r} (Type: {type(focal_length_raw).__name__}) -> "
                      f"Parsed: {focal_length}")
                print(f"  Raw ISO:           {iso_raw!r} (Type: {type(iso_raw).__name__}) -> Parsed: {iso}")
                print(f"  Lens Model:        {lens_model!r}")
                print("  Reason: None of the essential metadata fields could be found or parsed.")
                # Add this new part to show all available keys
                if exif_data:
                    import textwrap
                    # Show all keys from the merged dictionary
                    available_keys = ", ".join(sorted([str(k) for k in exif_data.keys()]))
                    print("\n  Available EXIF keys found in this file (merged):")
                    print(textwrap.fill(available_keys, width=80, initial_indent="    ", subsequent_indent="    "))
                else:
                    # This case is already handled above, but for safety.
                    print("\n  No known EXIF keys were found in this file.")
                print("----------------------------------------------------")
            return None

        return {
            'Shutter Speed': shutter_speed,
            'Aperture': aperture,
            'Focal Length': focal_length,
            'ISO': iso,
            'Lens': lens_model,
        }
    except Exception as e:
        # Catch all other exceptions from opening/reading files (e.g., not an image, corrupt file)
        if debug:
            print(f"\n--- Debugging (Pillow) failed extraction for: {image_path.name} ---")
            print(f"  An unexpected error occurred: {e}")
            print("----------------------------------------------------")
        return None
