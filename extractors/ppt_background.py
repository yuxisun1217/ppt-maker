"""从 .pptx 模版中提取首页/内容页背景图（固定代码，无 AI）。

模版背景通常以两种形式存在：
- <p:bg><p:bgPr><a:blipFill> 背景填充（slide / slideLayout / slideMaster）
- 铺满整页的 <p:pic> 图片（很多模版把背景直接作为图片摆放）

通过各 part 的 rels 把 r:embed 解析到 ppt/media/*，并按
slide → 所属 layout → 所属 master 逐级回退查找。
"""
import io
import os
import posixpath
import zipfile
from xml.etree import ElementTree as ET

_NS_A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
_NS_P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
_NS_R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
_TAG_A = '{%s}' % _NS_A
_TAG_P = '{%s}' % _NS_P
_TAG_R = '{%s}' % _NS_R

_SUPPORTED_RASTER = ('.png', '.jpg', '.jpeg')
_CONVERTIBLE = ('.gif', '.bmp', '.tif', '.tiff')
_VECTOR_EXTS = ('.emf', '.wmf')

_ERROR_NO_BG = '未在模版中找到背景图（请确认模版含有背景图片，或直接上传背景图片）'
_ERROR_VECTOR = '模版背景为矢量 EMF/WMF 格式，暂不支持提取，请先转换为图片（PNG/JPG）后上传'


def _rels(zf, part):
    """part 的 rels：{rId: (rel_type, target)}；无 rels 时返回空 dict。"""
    rels_path = posixpath.join(posixpath.dirname(part), '_rels',
                               posixpath.basename(part) + '.rels')
    try:
        data = zf.read(rels_path)
    except KeyError:
        return {}
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return {}
    out = {}
    for rel in root:
        rid = rel.get('Id')
        if rid:
            out[rid] = (rel.get('Type', ''), rel.get('Target', ''))
    return out


def _resolve(zf, part, target):
    """rels target → zip 内规范化路径。"""
    return posixpath.normpath(posixpath.join(posixpath.dirname(part), target))


def _layout_of(zf, slide):
    rels = _rels(zf, slide)
    for _rid, (rtype, target) in rels.items():
        if 'slideLayout' in rtype and target:
            return _resolve(zf, slide, target)
    return None


def _chain(zf, slide):
    """查找链：slide → 所属 layout → 所属 master（去重）。"""
    parts = [slide]
    layout = _layout_of(zf, slide)
    if layout and layout not in parts:
        parts.append(layout)
        rels = _rels(zf, layout)
        for _rid, (rtype, target) in rels.items():
            if 'slideMaster' in rtype and target:
                master = _resolve(zf, layout, target)
                if master not in parts:
                    parts.append(master)
                break
    return parts


def _slides(zf):
    """按文档顺序返回 slide part 列表。"""
    root = ET.fromstring(zf.read('ppt/presentation.xml'))
    rels = _rels(zf, 'ppt/presentation.xml')
    out = []
    sldids = root.findall('.//%ssldId' % _TAG_P)
    for s in sorted(sldids, key=lambda e: int(e.get('id', 0) or 0)):
        rid = s.get(_TAG_R + 'id')
        if rid in rels and rels[rid][1]:
            out.append(_resolve(zf, 'ppt/presentation.xml', rels[rid][1]))
    return out


def _slide_size(root):
    """<p:cSld><p:sldSz> 的 (cx, cy) EMU；缺失返回 None。"""
    sldsz = root.find('.//%ssldSz' % _TAG_P)
    if sldsz is None:
        return None
    try:
        return int(sldsz.get('cx', 0)), int(sldsz.get('cy', 0))
    except (TypeError, ValueError):
        return None


def _deck_size(zf):
    """全文档页面尺寸：python-pptx 只把 sldSz 写在 presentation.xml。"""
    try:
        root = ET.fromstring(zf.read('ppt/presentation.xml'))
    except (KeyError, ET.ParseError):
        return None
    return _slide_size(root)


def _candidates(zf, part, size_hint=None):
    """该 part 的背景图候选 media 路径，按优先级：bg 填充 → 最大整页图片。"""
    try:
        root = ET.fromstring(zf.read(part))
    except (KeyError, ET.ParseError):
        return []
    rels = _rels(zf, part)
    out = []

    def embed_target(elem):
        blip = elem.find('.//%sblip' % _TAG_A)
        if blip is None:
            return None
        rid = blip.get(_TAG_R + 'embed')
        if not rid or rid not in rels or not rels[rid][1]:
            return None
        return _resolve(zf, part, rels[rid][1])

    # 1) 背景填充（<p:bg> 中 r:embed 指向的图片）
    for bg in root.findall('.//%sbg' % _TAG_P):
        t = embed_target(bg)
        if t:
            out.append(t)
            break

    # 2) 回退：铺满整页的 <p:pic>（≥85% 页面尺寸且起点贴近左上角，取最大者）
    size = _slide_size(root) or size_hint
    best, best_area = None, 0
    if size:
        sw, sh = size
        for pic in root.findall('.//%spic' % _TAG_P):
            xfrm = pic.find('.//%sxfrm' % _TAG_A)
            if xfrm is None:
                continue
            off, ext = xfrm.find('%soff' % _TAG_A), xfrm.find('%sext' % _TAG_A)
            if off is None or ext is None:
                continue
            try:
                x, y = int(off.get('x', 0)), int(off.get('y', 0))
                w, h = int(ext.get('cx', 0)), int(ext.get('cy', 0))
            except (TypeError, ValueError):
                continue
            if (w >= sw * 0.85 and h >= sh * 0.85
                    and x <= sw * 0.02 and y <= sh * 0.02
                    and w * h > best_area):
                t = embed_target(pic)
                if t:
                    best, best_area = t, w * h
    if best:
        out.append(best)
    return out


def _convert(data):
    """gif/bmp/tiff → PNG bytes（Pillow 转换）。"""
    from PIL import Image

    img = Image.open(io.BytesIO(data))
    img.load()
    buf = io.BytesIO()
    img.convert('RGBA').save(buf, 'PNG')
    return buf.getvalue()


def _pick(zf, slide, saw_vector, size_hint=None):
    """沿查找链挑第一个可用背景图，返回 (bytes, ext)；无则 None。"""
    for part in _chain(zf, slide):
        for media in _candidates(zf, part, size_hint):
            ext = os.path.splitext(media)[1].lower()
            if ext in _SUPPORTED_RASTER:
                try:
                    return zf.read(media), ext.lstrip('.')
                except KeyError:
                    continue
            if ext in _CONVERTIBLE:
                try:
                    return _convert(zf.read(media)), 'png'
                except (KeyError, OSError, IOError):
                    continue
            if ext in _VECTOR_EXTS:
                saw_vector.append(True)
    return None


def extract_backgrounds(data):
    """从 .pptx（bytes 或本地路径）提取首页/内容页背景图。

    返回 {'home': (bytes, ext), 'content': (bytes, ext)}，ext 为
    'png'/'jpg'/'jpeg'。找不到时抛 ValueError（中文提示）。
    """
    if isinstance(data, (str, os.PathLike)):
        with open(data, 'rb') as f:
            data = f.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(bytes(data)))
    except zipfile.BadZipFile:
        raise ValueError('文件不是有效的 .pptx 文档')
    with zf:
        names = set(zf.namelist())
        if 'ppt/presentation.xml' not in names or '[Content_Types].xml' not in names:
            raise ValueError('文件不是有效的 .pptx 文档')
        slides = _slides(zf)
        if not slides:
            raise ValueError(_ERROR_NO_BG)

        saw_vector = []
        size_hint = _deck_size(zf)
        home = _pick(zf, slides[0], saw_vector, size_hint)

        # 内容页背景：取第一个与首页 layout 不同的 slide（真正的正文版式）
        home_layout = _layout_of(zf, slides[0])
        content_slide = None
        for s in slides[1:]:
            if _layout_of(zf, s) != home_layout:
                content_slide = s
                break
        if content_slide is None and len(slides) > 1:
            content_slide = slides[1]
        content = _pick(zf, content_slide, saw_vector, size_hint) if content_slide else None

        if home is None:
            if saw_vector:
                raise ValueError(_ERROR_VECTOR)
            raise ValueError(_ERROR_NO_BG)
        # 内容页无独立背景时复用首页背景
        if content is None:
            content = home
        return {'home': home, 'content': content}
