from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient
from app.main import app
from app.api import routes
from app.storage.organizer import OrganizerStore
from app.services.global_align import align_global
from app.services.mask import process_mask
from app.services.pipeline import compose
from app.storage.projects import ProjectStore


def encoded(image: np.ndarray, suffix: str = ".png") -> bytes:
    ok, data = cv2.imencode(suffix, image)
    assert ok
    return data.tobytes()


def feature_photo(width=480, height=360) -> np.ndarray:
    image = np.full((height, width, 3), 28, dtype=np.uint8)
    rng = np.random.default_rng(7)
    for index in range(100):
        x, y = rng.integers(15, width - 15), rng.integers(15, height - 15)
        cv2.circle(image, (int(x), int(y)), int(rng.integers(2, 8)), tuple(int(v) for v in rng.integers(70, 255, 3)), -1)
    cv2.rectangle(image, (150, 120), (330, 285), (65, 95, 160), -1)
    cv2.putText(image, "GROUP", (165, 210), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (250, 250, 250), 2)
    return image


def test_project_storage_alignment_compose_and_export(tmp_path: Path):
    local_store = ProjectStore(tmp_path / "projects")
    main = feature_photo()
    source = cv2.warpAffine(main, np.float32([[1, 0, 5], [0, 1, 3]]), (main.shape[1], main.shape[0]))
    source[150:210, 210:270] = (35, 210, 245)
    metadata = local_store.create(main, ".png", source, ".png")
    project_id = metadata["id"]
    alignment = align_global(main, source)
    assert alignment.inlier_count >= 10

    mask = np.zeros(main.shape[:2], dtype=np.uint8)
    cv2.circle(mask, (240, 180), 45, 255, -1)
    cleaned_mask = process_mask(encoded(mask), (main.shape[1], main.shape[0]), alignment.valid_mask)
    result = compose(
        main,
        alignment.aligned,
        cleaned_mask,
        use_local_alignment=False,
        blend_method="feather",
        feather_radius=8,
    )
    entry = local_store.add_version(
        metadata,
        result.image,
        cleaned_mask,
        parent_version=0,
        blend_mode="feather",
        local_success=result.local_alignment_success,
        warnings=result.warnings,
    )
    assert entry["version"] == 1
    reloaded = local_store.load(project_id)
    assert reloaded["current_version"] == 1
    exported = local_store.image(project_id, entry["filename"])
    assert exported.shape == main.shape
    assert np.mean(cv2.absdiff(exported, main)) > 0.1


def test_version_history_keeps_original_and_latest_ten(tmp_path: Path):
    local_store = ProjectStore(tmp_path / "history")
    image = feature_photo(320, 240)
    mask = np.zeros(image.shape[:2], dtype=np.uint8)
    mask[80:160, 110:210] = 255
    metadata = local_store.create(image, ".png", image, ".png")
    parent = 0
    for _ in range(12):
        entry = local_store.add_version(
            metadata,
            image,
            mask,
            parent_version=parent,
            blend_mode="feather",
            local_success=True,
            warnings=[],
        )
        parent = entry["version"]
    assert len(metadata["versions"]) == 11
    assert metadata["versions"][0]["version"] == 0
    assert metadata["versions"][1]["parent_version"] == 0
    assert metadata["versions"][-1]["version"] == 12


def test_merge_store_uses_lossless_working_copy_for_heic(tmp_path: Path):
    local_store = ProjectStore(tmp_path / "heic-workspace")
    image = feature_photo(320, 240)
    metadata = local_store.create(image, ".heic", image, ".heic")
    assert metadata["main"]["filename"] == "main.png"
    assert metadata["source"]["filename"] == "source.png"
    assert local_store.image(metadata["id"], "main.png").shape == image.shape


def test_group_merge_creates_independent_project_and_rejects_invalid_pairs(tmp_path, monkeypatch):
    organizer = OrganizerStore(tmp_path / "organizer")
    merges = ProjectStore(tmp_path / "merges")
    monkeypatch.setattr(routes, "organizer_store", organizer)
    monkeypatch.setattr(routes, "store", merges)
    metadata = organizer.begin("standard")
    image = feature_photo()
    for index in range(3):
        organizer.add_photo(metadata, data=encoded(image), image=image, extension=".png",
                            original_name=f"test-{index}.png", taken_at=None, quality={"score": 90})
    organizer.finalize(metadata, [[0, 1], [2]])
    endpoint = f"/api/organizer/projects/{metadata['id']}/merge"
    with TestClient(app) as client:
        response = client.post(endpoint, json={"main_photo_id": "photo_001", "source_photo_id": "photo_002"})
        assert response.status_code == 201
        merged = response.json()
        assert merged["main_image"]["width"] == image.shape[1]
        assert merges.load(merged["id"])["current_version"] == 0
        assert organizer.photo_path(metadata["id"], "photo_001").read_bytes() == encoded(image)
        for source in ("photo_001", "photo_003", "photo_999"):
            invalid = client.post(endpoint, json={"main_photo_id": "photo_001", "source_photo_id": source})
            assert invalid.status_code == 400

