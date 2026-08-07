import os
import tempfile
from pathlib import Path


def convert_to_pdf(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    if ext == '.pdf':
        return file_path
    if ext not in ('.docx', '.pptx'):
        raise ValueError(f'不支持的文件格式: {ext}')

    output_dir = tempfile.mkdtemp(prefix='pptmaker_')
    base_name = Path(file_path).stem
    output_path = os.path.join(output_dir, f'{base_name}.pdf')

    try:
        if ext == '.docx':
            _docx_to_pdf(file_path, output_path)
        elif ext == '.pptx':
            _pptx_to_pdf(file_path, output_path)
        if not os.path.exists(output_path):
            raise RuntimeError('转换未生成 PDF 文件')
        return output_path
    except Exception as e:
        raise RuntimeError(f'转换失败 ({file_path}): {e}') from e


def _docx_to_pdf(input_path: str, output_path: str):
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    word = None
    try:
        word = win32com.client.Dispatch('Word.Application')
        word.Visible = False
        word.DisplayAlerts = 0
        doc = word.Documents.Open(os.path.abspath(input_path), ReadOnly=True)
        doc.SaveAs(os.path.abspath(output_path), FileFormat=17)  # 17 = wdFormatPDF
        doc.Close(SaveChanges=0)
    finally:
        if word:
            try:
                word.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


def _pptx_to_pdf(input_path: str, output_path: str):
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    ppt = None
    try:
        ppt = win32com.client.Dispatch('PowerPoint.Application')
        ppt.Visible = False
        ppt.DisplayAlerts = 0
        pres = ppt.Presentations.Open(os.path.abspath(input_path), WithWindow=False)
        pres.SaveAs(os.path.abspath(output_path), 32)  # 32 = ppSaveAsPDF
        pres.Close()
    finally:
        if ppt:
            try:
                ppt.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()
