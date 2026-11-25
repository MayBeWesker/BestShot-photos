import json
from io import BytesIO
from pathlib import Path
import re
import zipfile

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from ..errors import BestShotError
from ..config import ORGANIZER_MAX_IMAGE_EDGE, ORGANIZER_MAX_IMAGE_PIXELS
from ..schemas import ComposeResponse, HealthResponse, MomentsDownloadRequest, MomentsRegenerationRequest, MomentsReplacementRequest, MomentsReplacementResponse, MomentsSelectionRequest, MomentsSelectionResponse, OrganizerProjectResponse, ProjectResponse
from ..services.global_align import align_global
from ..services.mask import process_mask
from ..services.pipeline import compose
from ..services.preprocess import decode_upload, read_image, write_image
from ..services.photo_classifier import cluster_photos, extract_features, extract_taken_at, score_quality
from ..services.deepseek_selection import regenerate_moments_photos, replace_moments_photo, select_moments_photos
from ..storage.organizer import organizer_store
from ..storage.projects import store


router = APIRouter(prefix="/api")


def serialize_organizer(metadata: dict) -> dict:
    project_id = metadata["id"]
    photos = [
        {
            "id": item["id"],
            "original_name": item["original_name"],
            "width": item["width"],
            "height": item["height"],
            "taken_at": item["taken_at"],
            "quality": item["quality"],
            "image_url": f"/api/organizer/projects/{project_id}/photos/{item['id']}",
            "thumbnail_url": f"/api/organizer/projects/{project_id}/photos/{item['id']}/thumbnail",
        }
        for item in metadata["photos"]
    ]
    return {**metadata, "photos": photos}


def build_moments_archive(metadata: dict, photo_ids: list[str]) -> bytes:
    if len(photo_ids) != len(set(photo_ids)):
        raise BestShotError("下载列表中存在重复照片。", code="duplicate_photos")
    photos = {photo["id"]: photo for photo in metadata["photos"]}
    missing = [photo_id for photo_id in photo_ids if photo_id not in photos]
    if missing:
        raise BestShotError("下载列表中包含不存在的照片。", code="photo_not_found", status_code=404)

    archive = BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for index, photo_id in enumerate(photo_ids, start=1):
            photo = photos[photo_id]
            safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", photo["original_name"]).strip(" .") or photo["filename"]
            bundle.writestr(f"{index:02d}_{safe_name}", organizer_store.photo_path(metadata["id"], photo_id).read_bytes())
    return archive.getvalue()


def _image_url(project_id: str, kind: str) -> str:
    return f"/api/projects/{project_id}/images/{kind}"


def serialize_project(metadata: dict) -> dict:
    project_id = metadata["id"]
    alignment = metadata.get("alignment")
    versions = [
        {
            "version": item["version"],
            "parent_version": item["parent_version"],
            "result_url": f"/api/projects/{project_id}/versions/{item['version']}",
            "blend_mode": item["blend_mode"],
            "local_alignment_success": item["local_alignment_success"],
            "warnings": item["warnings"],
            "created_at": item["created_at"],
        }
        for item in metadata["versions"]
    ]
    return {
        "id": project_id,
        "created_at": metadata["created_at"],
        "main_image": {**metadata["main"], "url": _image_url(project_id, "main")},
        "source_image": {**metadata["source"], "url": _image_url(project_id, "source")},
        "alignment": alignment,
        "versions": versions,
        "current_version": metadata["current_version"],
    }


@router.get("/health", response_model=HealthResponse)
def health() -> dict:
    return {"status": "ok", "service": "bestshot-photos"}


@router.post("/organizer/projects", response_model=OrganizerProjectResponse, status_code=201)
async def create_organizer_project(
    photos: list[UploadFile] = File(...),
    sensitivity: str = Form("standard"),
) -> dict:
    if not 2 <= len(photos) <= 200:
        raise BestShotError("请选择 2–200 张照片。", code="invalid_photo_count")
    if sensitivity not in {"conservative", "standard", "loose"}:
        raise BestShotError("分组灵敏度无效。", code="invalid_sensitivity")

    metadata = organizer_store.begin(sensitivity)
    features = []
    try:
        for upload in photos:
            data = await upload.read()
            image, extension = decode_upload(
                data,
                max_image_edge=ORGANIZER_MAX_IMAGE_EDGE,
                max_image_pixels=ORGANIZER_MAX_IMAGE_PIXELS,
            )
            taken_at = extract_taken_at(data)
            quality = score_quality(image)
            organizer_store.add_photo(
                metadata,
                data=data,
                image=image,
                extension=extension,
                original_name=Path(upload.filename or "未命名照片").name,
                taken_at=taken_at,
                quality=quality.__dict__,
            )
            features.append(extract_features(image, taken_at))

        groups = cluster_photos(features, sensitivity)  # type: ignore[arg-type]
        for group in groups:
            group.sort(key=lambda index: metadata["photos"][index]["quality"]["score"], reverse=True)
        groups.sort(key=lambda group: (-metadata["photos"][group[0]]["quality"]["score"], -len(group)))
        return serialize_organizer(organizer_store.finalize(metadata, groups))
    except Exception:
        organizer_store.delete(metadata["id"])
        raise


@router.get("/organizer/projects/{project_id}", response_model=OrganizerProjectResponse)
def get_organizer_project(project_id: str) -> dict:
    return serialize_organizer(organizer_store.load(project_id))


@router.get("/organizer/projects/{project_id}/photos/{photo_id}")
def get_organizer_photo(project_id: str, photo_id: str) -> FileResponse:
    path = organizer_store.photo_path(project_id, photo_id)
    media = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else f"image/{path.suffix.lstrip('.')}"
    return FileResponse(path, media_type=media, headers={"Cache-Control": "no-store"})


@router.get("/organizer/projects/{project_id}/photos/{photo_id}/thumbnail")
def get_organizer_thumbnail(project_id: str, photo_id: str) -> FileResponse:
    return FileResponse(organizer_store.photo_path(project_id, photo_id, thumbnail=True), media_type="image/jpeg")


@router.post("/organizer/projects/{project_id}/moments-selection", response_model=MomentsSelectionResponse)
def create_moments_selection(project_id: str, request: MomentsSelectionRequest) -> dict:
    metadata = organizer_store.load(project_id)
    result = select_moments_photos(metadata, context=request.context.model_dump())
    metadata["moments_selection"] = result
    organizer_store.save(metadata)
    return result


@router.post("/organizer/projects/{project_id}/moments-download")
def download_moments_archive(project_id: str, request: MomentsDownloadRequest) -> StreamingResponse:
    metadata = organizer_store.load(project_id)
    archive = build_moments_archive(metadata, request.photo_ids)
    return StreamingResponse(
        BytesIO(archive),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="bestshot-moments.zip"'},
    )


@router.post("/organizer/projects/{project_id}/moments-regeneration", response_model=MomentsSelectionResponse)
def regenerate_moments_selection(project_id: str, request: MomentsRegenerationRequest) -> dict:
    metadata = organizer_store.load(project_id)
    result = regenerate_moments_photos(
        metadata,
        previous=request.previous.model_dump(),
        instruction=request.instruction,
    )
    metadata["moments_selection"] = result
    organizer_store.save(metadata)
    return result


@router.post("/organizer/projects/{project_id}/moments-replacement", response_model=MomentsReplacementResponse)
def create_moments_replacement(project_id: str, request: MomentsReplacementRequest) -> dict:
    metadata = organizer_store.load(project_id)
    return replace_moments_photo(metadata, request.photo_ids, request.replace_rank)


@router.delete("/organizer/projects/{project_id}", status_code=204)
def delete_organizer_project(project_id: str) -> None:
    organizer_store.delete(project_id)


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(main_image: UploadFile = File(...), source_image: UploadFile = File(...)) -> dict:
    main, main_ext = decode_upload(await main_image.read())
    source, source_ext = decode_upload(await source_image.read())
    metadata = store.create(main, main_ext, source, source_ext)
    return serialize_project(metadata)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str) -> dict:
    return serialize_project(store.load(project_id))


@router.post("/projects/{project_id}/align", response_model=ProjectResponse)
def align_project(project_id: str) -> dict:
    metadata = store.load(project_id)
    main = store.image(project_id, metadata["main"]["filename"])
    source = store.image(project_id, metadata["source"]["filename"])
    result = align_global(main, source)
    write_image(store.path_for(project_id, "aligned_source.png"), result.aligned)
    write_image(store.path_for(project_id, "aligned_valid.png"), result.valid_mask)
    metadata["alignment"] = {
        "status": "success",
        "homography": result.homography.tolist(),
        "match_count": result.match_count,
        "inlier_count": result.inlier_count,
        "inlier_ratio": result.inlier_ratio,
        "reprojection_error": result.reprojection_error,
        "valid_coverage": result.valid_coverage,
    }
    store.save(metadata)
    return serialize_project(metadata)


@router.post("/projects/{project_id}/compose", response_model=ComposeResponse)
async def compose_project(
    project_id: str,
    mask_file: UploadFile = File(...),
    base_version: int = Form(...),
    blend_method: str = Form("feather"),
    feather_radius: int = Form(12),
    use_local_alignment: bool = Form(True),
) -> dict:
    metadata = store.load(project_id)
    if not metadata.get("alignment") or metadata["alignment"].get("status") != "success":
        raise BestShotError("请先完成全局自动配准。", code="alignment_required", status_code=409)
    version = store.version_entry(metadata, base_version)
    base = store.image(project_id, version["filename"])
    aligned_source, valid_mask = store.aligned_images(project_id)
    mask_data = await mask_file.read()
    mask = process_mask(mask_data, (base.shape[1], base.shape[0]), valid_mask)
    output = compose(
        base,
        aligned_source,
        mask,
        use_local_alignment=use_local_alignment,
        blend_method=blend_method,
        feather_radius=feather_radius,
    )
    entry = store.add_version(
        metadata,
        output.image,
        mask,
        parent_version=base_version,
        blend_mode=blend_method,
        local_success=output.local_alignment_success,
        warnings=output.warnings,
    )
    return {
        "project_id": project_id,
        "version": entry["version"],
        "status": "success",
        "result_url": f"/api/projects/{project_id}/versions/{entry['version']}",
        "local_alignment_success": output.local_alignment_success,
        "fallback_used": output.fallback_used,
        "warnings": output.warnings,
    }


@router.post("/projects/{project_id}/versions/{version}/activate", response_model=ProjectResponse)
def activate_version(project_id: str, version: int) -> dict:
    metadata = store.load(project_id)
    return serialize_project(store.activate_version(metadata, version))


@router.get("/projects/{project_id}/versions/{version}")
def get_version(project_id: str, version: int) -> FileResponse:
    metadata = store.load(project_id)
    entry = store.version_entry(metadata, version)
    return FileResponse(store.path_for(project_id, entry["filename"]), media_type="image/png", headers={"Cache-Control": "no-store"})


@router.get("/projects/{project_id}/images/{kind}")
def get_image(project_id: str, kind: str) -> FileResponse:
    metadata = store.load(project_id)
    mapping = {
        "main": metadata["main"]["filename"],
        "source": metadata["source"]["filename"],
        "aligned": "aligned_source.png",
    }
    if kind not in mapping:
        raise BestShotError("图片类型无效。", code="image_not_found", status_code=404)
    path = store.path_for(project_id, mapping[kind])
    if not path.exists():
        raise BestShotError("图片尚未生成。", code="image_not_found", status_code=404)
    media_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "no-store"})


@router.get("/projects/{project_id}/export")
def export_project(project_id: str) -> FileResponse:
    metadata = store.load(project_id)
    entry = store.version_entry(metadata, metadata["current_version"])
    return FileResponse(
        store.path_for(project_id, entry["filename"]),
        media_type="image/png",
        filename=f"bestshot-{project_id}.png",
    )


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str) -> None:
    store.delete(project_id)

