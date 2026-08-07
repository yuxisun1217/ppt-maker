import json
from typing import List
from dataclasses import dataclass


@dataclass
class AgendaItem:
    order: int
    time_slot: str
    session_title_cn: str
    session_title_en: str
    speaker_name: str
    host: str          # 主持人/主持嘉宾
    institution: str
    item_type: str     # 'speech' | 'panel' | 'opening' | 'closing'


OCR_PROMPT = (
    '以下文字是从会议日程图片中通过OCR识别提取的。'
    '部分中文字符可能识别不准确，但时间、英文单词和结构信息基本可靠。\n'
    '请根据这些文字还原会议日程中的全部内容，返回JSON数组。\n'
    '每个环节包含：\n'
    '  "order": 顺序号(从1开始，section标题也要编入序号),\n'
    '  "time_slot": "时间段",\n'
    '  "session_title_cn": "中文标题(根据上下文推测，如有英文请翻译)",\n'
    '  "session_title_en": "英文标题(保留原文)",\n'
    '  "speaker_name": "演讲者姓名",\n'
    '  "host": "主持人姓名(panel讨论的主持嘉宾，普通演讲留空)",\n'
    '  "institution": "机构",\n'
    '  "item_type": "类型: section/opening/speech/panel/closing"\n'
    '\n'
    '重要：日程图片中的章节标题（如"泌见前沿，云端共话""渝见前沿，加备精彩"等大字分隔标题）'
    '也必须提取，type设为"section"，只填order和session_title_cn，其他字段留空。\n'
    '\n'
    '返回格式：{"agenda": [...]}\n'
    '注意：严格按时间顺序排列，speaker_name只保留姓名不含职务。\n'
    '\n'
    'OCR文字：\n'
)


def _ocr_image(image_path: str) -> str:
    """Extract text from image using Tesseract OCR with preprocessing."""
    import pytesseract
    from PIL import Image, ImageEnhance

    pytesseract.pytesseract.tesseract_cmd = r'C:/Program Files/Tesseract-OCR/tesseract.exe'
    img = Image.open(image_path)

    img = img.convert('L')
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(2.0)

    text = pytesseract.image_to_string(img, lang='chi_sim+eng')
    if not text.strip() or len(text.strip()) < 20:
        text = pytesseract.image_to_string(img, lang='eng')
    return text


def extract_agenda(image_path: str, api_key: str) -> List[AgendaItem]:
    from utils.deepseek_client import structure_text

    ocr_text = _ocr_image(image_path)
    result = structure_text(ocr_text, OCR_PROMPT, api_key)
    data = json.loads(result)
    items = data.get('agenda', [])

    agenda = []
    for item in items:
        agenda.append(AgendaItem(
            order=int(item.get('order', 0)),
            time_slot=str(item.get('time_slot', '')),
            session_title_cn=str(item.get('session_title_cn', '')),
            session_title_en=str(item.get('session_title_en', '')),
            speaker_name=str(item.get('speaker_name', '')),
            host=str(item.get('host', '')),
            institution=str(item.get('institution', '')),
            item_type=str(item.get('item_type', 'speech')),
        ))
    return agenda
