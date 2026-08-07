import json
import base64
import urllib.request
import urllib.error
import urllib.parse
from typing import List
from dataclasses import dataclass


OCR_SPACE_URL = 'https://api.ocr.space/parse/image'


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


def _ocr_image(image_path: str, ocr_api_key: str) -> str:
    """Extract text from image using OCR.space API."""
    with open(image_path, 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode('utf-8')

    payload = urllib.parse.urlencode({
        'base64Image': f'data:image/png;base64,{img_b64}',
        'language': 'chs',
        'isTable': 'true',
        'OCREngine': '3',
    }).encode('utf-8')

    req = urllib.request.Request(OCR_SPACE_URL, data=payload, method='POST')
    req.add_header('apikey', ocr_api_key)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='ignore')
        raise RuntimeError(f'OCR.space API 错误 ({e.code}): {body}') from e

    if data.get('IsErroredOnProcessing', True):
        err_msg = data.get('ErrorMessage', ['Unknown error'])
        raise RuntimeError(f'OCR.space 处理失败: {err_msg}')

    results = data.get('ParsedResults', [])
    if not results:
        raise RuntimeError('OCR.space 未返回识别结果')

    text = results[0].get('ParsedText', '')
    if not text.strip():
        raise RuntimeError('OCR.space 返回空文本')
    return text


def extract_agenda(image_path: str, api_key: str, ocr_api_key: str = '') -> List[AgendaItem]:
    from utils.deepseek_client import structure_text

    if not ocr_api_key:
        raise RuntimeError('未配置 OCR.space API Key，请先在注册时填写或在账户设置中更新')

    ocr_text = _ocr_image(image_path, ocr_api_key)
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
