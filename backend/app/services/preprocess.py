from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from ..config import MAX_IMAGE_EDGE, MAX_IMAGE_PIXELS, MAX_UPLOAD_BYTES
from ..errors import BestShotError


ALLOWED_FORMATS = {
    "JPEG": ".jpg",
    # iPhone exports can use the JPEG-compatible MPO container while keeping
    # a .jpg/.jpeg filename. We process its primary frame as the photo.
    "MPO": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
    "HEIF": ".heic",
    "HEIC": ".heic",
}


def decode_upload(
    data: bytes,
    *,
    max_image_edge: int = MAX_IMAGE_EDGE,
    max_image_pixels: int = MAX_IMAGE_PIXELS,
) -> tuple[np.ndarray, str]:
    if not data:
        raise BestShotError("上传的图片为空。", code="empty_upload")
    if len(data) > MAX_UPLOAD_BYTES:
        raise BestShotError("单张图片不能超过 40 MB。", code="upload_too_large", status_code=413)
    try:
        with Image.open(BytesIO(data)) as opened:
            fmt = (opened.format or "").upper()
            if fmt not in ALLOWED_FORMATS:
                raise BestShotError("仅支持 JPG、JPEG、PNG、WebP、HEIC 和 HEIF 图片。", code="unsupported_format")
            image = ImageOps.exif_transpose(opened).convert("RGB")
            width, height = image.size
            if max(width, height) > max_image_edge or width * height > max_image_pixels:
                raise BestShotError(
                    f"图片尺寸过大；长边需不超过 {max_image_edge} 像素，且总像素不超过 {max_image_pixels // 10_000} 万。",
                    code="image_too_large",
                )
            rgb = np.asarray(image)
    except BestShotError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise BestShotError("无法读取图片，请确认文件没有损坏。", code="invalid_image") from exc
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), ALLOWED_FORMATS[fmt]


def read_image(path: Path, flags: int = cv2.IMREAD_COLOR) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, flags)
    if image is None:
        raise BestShotError(f"无法读取本地图像：{path.name}", code="storage_read_failed", status_code=500)
    return image


def write_image(path: Path, image: np.ndarray, quality: int = 95) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    params = [cv2.IMWRITE_JPEG_QUALITY, quality] if suffix in {".jpg", ".jpeg"} else [cv2.IMWRITE_PNG_COMPRESSION, 3]
    ok, encoded = cv2.imencode(suffix, image, params)
    if not ok:
        raise BestShotError("图片编码失败。", code="storage_write_failed", status_code=500)
    encoded.tofile(str(path))


def normalize_pair(main: np.ndarray, source: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if main.ndim != 3 or source.ndim != 3:
        raise BestShotError("输入图片必须为彩色图片。", code="invalid_image")
    return main, source

