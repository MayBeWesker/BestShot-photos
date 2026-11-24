"""BestShot Merge backend package."""

from pillow_heif import register_heif_opener


# Register HEIC/HEIF once for every Pillow-based decoder and EXIF reader.
register_heif_opener()

