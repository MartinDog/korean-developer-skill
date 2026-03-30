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

    # ── AI 최적화 텍스트 정제 ────────────────────────────────
    def _refine_text_for_ai(self, text: str) -> str:
        """
        AI가 헷갈려하는 체크박스 및 특수기호를 명시적인 의미의 텍스트로 변환합니다.
        """
        # 1. 체크되지 않은 빈 칸 -> [미선택]
        # 예: 여 [ ] 부 [ ] -> 여 [미선택] 부 [미선택]
        text = re.sub(r'\[\s*\]', '[미선택]', text)
        
        # 2. 체크된 칸 (v, V, o, O 등으로 표시된 경우) -> [선택됨]
        # 예: 여 [v] 부 [ ] -> 여 [선택됨] 부 [미선택]
        text = re.sub(r'\[\s*[vVoO]\s*\]', '[선택됨]', text)
        
        # 3. 불필요하게 반복되는 공백 및 탭 기호 압축
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()

    # ── 기존 평탄화 추출 로직 수정 ────────────────────────────────
    def _parse_cell_content_flat(self, tc_elem) -> str:
        parts = []
        for child in tc_elem:
            tag = self._local(child)
            if tag == "subList":
                parts.extend(self._sublist_to_text(child))
            elif tag == "p":
                parts.extend(self._para_to_text_parts(child))
            elif tag == "tbl":
                parts.append(self._parse_table_flat(child))
        
        # ★ 추출된 텍스트를 합친 후 AI 맞춤형으로 한 번 더 정제합니다.
        raw_text = " ".join(parts)
        return self._refine_text_for_ai(raw_text)

    def _parse_table_flat(self, tbl_elem) -> str:
        lines = []
        for child in tbl_elem:
            if self._local(child) == "tr":
                row_texts = []
                for tc in child:
                    if self._local(tc) == "tc":
                        text = self._parse_cell_content_flat(tc)
                        if text:
                            row_texts.append(text)
                
                if row_texts:
                    if len(row_texts) == 1:
                        lines.append(f"- {row_texts[0]}")
                    elif len(row_texts) == 2:
                        # 2칸 구조는 '키 : 값'
                        lines.append(f"- {row_texts[0]} : {row_texts[1]}")
                    else:
                        # 3칸 이상 구조는 파이프로 나열
                        lines.append("- " + " | ".join(row_texts))
        
        if not lines:
            return ""
        return "\n".join(lines) + "\n"

    def _sublist_to_text(self, sublist_elem) -> list[str]:
        parts = []
        for child in sublist_elem:
            tag = self._local(child)
            if tag == "p":
                parts.extend(self._para_to_text_parts(child))
            elif tag == "tbl":
                parts.append(self._parse_table_flat(child))
        return parts

    def _para_to_text_parts(self, p_elem) -> list[str]:
        parts = []
        text_buf = []

        def flush():
            t = "".join(text_buf).strip()
            text_buf.clear()
            if t:
                parts.append(t)

        for child in p_elem:
            tag = self._local(child)
            if tag == "run":
                for item in self._parse_run_items(child):
                    if isinstance(item, str):
                        # HTML 이스케이프(<, > 변환) 없이 순수 텍스트만 보존
                        text_buf.append(item)
                    else:
                        flush()
                        # 중첩 테이블 처리
                        parts.append(self._parse_table_flat(item))
            elif tag == "lineBreak":
                # AI가 한 문장으로 인식하도록 줄바꿈을 공백으로 처리
                text_buf.append(" ")

        flush()
        return parts

    # ── 섹션 순회 ────────────────────────────────────
    def _walk_section(self, root, blocks: list[str], zf: zipfile.ZipFile) -> None:
        """HWPX 구조: sec > p > run > (t | tbl | ctrl)"""
        for child in root:
            tag = self._local(child)
            if tag == "p":
                para_blocks = self._parse_paragraph_blocks(child)
                blocks.extend(para_blocks)
            elif tag == "tbl":
                text_block = self._parse_table_flat(child)
                if text_block:
                    blocks.append(text_block)
            elif tag in ("subList", "sec"):
                self._walk_section(child, blocks, zf)

    def _parse_paragraph_blocks(self, p_elem) -> list[str]:
        heading_level = self._heading_level(p_elem)
        result = []
        text_parts = []

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
                        text_block = self._parse_table_flat(item)
                        if text_block:
                            result.append(text_block)
            elif tag == "lineBreak":
                text_parts.append("\n")

        flush_text()
        return result


# ═════════════════════════════════════════════════════════════
# 통합 진입점
# ═════════════════════════════════════════════════════════════
def convert_hwpx(hwpx_path: Path, out_path: Path, image_dir: Path) -> None:
    print("[1/2] HWPX XML 파싱 중...")
    parser = HwpxParser(hwpx_path, image_dir)
    md = parser.convert()
    print("[2/2] Markdown 저장 중...")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")


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
  python hwp_to_markdown_ai.py 보고서.hwp
  python hwp_to_markdown_ai.py 신청서.hwpx 출력.md --image-dir 이미지
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
