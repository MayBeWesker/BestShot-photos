from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import threading
import uuid

import numpy as np

from ..config import DATA_ROOT, MAX_VERSIONS
from ..errors import BestShotError
from ..services.preprocess import read_image, write_image


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectStore:
    def __init__(self, root: Path = DATA_ROOT):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _project_dir(self, project_id: str) -> Path:
        if not project_id.startswith("p_") or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789_" for ch in project_id):
            raise BestShotError("项目 ID 无效。", code="invalid_project", status_code=404)
        path = (self.root / project_id).resolve()
        if self.root not in path.parents:
            raise BestShotError("项目路径无效。", code="invalid_project", status_code=404)
        return path

    def _metadata_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "project.json"

    def create(self, main: np.ndarray, main_ext: str, source: np.ndarray, source_ext: str) -> dict:
        with self._lock:
            project_id = f"p_{uuid.uuid4().hex[:12]}"
            directory = self._project_dir(project_id)
            directory.mkdir(parents=True)
            # OpenCV cannot encode HEIC. The merge workspace uses a lossless PNG
            # working copy while the organizer keeps uploaded originals untouched.
            main_storage_ext = main_ext if main_ext in {".jpg", ".png"} else ".png"
            source_storage_ext = source_ext if source_ext in {".jpg", ".png"} else ".png"
            main_name = f"main{main_storage_ext}"
            source_name = f"source{source_storage_ext}"
            write_image(directory / main_name, main)
            write_image(directory / source_name, source)
            write_image(directory / "version_0.png", main)
            metadata = {
                "id": project_id,
                "created_at": utc_now(),
                "main": {"filename": main_name, "width": int(main.shape[1]), "height": int(main.shape[0]), "format": main_storage_ext.lstrip(".")},
                "source": {"filename": source_name, "width": int(source.shape[1]), "height": int(source.shape[0]), "format": source_storage_ext.lstrip(".")},
                "alignment": None,
                "current_version": 0,
                "next_version": 1,
                "versions": [{
                    "version": 0,
                    "parent_version": None,
                    "filename": "version_0.png",
                    "mask_filename": None,
                    "blend_mode": "original",
                    "local_alignment_success": None,
                    "warnings": [],
                    "created_at": utc_now(),
                }],
            }
            self.save(metadata)
            return metadata

    def load(self, project_id: str) -> dict:
        path = self._metadata_path(project_id)
        if not path.exists():
            raise BestShotError("项目不存在或已被删除。", code="project_not_found", status_code=404)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BestShotError("项目数据损坏。", code="project_corrupt", status_code=500) from exc

    def save(self, metadata: dict) -> None:
        with self._lock:
            path = self._metadata_path(metadata["id"])
            temp = path.with_suffix(".tmp")
            temp.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(path)

    def path_for(self, project_id: str, filename: str) -> Path:
        directory = self._project_dir(project_id)
        path = (directory / filename).resolve()
        if directory not in path.parents:
            raise BestShotError("文件路径无效。", code="invalid_path", status_code=400)
        return path

    def image(self, project_id: str, filename: str) -> np.ndarray:
        return read_image(self.path_for(project_id, filename))

    def aligned_images(self, project_id: str) -> tuple[np.ndarray, np.ndarray]:
        directory = self._project_dir(project_id)
        return read_image(directory / "aligned_source.png"), read_image(directory / "aligned_valid.png", flags=0)

    def add_version(
        self,
        metadata: dict,
        image: np.ndarray,
        mask: np.ndarray,
        *,
        parent_version: int,
        blend_mode: str,
        local_success: bool,
        warnings: list[str],
    ) -> dict:
        with self._lock:
            version = int(metadata["next_version"])
            image_name = f"version_{version}.png"
            mask_name = f"mask_{version}.png"
            directory = self._project_dir(metadata["id"])
            write_image(directory / image_name, image)
            write_image(directory / mask_name, mask)
            entry = {
                "version": version,
                "parent_version": parent_version,
                "filename": image_name,
                "mask_filename": mask_name,
                "blend_mode": blend_mode,
                "local_alignment_success": local_success,
                "warnings": warnings,
                "created_at": utc_now(),
            }
            metadata["versions"].append(entry)
            metadata["current_version"] = version
            metadata["next_version"] = version + 1
            editable = [item for item in metadata["versions"] if item["version"] != 0]
            if len(editable) > MAX_VERSIONS:
                removable = editable[: len(editable) - MAX_VERSIONS]
                removable_ids = {item["version"] for item in removable}
                metadata["versions"] = [item for item in metadata["versions"] if item["version"] not in removable_ids]
                retained_edits = [item for item in metadata["versions"] if item["version"] != 0]
                if retained_edits and retained_edits[0].get("parent_version") in removable_ids:
                    retained_edits[0]["parent_version"] = 0
                for item in removable:
                    for key in ("filename", "mask_filename"):
                        if item.get(key):
                            (directory / item[key]).unlink(missing_ok=True)
            self.save(metadata)
            return entry

    def version_entry(self, metadata: dict, version: int) -> dict:
        for item in metadata["versions"]:
            if item["version"] == version:
                return item
        raise BestShotError("指定的历史版本不存在。", code="version_not_found", status_code=404)

    def activate_version(self, metadata: dict, version: int) -> dict:
        self.version_entry(metadata, version)
        metadata["current_version"] = version
        self.save(metadata)
        return metadata

    def delete(self, project_id: str) -> None:
        with self._lock:
            directory = self._project_dir(project_id)
            if not directory.exists():
                raise BestShotError("项目不存在或已被删除。", code="project_not_found", status_code=404)
            shutil.rmtree(directory)


store = ProjectStore()

