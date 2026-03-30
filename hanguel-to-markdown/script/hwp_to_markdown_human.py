#!/usr/bin/env python3
"""
HWP / HWPX (한글 워드프로세서) → Markdown 변환기

파이프라인:
  HWP  → pyhwp + lxml XSLT → XHTML → markdownify → Markdown
  HWPX → 직접 XML 파싱              → Markdown

사용법:
    python hwp_to_markdown.py input.hwp  [output.md] [--image-dir images]
    python hwp_to_markdown.py input.hwpx [output.md] [--image-dir images]

필요 패키지:
    pip install pyhwp lxml Pillow beautifulsoup4 markdownify
"""

import os
import sys
import io
import re
import shutil
import tempfile
import zipfile
import argparse
import warnings
from pathlib import Path

# Windows 터미널 UTF-8 출력 보장
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


# ─────────────────────────────────────────────────────────────
# 의존성 확인
# ─────────────────────────────────────────────────────────────
REQUIRED = {
    "pyhwp":          "hwp5",
    "lxml":           "lxml",
    "Pillow":         "PIL",
    "beautifulsoup4": "bs4",
    "markdownify":    "markdownify",
}

def check_dependencies() -> list[str]:
    missing = []
    for pkg, import_name in REQUIRED.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg)
    return missing


# ─────────────────────────────────────────────────────────────
# 공통 후처리
# ─────────────────────────────────────────────────────────────
def _postprocess(md: str) -> str:
    md = re.sub(r"\n{3,}", "\n\n", md)
    lines = []
    for line in md.splitlines():
        if not line.startswith("|"):
            line = line.rstrip()
        lines.append(line)
    return "\n".join(lines).strip() + "\n"


# ═════════════════════════════════════════════════════════════
# HWP 변환 (pyhwp + lxml XSLT → XHTML → markdownify)
# ═════════════════════════════════════════════════════════════
def hwp_to_html_dir(hwp_path: Path, out_dir: Path) -> Path:
    from hwp5.storage.ole import OleStorage
    from hwp5.xmlmodel import Hwp5File
    from hwp5.hwp5html import HTMLTransform
    from hwp5.plat._lxml import xslt_compile

    out_dir.mkdir(parents=True, exist_ok=True)
    storage = OleStorage(str(hwp_path))
    hwp5file = Hwp5File(storage)
    transform = HTMLTransform(xslt_compile=xslt_compile)
    transform.transform_hwp5_to_dir(hwp5file, str(out_dir))
    return out_dir / "index.xhtml"


def html_to_markdown(html_path: Path, image_dir: Path) -> str:
    from bs4 import BeautifulSoup
    import markdownify

    html_text = html_path.read_text(encoding="utf-8", errors="replace")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        soup = BeautifulSoup(html_text, features="xml")

    image_dir.mkdir(parents=True, exist_ok=True)
    for img_tag in soup.find_all("img"):
        src = img_tag.get("src", "")
        if not src:
            continue
        src_path = html_path.parent / src
        if src_path.exists():
            dest = image_dir / src_path.name
            shutil.copy2(src_path, dest)
            img_tag["src"] = f"{image_dir.name}/{src_path.name}"

    body = soup.find("body") or soup
    md = markdownify.markdownify(
        str(body),
        heading_style="ATX",
        bullets="-",
        newline_style="backslash",
        strip=["script", "style"],
    )
    return _postprocess(md)


def convert_hwp(hwp_path: Path, out_path: Path, image_dir: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="hwp2md_") as tmp_str:
        tmp_dir = Path(tmp_str)
        print("[1/3] HWP → HTML 변환 중...")
        html_path = hwp_to_html_dir(hwp_path, tmp_dir)
        if not html_path.exists():
            raise FileNotFoundError(f"HTML 변환 결과 없음: {html_path}")
        print("[2/3] HTML → Markdown 변환 중...")
        md = html_to_markdown(html_path, image_dir)
        print("[3/3] Markdown 저장 중...")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md, encoding="utf-8")


# ═════════════════════════════════════════════════════════════
# HWPX 변환 (ZIP XML 직접 파싱)
# ═════════════════════════════════════════════════════════════
HP   = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HP10 = "http://www.hancom.co.kr/hwpml/2016/paragraph"
HH   = "http://www.hancom.co.kr/hwpml/2011/head"

# 전각 공백 / 기타 인라인 요소 → 문자 매핑
INLINE_ELEM_TEXT: dict[str, str] = {
    "fwSpace":    "\u3000",   # 전각 공백
    "lineBreak":  "\n",
    "tab":        "\t",
    "nbSpace":    "\u00a0",   # Non-breaking space
}

# 제목 스타일 이름 → 레벨
HEADING_STYLE_MAP = {
    "제목1": 1, "제목2": 2, "제목3": 3, "제목4": 4, "제목5": 5, "제목6": 6,
    "Heading1": 1, "Heading2": 2, "Heading3": 3,
    "heading1": 1, "heading2": 2, "heading3": 3,
}


class HwpxParser:
    """HWPX ZIP 파일을 파싱하여 Markdown(+HTML 테이블) 문자열로 변환"""

    def __init__(self, hwpx_path: Path, image_dir: Path):
        self.hwpx_path = hwpx_path
        self.image_dir = image_dir
        self._style_map: dict[str, str] = {}
        self._image_counter = 0

    # ── 진입점 ──────────────────────────────────────
    def convert(self) -> str:
        with zipfile.ZipFile(self.hwpx_path) as zf:
            self._load_styles(zf)
            sections = sorted(
                [n for n in zf.namelist() if re.match(r"Contents/section\d+\.xml", n)]
            )
            blocks: list[str] = []
            for sec_name in sections:
                xml_bytes = zf.read(sec_name)
                root = self._parse_xml(xml_bytes)
                self._walk_section(root, blocks, zf)

        md = "\n\n".join(b for b in blocks if b)
        return _postprocess(md)

    # ── 스타일 로드 ──────────────────────────────────
    def _load_styles(self, zf: zipfile.ZipFile) -> None:
        if "Contents/header.xml" not in zf.namelist():
            return
        root = self._parse_xml(zf.read("Contents/header.xml"))
        for elem in root.iter():
            if self._local(elem) == "style":
                sid = elem.get("id", "")
                name = elem.get("name", "")
                if sid:
                    self._style_map[sid] = name

    # ── XML 파싱 ─────────────────────────────────────
    @staticmethod
    def _parse_xml(data: bytes):
        from lxml import etree
        return etree.fromstring(data)

    @staticmethod
    def _local(elem) -> str:
        return elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

    # ── <t> 요소 전체 텍스트 추출 ────────────────────
    def _t_text(self, t_elem) -> str:
        """
        <hp:t>텍스트<hp:fwSpace/>나머지</hp:t> 구조에서
        자식 요소(fwSpace 등)의 tail 텍스트까지 모두 수집한다.
        """
        parts: list[str] = []
        if t_elem.text:
            parts.append(t_elem.text)
        for child in t_elem:
            tag = self._local(child)
            # 인라인 특수 문자 요소
            parts.append(INLINE_ELEM_TEXT.get(tag, ""))
            # 요소 뒤에 오는 텍스트 (tail)
            if child.tail:
                parts.append(child.tail)
        return "".join(parts)

    # ── 섹션 순회 ────────────────────────────────────
    def _walk_section(self, root, blocks: list[str], zf: zipfile.ZipFile) -> None:
        """HWPX 구조: sec > p > run > (t | tbl | ctrl)"""
        for child in root:
            tag = self._local(child)
            if tag == "p":
                para_blocks = self._parse_paragraph_blocks(child)
                blocks.extend(para_blocks)
            elif tag == "tbl":
                html = self._parse_table_html(child)
                if html:
                    blocks.append(html)
            elif tag in ("subList", "sec"):
                self._walk_section(child, blocks, zf)

    # ── 단락 파싱 ────────────────────────────────────
    def _parse_paragraph_blocks(self, p_elem) -> list[str]:
        heading_level = self._heading_level(p_elem)
        result: list[str] = []
        text_parts: list[str] = []

        def flush_text():
            text = "".join(text_parts).strip()
            text_parts.clear()
            if not text:
                return
            if heading_level:
                result.append(f"{'#' * heading_level} {text}")
            else:
                result.append(text)

        for child in p_elem:
            tag = self._local(child)
            if tag == "run":
                for item in self._parse_run_items(child):
                    if isinstance(item, str):
                        text_parts.append(item)
                    else:
                        flush_text()
                        html = self._parse_table_html(item)
                        if html:
                            result.append(html)
            elif tag == "lineBreak":
                text_parts.append("\n")

        flush_text()
        return result

    def _parse_run_items(self, run_elem):
        """run 내부를 순서대로 순회: 텍스트→str, 테이블→element"""
        char_pr = run_elem.find(f"{{{HP}}}charPr")
        bold = italic = False
        if char_pr is not None:
            bold   = char_pr.get("bold",   "0") in ("1", "true")
            italic = char_pr.get("italic", "0") in ("1", "true")

        for child in run_elem:
            tag = self._local(child)
            if tag == "t":
                text = self._t_text(child)    # ← fwSpace/tail 포함 수집
                stripped = text.strip()
                if stripped and (bold or italic):
                    if bold and italic:
                        text = text.replace(stripped, f"***{stripped}***")
                    elif bold:
                        text = text.replace(stripped, f"**{stripped}**")
                    else:
                        text = text.replace(stripped, f"*{stripped}*")
                yield text
            elif tag == "tbl":
                yield child
            elif tag == "lineBreak":
                yield "\n"
            elif tag == "ctrl":
                for sub in child.iter():
                    if self._local(sub) == "t":
                        yield self._t_text(sub)

    def _heading_level(self, p_elem) -> int:
        style_id = p_elem.get("styleIDRef", "")
        style_name = self._style_map.get(style_id, "")
        for key, level in HEADING_STYLE_MAP.items():
            if key in style_name:
                return level
        return 0

    # ── 테이블 → HTML ────────────────────────────────
    def _parse_table_html(self, tbl_elem) -> str:
        """
        테이블 구조를 분석하여:
        1) 단순 표(병합/중첩 없음) -> 순수 Markdown 표로 렌더링 (토큰 대폭 절감)
        2) 복잡한 표(병합/중첩 존재) -> Minified HTML로 렌더링
        """
        is_complex = False
        rows = []
        
        # 테이블 복잡도 검사 및 데이터 추출
        for child in tbl_elem:
            if self._local(child) == "tr":
                cells = []
                for tc in child:
                    if self._local(tc) == "tc":
                        # 병합(Span) 검사
                        span = tc.find(f"{{{HP}}}cellSpan")
                        if span is not None:
                            c_span = int(span.get("colSpan", 1))
                            r_span = int(span.get("rowSpan", 1))
                            if c_span > 1 or r_span > 1:
                                is_complex = True
                        
                        # 중첩 테이블 검사 (내부에 tbl 요소가 있는지)
                        if tc.find(f".//{{{HP}}}tbl") is not None:
                            is_complex = True
                            
                        cells.append(tc)
                rows.append(cells)

        if not rows:
            return ""

        # 1x1 테이블이면 그냥 텍스트로 풀어서 반환 (인용구 스타일 적용)
        if len(rows) == 1 and len(rows[0]) == 1 and not is_complex:
            content = self._parse_cell_content(rows[0][0])
            return f"\n> {content.replace('<br>', ' ')}\n"

        # 단순 표 -> Markdown 테이블로 변환
        if not is_complex:
            md_rows = []
            for i, row in enumerate(rows):
                # HTML <br>을 마크다운 안에서 깨지지 않게 띄어쓰기나 쉼표로 대체
                cell_texts = [self._parse_cell_content(tc).replace("<br>", " ") for tc in row]
                md_rows.append("| " + " | ".join(cell_texts) + " |")
                
                # 첫 줄(헤더) 작성 후 구분선 추가
                if i == 0:
                    md_rows.append("|" + "|".join(["---"] * len(row)) + "|")
            
            return "\n".join(md_rows) + "\n"

        # 복잡한 표 -> Minified HTML로 변환 (공백, 줄바꿈 제거로 토큰 최소화)
        html_rows = []
        for tr in tbl_elem:
            if self._local(tr) == "tr":
                html_rows.append(self._parse_row_html(tr))
                
        return f"<table>{''.join(html_rows)}</table>"

    def _parse_row_html(self, tr_elem) -> str:
        cell_htmls = []
        for child in tr_elem:
            if self._local(child) == "tc":
                cell_htmls.append(self._parse_cell_html(child))
        return "<tr>" + "".join(cell_htmls) + "</tr>"

    def _parse_cell_html(self, tc_elem) -> str:
        span_elem = tc_elem.find(f"{{{HP}}}cellSpan")
        colspan = rowspan = 1
        if span_elem is not None:
            colspan = int(span_elem.get("colSpan", 1))
            rowspan = int(span_elem.get("rowSpan", 1))

        attrs = ""
        # 따옴표 제거 (예: colspan="2" -> colspan=2) 로 토큰 추가 절감
        if colspan > 1:
            attrs += f' colspan={colspan}'
        if rowspan > 1:
            attrs += f' rowspan={rowspan}'

        content = self._parse_cell_content(tc_elem)
        return f"<td{attrs}>{content}</td>"

    def _parse_cell_content(self, tc_elem) -> str:
        html_parts = []
        for child in tc_elem:
            tag = self._local(child)
            if tag == "subList":
                html_parts.extend(self._sublist_to_html(child))
            elif tag == "p":
                html_parts.extend(self._para_to_html_parts(child))
            elif tag == "tbl":
                html_parts.append(self._parse_table_html(child))

        result = "".join(html_parts)
        result = re.sub(r"(<br\s*/?>)+", "<br>", result)
        return result.strip()

    def _sublist_to_html(self, sublist_elem) -> list[str]:
        parts: list[str] = []
        for child in sublist_elem:
            tag = self._local(child)
            if tag == "p":
                p_parts = self._para_to_html_parts(child)
                p_content = "".join(p_parts).strip()
                if p_content:
                    if parts:
                        parts.append("<br>")
                    parts.append(p_content)
                # 빈 단락은 <br> 누적 없이 무시
                # (연속된 빈 단락이 섹션 구분을 덮어쓰는 버그 방지)
            elif tag == "tbl":
                if parts:
                    parts.append("<br>")
                parts.append(self._parse_table_html(child))
        return parts

    def _para_to_html_parts(self, p_elem) -> list[str]:
        """단락을 HTML 조각으로 변환 (테이블 포함)"""
        heading_level = self._heading_level(p_elem)
        parts: list[str] = []
        text_buf: list[str] = []

        def flush():
            t = "".join(text_buf).strip()
            text_buf.clear()
            if not t:
                return
            if heading_level:
                parts.append(f"<strong>{t}</strong>")
            else:
                parts.append(t)

        for child in p_elem:
            tag = self._local(child)
            if tag == "run":
                for item in self._parse_run_items(child):
                    if isinstance(item, str):
                        # HTML 특수문자 이스케이프
                        text_buf.append(
                            item.replace("&", "&amp;")
                                .replace("<", "&lt;")
                                .replace(">", "&gt;")
                        )
                    else:
                        flush()
                        parts.append(self._parse_table_html(item))
            elif tag == "lineBreak":
                text_buf.append("<br>")

        flush()
        return parts

    # ── 이미지 추출 ──────────────────────────────────
    def _save_image(self, zf: zipfile.ZipFile, bin_item: str) -> str | None:
        for cand in (f"BinData/{bin_item}", bin_item):
            if cand in zf.namelist():
                self.image_dir.mkdir(parents=True, exist_ok=True)
                self._image_counter += 1
                suffix = Path(bin_item).suffix or ".png"
                name = f"image_{self._image_counter:03d}{suffix}"
                (self.image_dir / name).write_bytes(zf.read(cand))
                return f"{self.image_dir.name}/{name}"
        return None


def convert_hwpx(hwpx_path: Path, out_path: Path, image_dir: Path) -> None:
    print("[1/2] HWPX XML 파싱 중...")
    parser = HwpxParser(hwpx_path, image_dir)
    md = parser.convert()
    print("[2/2] Markdown 저장 중...")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")


# ═════════════════════════════════════════════════════════════
# 통합 진입점
# ═════════════════════════════════════════════════════════════
def convert(hwp_path: Path, out_path: Path, image_dir: Path) -> None:
    suffix = hwp_path.suffix.lower()
    if suffix == ".hwpx" or zipfile.is_zipfile(hwp_path):
        convert_hwpx(hwp_path, out_path, image_dir)
    else:
        convert_hwp(hwp_path, out_path, image_dir)


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="HWP / HWPX 파일을 Markdown으로 변환합니다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python hwp_to_markdown.py 보고서.hwp
  python hwp_to_markdown.py 신청서.hwpx 출력.md --image-dir 이미지
        """,
    )
    parser.add_argument("input",  help="변환할 .hwp / .hwpx 파일 경로")
    parser.add_argument("output", nargs="?", help="출력 .md 파일 경로 (기본: 입력파일명.md)")
    parser.add_argument(
        "--image-dir", default="images",
        help="이미지 저장 디렉토리 (기본: images)",
    )
    args = parser.parse_args()

    missing = check_dependencies()
    if missing:
        print(f"[오류] 필요한 패키지가 없습니다: {', '.join(missing)}")
        print(f"설치: pip install {' '.join(missing)}")
        sys.exit(1)

    hwp_path = Path(args.input)
    if not hwp_path.exists():
        print(f"[오류] 파일을 찾을 수 없습니다: {hwp_path}")
        sys.exit(1)

    out_path = Path(args.output) if args.output else hwp_path.with_suffix(".md")
    image_dir = out_path.parent / args.image_dir

    print(f"입력: {hwp_path}")
    print(f"출력: {out_path}")
    print(f"이미지: {image_dir}")
    print()

    try:
        convert(hwp_path, out_path, image_dir)
    except Exception as exc:
        print(f"\n[오류] 변환 실패: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    md_text = out_path.read_text(encoding="utf-8")
    image_count = len(list(image_dir.glob("*"))) if image_dir.exists() else 0
    print(f"\n완료!")
    print(f"  Markdown: {out_path} ({len(md_text):,} 자)")
    print(f"  이미지:   {image_dir} ({image_count}개)")


if __name__ == "__main__":
    main()
