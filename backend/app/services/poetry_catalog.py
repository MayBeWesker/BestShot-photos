"""Curated public-domain excerpts, checked against source editions on 2026-11-26.

Only original verse is transcribed (simplified characters, modern punctuation).
Sources use fixed Wikisource revisions; editorial notes are not reproduced.
Model output may select IDs, but can never supply or overwrite quoted verse.
"""


def _entry(id: str, author: str, era: str, title: str, verse: str, revision: int, mood: str) -> dict:
    return dict(id=id, author=author, era=era, title=title, verse=verse,
                source_url=f"https://zh.wikisource.org/w/index.php?oldid={revision}", mood=mood)


POEMS = [
    _entry("mountain-rain", "王维", "唐", "山居秋暝", "空山新雨后，天气晚来秋。", 12969969, "雨后山林、秋日清新、宁静"),
    _entry("pine-moon", "王维", "唐", "山居秋暝", "明月松间照，清泉石上流。", 12969969, "松林月夜、清泉、清幽恬静"),
    _entry("clouds", "王维", "唐", "终南别业", "行到水穷处，坐看云起时。", 1982349, "山水云起、独行、随遇而安、从容"),
    _entry("bamboo-moon", "王维", "唐", "竹里馆", "深林人不知，明月来相照。", 2328978, "竹林月夜、独处、自在安静"),
    _entry("forest-light", "王维", "唐", "鹿柴", "返景入深林，复照青苔上。", 12232893, "林间夕照、青苔、幽静"),
    _entry("village-trees", "孟浩然", "唐", "过故人庄", "绿树村边合，青山郭外斜。", 2691920, "田园村落、绿树青山、亲切闲适"),
    _entry("friends-table", "孟浩然", "唐", "过故人庄", "开筵面场圃，把酒话桑麻。", 2691920, "朋友相聚、乡间餐饮、温暖日常"),
    _entry("new-village", "陆游", "宋", "游山西村", "山重水复疑无路，柳暗花明又一村。", 902696, "山水村落、转角发现、希望惊喜"),
    _entry("village-feast", "陆游", "宋", "游山西村", "莫笑农家腊酒浑，丰年留客足鸡豚。", 902696, "农家美食、款待、丰足热情"),
    _entry("light-boat", "李白", "唐", "早发白帝城", "两岸猿声啼不尽，轻舟已过万重山。", 12232697, "江河舟行、群山、轻快释然"),
    _entry("gentle-rain", "杜甫", "唐", "春夜喜雨", "随风潜入夜，润物细无声。", 2261431, "春雨夜色、温柔润泽、细腻欣喜"),
    _entry("river-lamp", "杜甫", "唐", "春夜喜雨", "野径云俱黑，江船火独明。", 2261431, "夜雨江船、灯火、幽暗中明亮"),
    _entry("rain-walk", "苏轼", "宋", "定风波·莫听穿林打叶声", "莫听穿林打叶声，何妨吟啸且徐行。", 8732900, "林间风雨、步行、旷达从容"),
    _entry("lake-weather", "苏轼", "宋", "饮湖上初晴后雨·其二", "水光潋滟晴方好，山色空蒙雨亦奇。", 8732097, "西湖湖光山色、晴雨皆美、欣赏愉悦"),
    _entry("lotus-summer", "杨万里", "宋", "晓出净慈寺送林子方", "接天莲叶无穷碧，映日荷花别样红。", 2391475, "夏日荷花莲叶、明亮热烈、生机"),
    _entry("moon-longing", "张九龄", "唐", "望月怀远", "海上生明月，天涯共此时。", 2273256, "海上月亮、异地思念、共同牵挂"),
    _entry("farewell-wine", "王维", "唐", "送元二使安西", "劝君更尽一杯酒，西出阳关无故人。", 12232830, "送别友人、酒宴、不舍；不适合单纯欢快聚餐"),
]
