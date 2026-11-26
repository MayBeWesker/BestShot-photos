import json

import httpx
import pytest

from app.errors import BestShotError
from app.services.poetry_catalog import POEMS
from app.services.poetry_selection import recommend_poetry
from test_deepseek_selection import make_organizer_project


def test_poetry_uses_current_images_caption_and_intent_and_trusts_only_catalog(tmp_path):
    store, metadata = make_organizer_project(tmp_path)
    metadata["moments_context"] = {"highlights": "旅行后释然，想慢下来", "location": "湖边"}
    metadata["moments_instruction"] = "减少夜景，保留云和山"
    # Include a photo outside the first nine and use a non-default order.
    ids = ["photo_010", "photo_003", "photo_001"]

    def handler(request):
        blocks = json.loads(request.content)["messages"][0]["content"]
        prompt = blocks[0]["text"]
        assert "旅行后释然，想慢下来" in prompt
        assert "减少夜景，保留云和山" in prompt
        assert "今天终于能松口气" in prompt
        assert "从容平静" in prompt
        assert "情绪相反" in prompt
        images = [block["image_url"]["url"] for block in blocks if block["type"] == "image_url"]
        assert len(images) == len(ids)
        import base64
        for photo_id, image in zip(ids, images):
            assert base64.b64decode(image.split(",", 1)[1]) == store.photo_path(metadata["id"], photo_id, thumbnail=True).read_bytes()
        content = {"recommendations": [
            {"poem_id": "invented", "reason": "看起来合适", "matched_ranks": [1]},
            {"poem_id": "clouds", "verse": "模型杜撰的句子", "author": "错误作者", "source_url": "https://bad.example",
             "reason": "山间云气呼应慢下来、从容平静的心情。", "matched_ranks": [1, 1, 3, 99, True]},
            {"poem_id": "clouds", "reason": "重复", "matched_ranks": [2]},
        ]}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content)}}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = recommend_poetry(metadata, ids, "今天终于能松口气", "从容平静", store=store, api_key="test", client=client)
    assert len(result["recommendations"]) == 1
    entry = result["recommendations"][0]
    assert entry["verse"] == "行到水穷处，坐看云起时。"
    assert entry["author"] == "王维"
    assert entry["matched_ranks"] == [1, 3]
    assert entry["source_url"].startswith("https://zh.wikisource.org/")


@pytest.mark.parametrize("entries", [[], [{"poem_id": "fake", "reason": "假的", "matched_ranks": [1]}], "invalid"])
def test_poetry_does_not_fabricate_fallbacks(tmp_path, entries):
    store, metadata = make_organizer_project(tmp_path, 2)
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"recommendations": entries})}}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        if entries == []:
            assert recommend_poetry(metadata, ["photo_001"], "", store=store, api_key="test", client=client) == {"recommendations": []}
        else:
            with pytest.raises(BestShotError, match="诗句"):
                recommend_poetry(metadata, ["photo_001"], "", store=store, api_key="test", client=client)


def test_poetry_rejects_missing_or_duplicate_photos_before_request(tmp_path):
    store, metadata = make_organizer_project(tmp_path, 2)
    for ids in ([], ["photo_001", "photo_001"], ["not-a-photo"]):
        with pytest.raises(BestShotError) as raised:
            recommend_poetry(metadata, ids, "", store=store, api_key="test")
        assert raised.value.code == "invalid_poetry_photos"
    assert len({entry["id"] for entry in POEMS}) == len(POEMS)
