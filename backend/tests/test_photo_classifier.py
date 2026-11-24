from datetime import datetime, timedelta
from io import BytesIO
import zipfile

import cv2
import numpy as np
from PIL import Image
import pytest

from app.api import routes
from app.errors import BestShotError
from app.services.photo_classifier import cluster_photos, extract_features, photo_similarity, score_quality
from app.services.preprocess import decode_upload
from app.storage.organizer import OrganizerStore


def travel_scene(seed: int = 3) -> np.ndarray:
    image = np.full((360, 520, 3), (175, 205, 225), dtype=np.uint8)
    cv2.rectangle(image, (0, 235), (520, 360), (80, 145, 70), -1)
    cv2.rectangle(image, (175, 90), (350, 250), (45, 65, 150), -1)
    cv2.circle(image, (260, 145), 46, (80, 180, 235), -1)
    rng = np.random.default_rng(seed)
    for _ in range(70):
        x, y = rng.integers(8, 512), rng.integers(8, 350)
        cv2.circle(image, (int(x), int(y)), 2, (235, 235, 235), -1)
    return image


def test_similar_burst_is_grouped_and_different_scene_is_separate():
    first = travel_scene()
    second = cv2.warpAffine(first, np.float32([[1, 0, 3], [0, 1, 2]]), (first.shape[1], first.shape[0]))
    different = np.zeros_like(first)
    cv2.line(different, (0, 0), (519, 359), (255, 255, 255), 18)
    cv2.line(different, (519, 0), (0, 359), (50, 90, 245), 18)
    start = datetime(2026, 5, 2, 10, 0, 0)
    features = [
        extract_features(first, start),
        extract_features(second, start + timedelta(seconds=4)),
        extract_features(different, start + timedelta(seconds=8)),
    ]
    assert photo_similarity(features[0], features[1]) > photo_similarity(features[0], features[2])
    groups = cluster_photos(features, "standard")
    assert any(set(group) == {0, 1} for group in groups)
    assert any(group == [2] for group in groups)


def test_complete_link_rule_avoids_chain_merge(monkeypatch):
    import app.services.photo_classifier as classifier

    features = [extract_features(travel_scene(seed)) for seed in (1, 2, 3)]
    scores = {(0, 1): 0.78, (1, 2): 0.78, (0, 2): 0.55}
    index_by_id = {id(feature): index for index, feature in enumerate(features)}

    def fake_similarity(left, right):
        pair = tuple(sorted((index_by_id[id(left)], index_by_id[id(right)])))
        return 1.0 if pair[0] == pair[1] else scores[pair]

    monkeypatch.setattr(classifier, "photo_similarity", fake_similarity)
    groups = classifier.cluster_photos(features, "standard")
    assert len(groups) == 2
    assert groups[0] == [0, 1]
    assert groups[1] == [2]


def test_sharp_photo_scores_above_blurred_copy():
    sharp = travel_scene()
    cv2.putText(sharp, "TRAVEL 2026", (120, 320), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (10, 10, 10), 3)
    blurred = cv2.GaussianBlur(sharp, (31, 31), 9)
    sharp_score = score_quality(sharp)
    blurred_score = score_quality(blurred)
    assert sharp_score.sharpness > blurred_score.sharpness
    assert sharp_score.score > blurred_score.score
    assert 0 <= blurred_score.score <= 100


def test_clean_composition_scores_above_evenly_cluttered_texture():
    clean = np.full((420, 560, 3), (190, 205, 215), dtype=np.uint8)
    cv2.circle(clean, (365, 145), 68, (50, 105, 205), -1)
    cv2.rectangle(clean, (0, 310), (560, 420), (75, 135, 75), -1)
    cluttered = clean.copy()
    rng = np.random.default_rng(19)
    for _ in range(650):
        x, y = rng.integers(0, 560), rng.integers(0, 420)
        color = tuple(int(value) for value in rng.integers(20, 245, 3))
        cv2.circle(cluttered, (int(x), int(y)), int(rng.integers(1, 5)), color, -1)
    clean_score = score_quality(clean)
    cluttered_score = score_quality(cluttered)
    assert clean_score.simplicity > cluttered_score.simplicity + 25
    assert clean_score.score > cluttered_score.score


def test_organizer_api_returns_groups_sorted_by_quality(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "organizer_store", OrganizerStore(tmp_path / "organizer"))
    sharp = travel_scene()
    blurred = cv2.GaussianBlur(sharp, (31, 31), 9)
    ok_sharp, encoded_sharp = cv2.imencode(".jpg", sharp)
    assert ok_sharp
    heic_buffer = BytesIO()
    Image.fromarray(cv2.cvtColor(blurred, cv2.COLOR_BGR2RGB)).save(heic_buffer, format="HEIF", quality=90)
    heic_data = heic_buffer.getvalue()
    decoded_heic, heic_extension = decode_upload(heic_data)
    assert decoded_heic.shape == blurred.shape
    assert heic_extension == ".heic"

    class FakeUpload:
        def __init__(self, data: bytes, filename: str):
            self.data = data
            self.filename = filename

        async def read(self) -> bytes:
            return self.data

    # One request deliberately mixes HEIC and JPEG inputs.
    uploads = [FakeUpload(heic_data, "blurred.heic"), FakeUpload(encoded_sharp.tobytes(), "sharp.jpeg")]
    coroutine = routes.create_organizer_project(uploads, "loose")
    try:
        coroutine.send(None)
        raise AssertionError("The route coroutine unexpectedly suspended")
    except StopIteration as completed:
        project = completed.value
    assert len(project["groups"]) == 1
    ordered_ids = project["groups"][0]["photo_ids"]
    by_id = {photo["id"]: photo for photo in project["photos"]}
    assert by_id[ordered_ids[0]]["original_name"] == "sharp.jpeg"
    assert by_id[ordered_ids[0]]["quality"]["score"] > by_id[ordered_ids[1]]["quality"]["score"]
    blurred_id = next(photo_id for photo_id, photo in by_id.items() if photo["original_name"] == "blurred.heic")
    assert routes.organizer_store.photo_path(project["id"], blurred_id).suffix == ".heic"
    thumbnail = routes.organizer_store.photo_path(project["id"], ordered_ids[0], thumbnail=True)
    assert thumbnail.exists()
    assert thumbnail.suffix == ".jpg"


def test_organizer_groups_are_sorted_by_each_groups_best_score(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "organizer_store", OrganizerStore(tmp_path / "group-order"))
    monkeypatch.setattr(routes, "cluster_photos", lambda _features, _sensitivity: [[0, 1], [2]])
    sharp = travel_scene()
    low_first = cv2.GaussianBlur(sharp, (51, 51), 15)
    low_second = np.full_like(sharp, 120)
    images = [low_first, low_second, sharp]

    class FakeUpload:
        def __init__(self, data: bytes, filename: str):
            self.data = data
            self.filename = filename

        async def read(self) -> bytes:
            return self.data

    uploads = []
    for index, image in enumerate(images):
        ok, encoded = cv2.imencode(".jpg", image)
        assert ok
        uploads.append(FakeUpload(encoded.tobytes(), f"image-{index}.jpg"))

    coroutine = routes.create_organizer_project(uploads, "standard")
    try:
        coroutine.send(None)
        raise AssertionError("The route coroutine unexpectedly suspended")
    except StopIteration as completed:
        project = completed.value

    by_id = {photo["id"]: photo for photo in project["photos"]}
    first_group_best = by_id[project["groups"][0]["photo_ids"][0]]
    second_group_best = by_id[project["groups"][1]["photo_ids"][0]]
    assert first_group_best["quality"]["score"] >= second_group_best["quality"]["score"]
    assert first_group_best["original_name"] == "image-2.jpg"


def test_moments_archive_keeps_requested_order_and_original_files(tmp_path, monkeypatch):
    local_store = OrganizerStore(tmp_path / "moments-download")
    monkeypatch.setattr(routes, "organizer_store", local_store)
    metadata = local_store.begin("standard")
    original_bytes = {}
    for index, color in enumerate(((20, 80, 180), (60, 160, 80)), start=1):
        image = np.full((80, 100, 3), color, dtype=np.uint8)
        ok, encoded = cv2.imencode(".jpg", image)
        assert ok
        data = encoded.tobytes()
        photo_id = f"photo_{index:03d}"
        original_bytes[photo_id] = data
        local_store.add_photo(
            metadata,
            data=data,
            image=image,
            extension=".jpg",
            original_name=f"旅行照片 {index}.jpg",
            taken_at=None,
            quality={"score": 80 + index, "sharpness": 80, "exposure": 80, "color": 80, "composition": 80, "simplicity": 80, "reasons": []},
        )
    metadata = local_store.finalize(metadata, [[0], [1]])

    archive = routes.build_moments_archive(metadata, ["photo_002", "photo_001"])
    with zipfile.ZipFile(BytesIO(archive)) as bundle:
        assert bundle.namelist() == ["01_旅行照片 2.jpg", "02_旅行照片 1.jpg"]
        assert bundle.read(bundle.namelist()[0]) == original_bytes["photo_002"]


def test_unsupported_format_message_lists_current_formats():
    ok, bitmap = cv2.imencode(".bmp", travel_scene())
    assert ok
    with pytest.raises(BestShotError) as raised:
        decode_upload(bitmap.tobytes())
    assert raised.value.code == "unsupported_format"
    assert "JPEG" in raised.value.message
    assert "HEIC" in raised.value.message
    assert "HEIF" in raised.value.message


def test_iphone_mpo_is_accepted_as_jpeg():
    first = Image.new("RGB", (80, 60), "red")
    second = Image.new("RGB", (80, 60), "blue")
    buffer = BytesIO()
    first.save(buffer, format="MPO", save_all=True, append_images=[second])
    decoded, extension = decode_upload(buffer.getvalue())
    assert decoded.shape == (60, 80, 3)
    assert extension == ".jpg"


def test_organizer_limit_accepts_wide_phone_panorama():
    image = Image.new("RGB", (7000, 100), "green")
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=80)
    with pytest.raises(BestShotError) as raised:
        decode_upload(buffer.getvalue())
    assert raised.value.code == "image_too_large"
    decoded, _ = decode_upload(buffer.getvalue(), max_image_edge=12000, max_image_pixels=80_000_000)
    assert decoded.shape == (100, 7000, 3)
