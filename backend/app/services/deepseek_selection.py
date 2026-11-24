from __future__ import annotations

import base64
from datetime import datetime, timezone
import json

import httpx

from ..config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from ..errors import BestShotError
from ..storage.organizer import OrganizerStore, organizer_store


def _request_json(
    client: httpx.Client,
    credential: str,
    base_url: str,
    model: str,
    content: list[dict],
    *,
    max_tokens: int,
) -> dict:
    try:
        response = client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {credential}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": content}],
                "response_format": {"type": "json_object"},
                "reasoning_effort": "none",
                "max_tokens": max_tokens,
            },
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise BestShotError(
            f"AI 服务请求失败（HTTP {exc.response.status_code}），请稍后重试。",
            code="deepseek_request_failed",
            status_code=502,
        ) from exc
    except httpx.HTTPError as exc:
        raise BestShotError(
            "暂时无法连接 AI 服务，请检查网络后重试。",
            code="deepseek_request_failed",
            status_code=502,
        ) from exc

    try:
        payload = response.json()
        choice = payload["choices"][0]
        message = choice["message"]
        content_text = message.get("content") or ""
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise BestShotError(
            "AI 服务返回了无法识别的结果，请稍后重试。",
            code="deepseek_invalid_response",
            status_code=502,
        ) from exc
    if not isinstance(content_text, str) or not content_text.strip():
        finish_reason = choice.get("finish_reason", "unknown")
        raise BestShotError(
            f"AI 服务没有生成完整结果（finish_reason={finish_reason}），请重试。",
            code="deepseek_empty_response",
            status_code=502,
        )
    try:
        return _parse_json_content(content_text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise BestShotError(
            "AI 服务返回内容无法解析，请稍后重试。",
            code="deepseek_invalid_response",
            status_code=502,
        ) from exc


def _candidate_blocks(metadata: dict, store: OrganizerStore) -> tuple[list[dict], dict[str, dict], float]:
    photos = {item["id"]: item for item in metadata["photos"]}
    representatives = []
    for group in metadata["groups"]:
        if group["photo_ids"]:
            photo = photos[group["photo_ids"][0]]
            representatives.append({"photo": photo, "group_id": group["id"], "score": float(photo["quality"]["score"])})
    representatives.sort(key=lambda item: item["score"], reverse=True)
    if not representatives:
        return [], {}, 0.0

    sorted_scores = sorted(item["score"] for item in representatives)
    median_score = sorted_scores[len(sorted_scores) // 2]
    threshold = round(max(55.0, min(75.0, median_score)), 1)
    eligible = [item for item in representatives if item["score"] >= threshold]
    minimum = min(9, len(representatives))
    if len(eligible) < minimum:
        eligible = representatives[:minimum]
        threshold = round(eligible[-1]["score"], 1)
    eligible = eligible[:60]

    candidates: dict[str, dict] = {}
    blocks: list[dict] = []
    for item in eligible:
        photo = item["photo"]
        photo_id = photo["id"]
        candidates[photo_id] = {"photo": photo, "group_id": item["group_id"]}
        quality = photo["quality"]
        blocks.append({
            "type": "text",
            "text": (
                f"候选 {photo_id}；所属分组 {item['group_id']}；文件 {photo['original_name']}；"
                f"本地质量 {quality['score']}/100；"
                f"清晰 {quality['sharpness']}，曝光 {quality['exposure']}，"
                f"色彩 {quality['color']}，构图 {quality['composition']}，"
                f"简洁度 {quality.get('simplicity', '未计算')}。"
            ),
        })
        encoded = base64.b64encode(store.photo_path(metadata["id"], photo_id, thumbnail=True).read_bytes()).decode("ascii")
        blocks.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{encoded}", "detail": "low"},
        })
    return blocks, candidates, threshold


def _normalize_selection(raw_selected: object, candidates: dict[str, dict], target_count: int) -> list[dict]:
    if not isinstance(raw_selected, list):
        raise BestShotError("AI 服务未返回有效的选片列表。", code="deepseek_invalid_response", status_code=502)
    selected = []
    seen_photos: set[str] = set()
    seen_groups: set[str] = set()
    for item in raw_selected:
        if not isinstance(item, dict):
            continue
        photo_id = str(item.get("candidate_id", ""))
        if photo_id not in candidates or photo_id in seen_photos:
            continue
        candidate = candidates[photo_id]
        group_id = candidate["group_id"]
        if group_id in seen_groups:
            continue
        seen_photos.add(photo_id)
        seen_groups.add(group_id)
        selected.append({
            "rank": len(selected) + 1,
            "group_id": group_id,
            "photo_id": photo_id,
            "reason": str(item.get("reason", "综合画面表现良好"))[:160],
            "role": str(item.get("role", "旅行记录"))[:40],
        })
        if len(selected) == target_count:
            break

    # Keep the generated order, then fill any omitted or repeated cells with
    # the highest-scoring unused scenes instead of discarding the whole result.
    for photo_id, candidate in candidates.items():
        if len(selected) == target_count:
            break
        group_id = candidate["group_id"]
        if photo_id in seen_photos or group_id in seen_groups:
            continue
        seen_photos.add(photo_id)
        seen_groups.add(group_id)
        selected.append({
            "rank": len(selected) + 1,
            "group_id": group_id,
            "photo_id": photo_id,
            "reason": "补充高质量场景，使九图内容完整且不重复。",
            "role": "故事补充",
        })
    return selected


def select_moments_photos(
    metadata: dict,
    *,
    store: OrganizerStore = organizer_store,
    api_key: str | None = None,
    base_url: str = DEEPSEEK_BASE_URL,
    model: str = DEEPSEEK_MODEL,
    client: httpx.Client | None = None,
    context: dict | None = None,
) -> dict:
    credential = (api_key if api_key is not None else DEEPSEEK_API_KEY).strip()
    if not credential:
        raise BestShotError(
            "尚未配置 AI 服务密钥。请在本地 .env 中填写服务密钥后重启应用。",
            code="deepseek_not_configured",
            status_code=503,
        )

    image_blocks, candidates, quality_threshold = _candidate_blocks(metadata, store)
    if not candidates:
        raise BestShotError("当前没有可供精选的照片分组。", code="no_candidates")
    target_count = min(9, len(candidates))
    context = context or {}
    context_lines = []
    labels = {
        "theme": "朋友圈主题",
        "location": "地点",
        "highlights": "值得记录的故事、心情或重点",
        "tone": "期望文案风格",
    }
    for context_key, label in labels.items():
        value = str(context.get(context_key, "")).strip()
        if value:
            context_lines.append(f"- {label}：{value}")
    background = "\n用户提供的朋友圈背景信息：\n" + "\n".join(context_lines) if context_lines else "\n用户没有提供额外背景信息，请只根据图片生成。"
    owns_client = client is None
    request_client = client or httpx.Client(timeout=httpx.Timeout(180.0, connect=20.0))
    try:
        story_prompt = (
            f"你是旅行视觉叙事策划。请先整体观察这 {len(candidates)} 张不同场景的代表照片，"
            f"为最终 {target_count} 张朋友圈九宫格设计一条清晰故事线和有规律的视觉布局。"
            "此阶段只制定方案，不选择具体照片。方案需要有开场、发展、亮点和收尾，说明人物、风景、细节如何穿插，"
            f"以及色彩、远近景和节奏如何排列。beats 必须覆盖 1 到 {target_count} 的每个位置。请仅输出 JSON："
            '{"story_title":"故事标题","story_summary":"故事线",'
            '"beats":[{"position":1,"purpose":"这一格承担的叙事任务","visual_preference":"希望出现的内容"}],'
            '"layout_rationale":"九宫格布局规律和理由"}。'
            f"{background}"
        )
        story_plan = _request_json(
            request_client, credential, base_url, model,
            [{"type": "text", "text": story_prompt}, *image_blocks],
            max_tokens=4096,
        )
        selection_prompt = (
            f"你是旅行朋友圈选片编辑。请严格依据下面已经制定的故事与布局方案，从候选图中选出恰好 {target_count} 张。"
            "优先主体明确、背景干净、杂物少、人物状态自然的照片；避免重复内容。"
            "按九宫格从左到右、从上到下的顺序返回，每一张都要说明叙事角色和入选理由。"
            f"\n故事与布局方案：{json.dumps(story_plan, ensure_ascii=False)}"
            "\n请仅输出 JSON："
            '{"story_title":"故事标题","selected":[{"candidate_id":"photo_001","reason":"入选理由","role":"这一格的叙事角色"}],'
            '"summary":"整体选片说明","layout_rationale":"最终九宫格的排列规律和理由",'
            '"caption_suggestion":"结合背景信息的朋友圈配文"}。'
            "candidate_id 必须逐字使用下方提供的 photo 候选 ID。"
            f"{background}"
        )
        parsed = _request_json(
            request_client, credential, base_url, model,
            [{"type": "text", "text": selection_prompt}, *image_blocks],
            max_tokens=8192,
        )
        initial_selected = _normalize_selection(parsed.get("selected"), candidates, target_count)
        review_prompt = (
            f"你是朋友圈九宫格的终审编辑。下面是初选的 {target_count} 张照片及其从左到右、从上到下的顺序："
            f"{json.dumps(initial_selected, ensure_ascii=False)}。"
            "请把它们作为一个完整九宫格观察，而不是逐张孤立评分。重点检查："
            "横向和纵向相邻图片是否在主体、场景、构图、视角或颜色上过于相似；"
            "远景、人物、建筑和细节是否分布均衡；明暗与色彩是否有节奏；故事开场、发展、亮点和收尾是否自然。"
            "如果相邻画面过于重复，可以从候选中替换；如果内容合适但位置不佳，可以重新排序。"
            f"最终必须返回恰好 {target_count} 张、每个分组最多一张，并按最终九宫格顺序排列。"
            "请仅输出 JSON："
            '{"story_title":"故事标题","selected":[{"candidate_id":"photo_001","reason":"终审理由","role":"叙事角色"}],'
            '"summary":"最终整体说明","grid_review":"对整体美感、相邻相似度和视觉节奏的判断",'
            '"layout_rationale":"最终排列规律和理由","caption_suggestion":"朋友圈配文"}。'
            "candidate_id 必须逐字使用下方提供的候选 ID。"
            f"\n前序故事方案：{json.dumps(story_plan, ensure_ascii=False)}"
            f"\n初选说明：{json.dumps(parsed, ensure_ascii=False)}"
            f"{background}"
        )
        reviewed = _request_json(
            request_client, credential, base_url, model,
            [{"type": "text", "text": review_prompt}, *image_blocks],
            max_tokens=8192,
        )
    finally:
        if owns_client:
            request_client.close()

    selected = _normalize_selection(reviewed.get("selected"), candidates, target_count)

    return {
        "project_id": metadata["id"],
        "model": model,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "story_title": str(reviewed.get("story_title") or parsed.get("story_title") or story_plan.get("story_title") or "这一程的九个瞬间")[:120],
        "summary": str(reviewed.get("summary") or parsed.get("summary") or "已兼顾画面质量、场景变化与叙事节奏。")[:500],
        "grid_review": str(reviewed.get("grid_review") or "已从整体构图、相邻相似度与视觉节奏复核最终九图。")[:800],
        "layout_rationale": str(reviewed.get("layout_rationale") or parsed.get("layout_rationale") or story_plan.get("layout_rationale") or "按开场、发展、亮点和收尾排列，让远景、人物与细节自然穿插。")[:800],
        "caption_suggestion": str(reviewed.get("caption_suggestion") or parsed.get("caption_suggestion") or "记录旅途中值得分享的九个瞬间。")[:500],
        "analysis_candidate_count": len(candidates),
        "quality_threshold": quality_threshold,
        "selected": selected,
    }


def replace_moments_photo(
    metadata: dict,
    photo_ids: list[str],
    replace_rank: int,
    *,
    store: OrganizerStore = organizer_store,
    api_key: str | None = None,
    base_url: str = DEEPSEEK_BASE_URL,
    model: str = DEEPSEEK_MODEL,
    client: httpx.Client | None = None,
) -> dict:
    credential = (api_key if api_key is not None else DEEPSEEK_API_KEY).strip()
    if not credential:
        raise BestShotError(
            "尚未配置 AI 服务密钥。请在本地 .env 中填写服务密钥后重启应用。",
            code="deepseek_not_configured",
            status_code=503,
        )
    if not 1 <= replace_rank <= len(photo_ids):
        raise BestShotError("需要替换的位置无效。", code="invalid_replace_rank")

    photos = {photo["id"]: photo for photo in metadata["photos"]}
    group_by_photo = {
        photo_id: group
        for group in metadata["groups"]
        for photo_id in group["photo_ids"]
    }
    if any(photo_id not in photos or photo_id not in group_by_photo for photo_id in photo_ids):
        raise BestShotError("当前九图中包含不存在的照片。", code="photo_not_found", status_code=404)
    used_group_ids = {group_by_photo[photo_id]["id"] for photo_id in photo_ids}
    alternative_groups = [
        group for group in metadata["groups"]
        if group["id"] not in used_group_ids and group["photo_ids"]
    ]
    alternative_groups.sort(
        key=lambda group: float(photos[group["photo_ids"][0]]["quality"]["score"]),
        reverse=True,
    )
    alternative_groups = alternative_groups[:60]
    if not alternative_groups:
        raise BestShotError("没有尚未使用的分组可供替换。", code="no_replacement_groups")

    content: list[dict] = [{
        "type": "text",
        "text": (
            f"你是朋友圈九宫格编辑。当前九图从左到右、从上到下的照片 ID 为 {json.dumps(photo_ids, ensure_ascii=False)}。"
            f"请只替换第 {replace_rank} 格，并从下方“可替换候选”中选择一个来自未使用分组的画面。"
            "请整体观察当前九图，重点判断新照片与上下左右相邻画面的主体、场景、视角和颜色是否过于相似，"
            "同时保持故事连续、明暗均衡和视觉节奏。不要选择当前九图已有的分组。"
            "仅输出 JSON："
            '{"candidate_id":"photo_001","reason":"为什么替换后更好","role":"新照片的叙事角色",'
            '"grid_review":"替换后整体美感和相邻相似度的判断"}。'
        ),
    }]
    for index, photo_id in enumerate(photo_ids, start=1):
        photo = photos[photo_id]
        content.append({"type": "text", "text": f"当前第 {index} 格：{photo_id}；文件 {photo['original_name']}。"})
        encoded = base64.b64encode(store.photo_path(metadata["id"], photo_id, thumbnail=True).read_bytes()).decode("ascii")
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}", "detail": "low"}})

    alternatives: dict[str, dict] = {}
    for group in alternative_groups:
        photo = photos[group["photo_ids"][0]]
        photo_id = photo["id"]
        alternatives[photo_id] = {"photo": photo, "group_id": group["id"]}
        quality = photo["quality"]
        content.append({
            "type": "text",
            "text": (
                f"可替换候选 {photo_id}；所属分组 {group['id']}；文件 {photo['original_name']}；"
                f"本地质量 {quality['score']}/100；简洁度 {quality.get('simplicity', '未计算')}。"
            ),
        })
        encoded = base64.b64encode(store.photo_path(metadata["id"], photo_id, thumbnail=True).read_bytes()).decode("ascii")
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}", "detail": "low"}})

    owns_client = client is None
    request_client = client or httpx.Client(timeout=httpx.Timeout(180.0, connect=20.0))
    try:
        parsed = _request_json(request_client, credential, base_url, model, content, max_tokens=4096)
    finally:
        if owns_client:
            request_client.close()

    photo_id = str(parsed.get("candidate_id", ""))
    if photo_id not in alternatives:
        raise BestShotError("AI 服务没有返回有效的替换分组。", code="deepseek_invalid_replacement", status_code=502)
    candidate = alternatives[photo_id]
    return {
        "group_id": candidate["group_id"],
        "photo_id": photo_id,
        "reason": str(parsed.get("reason") or "替换后与相邻画面的差异更明显，整体节奏更协调。")[:200],
        "role": str(parsed.get("role") or "故事补充")[:40],
        "grid_review": str(parsed.get("grid_review") or "已重新检查整体美感与相邻图片的相似度。")[:800],
    }


def _parse_json_content(content: str) -> dict:
    """Accept strict JSON plus the common ```json ... ``` wrapper."""
    cleaned = content.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].lstrip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(cleaned[start:end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("JSON root must be an object")
    return parsed
