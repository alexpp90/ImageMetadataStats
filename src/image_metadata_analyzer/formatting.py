from typing import Union


def format_score(val: Union[float, str, None], decimal_places: int = 1) -> str:
    """Formats a sharpness or noise score safely."""
    if val is None or val == "N/A":
        return "N/A"
    if isinstance(val, float):
        return f"{val:.{decimal_places}f}"
    return str(val)


def format_meta(val: Union[float, str, tuple, None], unit: str = "") -> str:
    """Formats EXIF metadata values with appropriate units."""
    if val is None or val == "N/A":
        return "N/A"
    if isinstance(val, float):
        if unit == "s":
            if 0 < val < 1.0:
                denom = int(round(1.0 / val))
                return f"1/{denom}s"
            return f"{val}s"
        if unit == "mm":
            return f"{val:.0f}mm"
        if unit == "f/":
            return f"f/{val:.1f}"
        return f"{val:.1f}"
    return str(val)
