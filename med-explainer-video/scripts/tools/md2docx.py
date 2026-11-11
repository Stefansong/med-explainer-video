#!/usr/bin/env python3
"""Markdown → Word（.docx）：给用户看的修订稿、台词本都出一份 docx（不依赖 pandoc，Windows / macOS 通用）。
只支持本技能文稿用到的写法：# 标题、段落、**粗体**、`代码`、- 列表、1. 列表、| 表格 |、> 引用、--- 分隔线。
  python tools/md2docx.py <in.md> [out.docx]"""
import re, sys
from pathlib import Path

def _runs(par, text, size=None):
    """把一行里的 **粗体**、`代码`、*斜体* 拆成 run"""
    from docx.shared import Pt
    for part in re.split(r'(\*\*.+?\*\*|`[^`]+`|\*[^*\s][^*]*\*)', text):
        if not part: continue
        if part.startswith('**') and part.endswith('**'): r = par.add_run(part[2:-2]); r.bold = True
        elif part.startswith('`') and part.endswith('`'): r = par.add_run(part[1:-1]); r.font.name = 'Consolas'
        elif part.startswith('*') and part.endswith('*') and len(part) > 2: r = par.add_run(part[1:-1]); r.italic = True
        else: r = par.add_run(part)
        if size: r.font.size = Pt(size)

def convert(md_path, out_path=None):
    try:
        from docx import Document
        from docx.shared import Pt, Cm
        from docx.oxml.ns import qn
    except ImportError:
        return None   # 没装 python-docx：调用方只出 md
    md_path = Path(md_path); out_path = Path(out_path) if out_path else md_path.with_suffix('.docx')
    doc = Document()
    for sec in doc.sections: sec.left_margin = sec.right_margin = Cm(2.2); sec.top_margin = sec.bottom_margin = Cm(2.2)
    st = doc.styles['Normal']; st.font.name = 'Arial'; st.font.size = Pt(11)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')   # 中文字体：Windows 用微软雅黑，别的系统 Word 会自动替换成相近的黑体
    lines = md_path.read_text(encoding='utf-8').splitlines(); i = 0
    while i < len(lines):
        ln = lines[i]; s = ln.strip()
        if not s: i += 1; continue
        m = re.match(r'^(#{1,4})\s+(.*)$', s)
        if m:
            h = doc.add_heading(level=min(len(m.group(1)), 4)); _runs(h, m.group(2))
            for r in h.runs: r.font.name = 'Arial'; r._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
            i += 1; continue
        if s.startswith('|') and i + 1 < len(lines) and re.match(r'^\s*\|?\s*:?-{2,}', lines[i + 1]):   # 表格
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                if not re.match(r'^\s*\|?[\s:\-|]+\|?\s*$', lines[i]): rows.append([c.strip() for c in re.split(r'(?<!\\)\|', lines[i].strip().strip('|'))])
                i += 1
            n = max(len(r) for r in rows); t = doc.add_table(rows=len(rows), cols=n); t.style = 'Table Grid'
            for ri, row in enumerate(rows):
                for ci in range(n):
                    cell = t.cell(ri, ci); p = cell.paragraphs[0]; _runs(p, row[ci] if ci < len(row) else '', 10)
                    if ri == 0:
                        for r in p.runs: r.bold = True
            doc.add_paragraph(); continue
        if re.match(r'^-{3,}$', s): doc.add_paragraph('—' * 20); i += 1; continue
        m = re.match(r'^(\s*)[-*]\s+(.*)$', ln)
        if m: p = doc.add_paragraph(style='List Bullet 2' if len(m.group(1)) >= 2 else 'List Bullet'); _runs(p, m.group(2)); i += 1; continue
        m = re.match(r'^\s*\d+[.、)]\s+(.*)$', ln)
        if m: p = doc.add_paragraph(style='List Number'); _runs(p, m.group(1)); i += 1; continue
        if s.startswith('>'): p = doc.add_paragraph(); p.paragraph_format.left_indent = Cm(0.8); _runs(p, s.lstrip('> ')); i += 1; continue
        if s.startswith('```'):
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'): p = doc.add_paragraph(); r = p.add_run(lines[i]); r.font.name = 'Consolas'; r.font.size = Pt(9.5); i += 1
            i += 1; continue
        p = doc.add_paragraph(); _runs(p, s.rstrip()); i += 1
    doc.save(out_path); return out_path

if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    out = convert(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print('→', out) if out else sys.exit('没装 python-docx（python -m pip install python-docx）')
