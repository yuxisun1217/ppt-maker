import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass, field

MIN_PHOTO_HEIGHT_CM = 3.0
MIN_ASPECT_RATIO = 0.4
MAX_ASPECT_RATIO = 2.5


def _image_height_cm(img_path: str) -> float:
    """Return image physical height in cm. Uses DPI if available, else assumes 200 DPI."""
    try:
        from PIL import Image
        img = Image.open(img_path)
        dpi = img.info.get('dpi', None)
        h_px = img.height
        if dpi and dpi[1] and dpi[1] > 0:
            return h_px / dpi[1] * 2.54
        return h_px / 200 * 2.54
    except Exception:
        return 0.0


def _is_photo(img_path: str) -> bool:
    """Check if image looks like a photo (reasonable aspect ratio + min height)."""
    try:
        from PIL import Image
        img = Image.open(img_path)
        w, h = img.size
        ratio = w / h if h > w else h / w
        if ratio < MIN_ASPECT_RATIO or ratio > MAX_ASPECT_RATIO:
            return False
        return _image_height_cm(img_path) >= MIN_PHOTO_HEIGHT_CM
    except Exception:
        return False


_SESSION_PHOTO_DIR = None


def _get_session_photo_dir():
    global _SESSION_PHOTO_DIR
    if _SESSION_PHOTO_DIR is None or not os.path.exists(_SESSION_PHOTO_DIR):
        _SESSION_PHOTO_DIR = tempfile.mkdtemp(prefix='ppt_speaker_photos_')
    return _SESSION_PHOTO_DIR


@dataclass
class Speaker:
    name: str
    photo_path: str = ''
    bio: str = ''
    institution: str = ''
    title: str = ''


def _extract_images_from_docx(file_path: str, output_dir: str) -> List[str]:
    """Extract embedded images from a DOCX file. Returns list of image paths."""
    from docx import Document

    try:
        doc = Document(file_path)
    except Exception:
        return _extract_images_from_docx_zip_fallback(file_path, output_dir)

    paths = []
    for i, rel in enumerate(doc.part.rels.values()):
        if 'image' in rel.reltype:
            ext = rel.target_ref.split('.')[-1].split('?')[0]
            if ext not in ('jpeg', 'jpg', 'png', 'gif', 'bmp'):
                ext = 'png'
            img_path = os.path.join(output_dir, f'docx_img_{i}.{ext}')
            try:
                with open(img_path, 'wb') as f:
                    f.write(rel.target_part.blob)
                paths.append(img_path)
            except Exception:
                continue
    return paths


def _extract_images_from_docx_zip_fallback(file_path: str, output_dir: str) -> List[str]:
    """Fallback: extract images from DOCX ZIP directly, skipping corrupt entries."""
    import zipfile

    paths = []
    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            for i, name in enumerate(zf.namelist()):
                if not name.startswith('word/media/'):
                    continue
                try:
                    data = zf.read(name)
                except Exception:
                    continue
                ext = name.rsplit('.', 1)[-1].lower()
                if ext not in ('jpeg', 'jpg', 'png', 'gif', 'bmp'):
                    ext = 'png'
                img_path = os.path.join(output_dir, f'docx_img_{i}.{ext}')
                with open(img_path, 'wb') as f:
                    f.write(data)
                paths.append(img_path)
    except Exception:
        pass
    return paths


def _extract_images_from_pptx(file_path: str, output_dir: str) -> List[str]:
    """Extract embedded images from a PPTX file. Returns list of image paths."""
    from pptx import Presentation

    prs = Presentation(file_path)
    paths = []
    img_idx = 0
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.shape_type == 13:  # PICTURE
                ext = shape.image.content_type.split('/')[-1]
                if ext == 'jpeg':
                    ext = 'jpg'
                img_path = os.path.join(output_dir, f'pptx_img_{img_idx}.{ext}')
                with open(img_path, 'wb') as f:
                    f.write(shape.image.blob)
                paths.append(img_path)
                img_idx += 1
    return paths


def _extract_images_from_pdf(file_path: str, output_dir: str) -> List[str]:
    """Try to extract embedded images from a PDF file. Empty if none."""
    # PyPDF2 can't reliably extract images, return empty
    return []


def _extract_text_from_docx(file_path: str) -> str:
    from docx import Document
    try:
        doc = Document(file_path)
    except Exception:
        return _extract_text_from_docx_zip_fallback(file_path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return '\n'.join(paragraphs)


def _extract_text_from_docx_zip_fallback(file_path: str) -> str:
    """Fallback: extract text from word/document.xml directly, tolerating corrupt media."""
    import zipfile
    from xml.etree import ElementTree
    import re

    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            xml_bytes = zf.read('word/document.xml')
    except Exception:
        raise RuntimeError(f'无法读取DOCX文件: {file_path}')

    root = ElementTree.fromstring(xml_bytes)
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    texts = []
    for t in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'):
        if t.text:
            texts.append(t.text)
    # Join with newlines at paragraph breaks
    full = ''.join(texts)
    # Split on paragraph markers
    paragraphs = [p.strip() for p in re.split(r'\n\s*', full) if p.strip()]
    return '\n'.join(paragraphs)


def _extract_text_from_pptx(file_path: str) -> str:
    from pptx import Presentation
    prs = Presentation(file_path)
    texts = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    t = para.text.strip()
                    if t:
                        texts.append(t)
    return '\n'.join(texts)


def _extract_text_from_pdf(file_path: str) -> str:
    from PyPDF2 import PdfReader
    reader = PdfReader(file_path)
    texts = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            texts.append(t)
    return '\n'.join(texts)


def extract_speaker(file_path: str, api_key: str) -> Speaker:
    """
    Extract speaker info from a file (docx/pptx/pdf).
    Uses python libraries for text/image extraction, then DeepSeek to structure.
    """
    ext = Path(file_path).suffix.lower()
    work_dir = tempfile.mkdtemp(prefix='spk_')
    import re
    stem = Path(file_path).stem
    # Pattern: optional prefix (number/underscore) + Chinese name + suffix
    name_from_file = re.sub(r'^[\d_]+', '', stem)
    name_from_file = re.sub(r'(简介|简历|介绍|资料|个人|履历)$', '', name_from_file)
    if not name_from_file:
        name_from_file = stem

    try:
        # Extract text
        if ext == '.docx':
            raw_text = _extract_text_from_docx(file_path)
            img_paths = _extract_images_from_docx(file_path, work_dir)
        elif ext == '.pptx':
            raw_text = _extract_text_from_pptx(file_path)
            img_paths = _extract_images_from_pptx(file_path, work_dir)
        elif ext == '.pdf':
            raw_text = _extract_text_from_pdf(file_path)
            img_paths = _extract_images_from_pdf(file_path, work_dir)
        else:
            raise ValueError(f'不支持的文件格式: {ext}')

        if not raw_text:
            raise RuntimeError(f'未能从文件中提取到文字: {file_path}')

        # Use DeepSeek to structure the text
        from utils.deepseek_client import structure_text

        prompt = (
            '请从以下文本中识别演讲者的信息，返回JSON格式：\n'
            '{"name": "姓名", "institution": "所属医院", '
            '"bio": "履历列表"}\n'
            '\n'
            f'提示：文件名为「{stem}」，该演讲者的姓名很可能是「{name_from_file}」。\n'
            '如果文本中找不到明确的姓名，请使用提示中的姓名。\n'
            'name字段只返回姓名（2-3个汉字），不要包含职务和头衔。\n'
            'institution字段从文本中提取医院名称，如"重庆大学附属肿瘤医院"（只保留一个最完整的医院名称）。\n'
            'bio字段返回JSON字符串数组，每项为一行履历。\n'
            '数组内容按语义分类整理：\n'
            '1. 学位、职称、导师资格合并为第一项，如"医学博士、主任医师、硕士生导师"\n'
            '2. 科室职务必须保留完整医院名称，如"重庆医科大学附属第一医院泌尿外科主任"\n'
            '3. 以国家（中国/中华/全国/美国/欧洲）、省（省/直辖市）等地区开头的学会任职，每个单独一项\n'
            '4. 访问学者、获奖等经历类各单独一项\n'
            '每项不超过30个字，去掉多余的连接词和标点。\n'
            '如果文本中包含多个人的信息，只提取主要人物。'
        )
        result = structure_text(raw_text, prompt, api_key)
        import json
        data = json.loads(result)

        # Pick the largest qualifying photo (height >= 3cm), copy to session temp dir
        photo_path = ''
        qualifying = [(p, os.path.getsize(p)) for p in img_paths if _is_photo(p)]
        if qualifying:
            best = max(qualifying, key=lambda x: x[1])[0]
            name = data.get('name', name_from_file)
            ext = os.path.splitext(best)[1]
            safe_name = name.replace('/', '_').replace('\\', '_')
            dest = os.path.join(_get_session_photo_dir(), f'{safe_name}{ext}')
            shutil.copy2(best, dest)
            photo_path = dest

        bio = data.get('bio', '')
        if isinstance(bio, list):
            bio = '\n'.join(bio)

        return Speaker(
            name=data.get('name', ''),
            photo_path=photo_path,
            bio=bio,
            institution=data.get('institution', ''),
            title='教授',
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
