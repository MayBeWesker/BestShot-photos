import json

import cv2
import httpx
import numpy as np
import pytest

from app.errors import BestShotError
from app.services.deepseek_selection import replace_moments_photo, select_moments_photos
from app.storage.organizer import OrganizerStore


def make_organizer_project(tmp_path, count: int = 10):
    store = OrganizerStore(tmp_path / "deepseek-project")
    metadata = store.begin("standard")
    for index in range(count):
        image = np.full((90, 120, 3), (20 + index * 8, 90, 180), dtype=np.uint8)
        cv2.putText(image, str(index + 1), (40, 58), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
        ok, encoded = cv2.imencode(".jpg", image)
        assert ok
        store.add_photo(
            metadata,
            data=encoded.tobytes(),
            image=image,
            extension=".jpg",
            original_name=f"candidate-{index + 1}.jpg",
            taken_at=None,
            quality={"score": 90 - index, "sharpness": 80, "exposure": 82, "color": 76, "composition": 79, "reasons": ["画面清晰"]},
        )
    metadata = store.finalize(metadata, [[index] for index in range(count)])
    return store, metadata


def test_deepseek_selection_sends_each_group_best_and_validates_nine(tmp_path):
    store, metadata = make_organizer_project(tmp_path)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        payload = json.loads(request.content)
        calls.append(payload)
        assert payload["model"] == "deepseek-flash"
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["reasoning_effort"] == "none"
        blocks = payload["messages"][0]["content"]
        assert "京都" in blocks[0]["text"]
        images = [block for block in blocks if block["type"] == "image_url"]
        assert len(images) == 10
        assert all(block["image_url"]["url"].startswith("data:image/jpeg;base64,") for block in images)
        if len(calls) == 1:
            assert payload["max_tokens"] == 4096
            content = json.dumps({
                "story_title": "京都秋日散步",
                "story_summary": "从抵达到告别的旅行故事。",
                "beats": [{"position": 1, "purpose": "开场", "visual_preference": "环境远景"}],
                "layout_rationale": "远景开场，人物居中，细节收尾。",
            }, ensure_ascii=False)
            return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

        assert payload["max_tokens"] == 8192
        assert "京都秋日散步" in blocks[0]["text"]
        selected = [
            {"candidate_id": f"photo_{index:03d}", "reason": f"理由 {index}", "role": "旅行记录"}
            for index in range(1, 10)
        ]
        if len(calls) == 2:
            content = "```json\n" + json.dumps({
                "story_title": "京都秋日散步",
                "selected": selected,
                "summary": "九张照片覆盖不同场景。",
                "layout_rationale": "远景、人物与细节交替，最后以安静画面收束。",
                "caption_suggestion": "一路走，一路拍。",
            }, ensure_ascii=False) + "\n```"
            return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

        assert "横向和纵向相邻图片" in blocks[0]["text"]
        content = json.dumps({
            "story_title": "京都秋日散步",
            "selected": selected,
            "summary": "终审后九张照片覆盖不同场景。",
            "grid_review": "相邻照片的主体和视角均有变化，色彩节奏协调。",
            "layout_rationale": "终审后以远景、人物与细节交替排列。",
            "caption_suggestion": "一路走，一路拍。",
        }, ensure_ascii=False)
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = select_moments_photos(
            metadata,
            store=store,
            api_key="test-key",
            client=client,
            context={"theme": "第一次赏枫", "location": "京都", "highlights": "和朋友旅行", "tone": "温柔文艺"},
        )
    assert len(result["selected"]) == 9
    assert len(calls) == 3
    assert result["selected"][0]["photo_id"] == "photo_001"
    assert result["selected"][-1]["group_id"] == "group_009"
    assert result["story_title"] == "京都秋日散步"
    assert result["analysis_candidate_count"] == 10
    assert result["quality_threshold"] == 75
    assert "终审后" in result["layout_rationale"]
    assert "相邻照片" in result["grid_review"]
    assert result["caption_suggestion"] == "一路走，一路拍。"


def test_deepseek_selection_requires_local_key(tmp_path):
    store, metadata = make_organizer_project(tmp_path, count=2)
    with pytest.raises(BestShotError) as raised:
        select_moments_photos(metadata, store=store, api_key="")
    assert raised.value.code == "deepseek_not_configured"


def test_deepseek_empty_content_has_specific_error(tmp_path):
    store, metadata = make_organizer_project(tmp_path, count=2)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"finish_reason": "length", "message": {"content": "", "reasoning_content": "long reasoning"}}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(BestShotError) as raised:
            select_moments_photos(metadata, store=store, api_key="test-key", client=client)
    assert raised.value.code == "deepseek_empty_response"
    assert "finish_reason=length" in raised.value.message


def test_smart_replacement_uses_an_unselected_group_and_reviews_grid(tmp_path):
    store, metadata = make_organizer_project(tmp_path, count=12)
    current = [f"photo_{index:03d}" for index in range(1, 10)]

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        blocks = payload["messages"][0]["content"]
        assert "只替换第 5 格" in blocks[0]["text"]
        assert "不要选择当前九图已有的分组" in blocks[0]["text"]
        images = [block for block in blocks if block["type"] == "image_url"]
        assert len(images) == 12
        content = json.dumps({
            "candidate_id": "photo_011",
            "reason": "与相邻的建筑远景形成内容变化。",
            "role": "旅途细节",
            "grid_review": "替换后相邻图片在主体与视角上更有差异。",
        }, ensure_ascii=False)
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = replace_moments_photo(metadata, current, 5, store=store, api_key="test-key", client=client)

    assert result["photo_id"] == "photo_011"
    assert result["group_id"] == "group_011"
    assert "相邻图片" in result["grid_review"]
