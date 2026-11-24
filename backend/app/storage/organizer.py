from __future__ import annotations

import json
import shutil
import threading
import uuid
from pathlib import Path

import cv2
import numpy as np

from ..config import DATA_ROOT
from ..errors import BestShotError
from ..services.preprocess import write_image
from .projects import utc_now


class OrganizerStore:
    def __init__(self, root: Path = DATA_ROOT):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _directory(self, project_id: str) -> Path:
        if not project_id.startswith("o_") or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789_" for ch in project_id):
            raise BestShotError("整理项目 ID 无效。", code="invalid_project", status_code=404)
        path = (self.root / project_id).resolve()
        if self.root not in path.parents:
            raise BestShotError("整理项目路径无效。", code="invalid_project", status_code=404)
        return path

    def begin(self, sensitivity: str) -> dict:
        with self._lock:
            project_id = f"o_{uuid.uuid4().hex[:12]}"
            directory = self._directory(project_id)
            directory.mkdir(parents=True)
            metadata = {
                "id": project_id,
                "type": "organizer",
                "created_at": utc_now(),
                "sensitivity": sensitivity,
                "photos": [],
                "groups": [],
            }
            self.save(metadata)
            return metadata

    def add_photo(
        self,
        metadata: dict,
        *,
        data: bytes,
        image: np.ndarray,
        extension: str,
        original_name: str,
        taken_at,
        quality: dict,
    ) -> None:
        index = len(metadata["photos"])
        photo_id = f"photo_{index + 1:03d}"
        filename = f"{photo_id}{extension}"
        thumbnail_name = f"{photo_id}_thumb.jpg"
        directory = self._directory(metadata["id"])
        # Keep the uploaded bytes untouched; thumbnails are separate derived files.
        (directory / filename).write_bytes(data)
        height, width = image.shape[:2]
        thumb_scale = min(1.0, 420.0 / max(height, width))
        thumbnail = cv2.resize(image, (round(width * thumb_scale), round(height * thumb_scale)), interpolation=cv2.INTER_AREA)
        write_image(directory / thumbnail_name, thumbnail, quality=88)
        metadata["photos"].append({
            "id": photo_id,
            "original_name": original_name,
            "filename": filename,
            "thumbnail_filename": thumbnail_name,
            "width": width,
            "height": height,
            "taken_at": taken_at.isoformat() if taken_at else None,
            "quality": quality,
        })

    def finalize(self, metadata: dict, groups: list[list[int]]) -> dict:
        mapped_groups = []
        for group_index, members in enumerate(groups):
            photo_ids = [metadata["photos"][index]["id"] for index in members]
            mapped_groups.append({"id": f"group_{group_index + 1:03d}", "name": f"场景 {group_index + 1}", "photo_ids": photo_ids})
        metadata["groups"] = mapped_groups
        self.save(metadata)
        return metadata

    def save(self, metadata: dict) -> None:
        path = self._directory(metadata["id"]) / "project.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    def load(self, project_id: str) -> dict:
        path = self._directory(project_id) / "project.json"
        if not path.exists():
            raise BestShotError("整理项目不存在或已删除。", code="project_not_found", status_code=404)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BestShotError("整理项目数据损坏。", code="project_corrupt", status_code=500) from exc

    def photo_path(self, project_id: str, photo_id: str, thumbnail: bool = False) -> Path:
        metadata = self.load(project_id)
        photo = next((item for item in metadata["photos"] if item["id"] == photo_id), None)
        if not photo:
            raise BestShotError("照片不存在。", code="photo_not_found", status_code=404)
        name = photo["thumbnail_filename"] if thumbnail else photo["filename"]
        return self._directory(project_id) / name

    def delete(self, project_id: str) -> None:
        directory = self._directory(project_id)
        if not directory.exists():
            raise BestShotError("整理项目不存在或已删除。", code="project_not_found", status_code=404)
        shutil.rmtree(directory)


organizer_store = OrganizerStore()
