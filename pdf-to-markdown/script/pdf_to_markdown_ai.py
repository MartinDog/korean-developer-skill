#!/usr/bin/env python3
"""
PDF → Markdown 변환기 (AI-Optimized Mode)

파이프라인:
  PDF → pdfplumber (텍스트 + 표 추출) → 평탄화된 Key:Value 텍스트
  표는 2D 구조를 파괴하고 1D "키 : 값" 형식으로 변환.
  체크박스는 [미선택] / [선택됨] 시맨틱 태그로 변환.
  이미지는 [이미지 N개] 로 표기 (토큰 절약).

사용법:
    python pdf_to_markdown_ai.py input.pdf [output.md] [--image-dir images]

필요 패키지:
    pip install pdfplumber Pillow
"""

import sys
import re
import argparse
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
    "pdfplumber": "pdfplumber",
    "Pillow":     "PIL",
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
    return md.strip() + "\n"


# ─────────────────────────────────────────────────────────────
# AI 최적화 텍스트 정제
# ─────────────────────────────────────────────────────────────
def _refine_text_for_ai(text: str) -> str:
    """
    AI가 헷갈려하는 체크박스 및 특수기호를 명시적인 의미의 텍스트로 변환.
    """
    # 체크되지 않은 빈 칸 → [미선택]
    text = re.sub(r'\[\s*\]', '[미선택]', text)
    # 체크된 칸 (v, V, o, O, ✓, ✔) → [선택됨]
    text = re.sub(r'\[\s*[vVoO✓✔]\s*\]', '[선택됨]', text)
    # 반복 공백 압축
    text = re.sub(r'[ \t]+', ' ', text)
    # 반복 줄바꿈 압축
    text = re.sub(r'\n{2,}', '\n', text)
    return text.strip()


# ─────────────────────────────────────────────────────────────
# 표 → 평탄화 (Key:Value / 파이프 형식)
# ─────────────────────────────────────────────────────────────
def _table_to_flat(table: list[list]) -> str:
    """
    pdfplumber 추출 테이블 → AI 친화적 평탄화 텍스트.
      2열: "- 키 : 값"
      3열+: "- 열1 | 열2 | 열3"
      1열: "- 내용"
    """
    if not table:
        return ""

    lines = []
    for row in table:
        # None 제거, 줄바꿈 공백화, 공백 정제
        cells = [_refine_text_for_ai(str(cell or "").replace("\n", " ")) for cell in row]
        # 완전히 빈 셀 제거
        cells = [c for c in cells if c]
        if not cells:
            continue

        if len(cells) == 1:
            lines.append(f"- {cells[0]}")
        elif len(cells) == 2:
            lines.append(f"- {cells[0]} : {cells[1]}")
        else:
            lines.append("- " + " | ".join(cells))

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# 이미지 개수 집계 (pymupdf, 선택적)
# ─────────────────────────────────────────────────────────────
def _count_images_per_page(pdf_path: Path) -> dict[int, int]:
    """페이지 인덱스 → 이미지 개수. pymupdf 없으면 빈 dict."""
    try:
        import fitz  # noqa: pymupdf
    except ImportError:
        return {}

    doc = fitz.open(str(pdf_path))
    result = {}
    for page_num, page in enumerate(doc):
        count = len(page.get_images(full=True))
        if count > 0:
            result[page_num] = count
    doc.close()
    return result


# ─────────────────────────────────────────────────────────────
# 페이지 파싱
# ─────────────────────────────────────────────────────────────
def _page_to_blocks_ai(page, image_count: int) -> list[str]:
    """
    페이지에서 텍스트 + 표를 추출하여 AI 친화적 블록 목록으로 반환.
    표 영역의 텍스트 중복을 방지하기 위해 표 bbox를 제외한 영역에서만 텍스트 추출.
    """
    items: list[tuple[float, str]] = []

    # 표 추출
    found_tables = page.find_tables()
    table_bboxes = [t.bbox for t in found_tables]

    for tbl_obj in found_tables:
        y_top = tbl_obj.bbox[1]
        flat = _table_to_flat(tbl_obj.extract())
        if flat:
            items.append((y_top, flat))

    # 표 영역 제외 텍스트 추출
    non_table_page = page
    for bbox in table_bboxes:
        try:
            non_table_page = non_table_page.outside_bbox(bbox)
        except Exception:
            pass

    raw_text = non_table_page.extract_text(x_tolerance=3, y_tolerance=3) or ""
    raw_text = _refine_text_for_ai(raw_text)
    if raw_text:
        chars = non_table_page.chars
        y_text = chars[0]["top"] if chars else 0.0
        items.append((y_text, raw_text))

    # 이미지 표기 (토큰 절약)
    if image_count > 0:
        items.append((9999.0, f"[이미지 {image_count}개]"))

    items.sort(key=lambda x: x[0])
    return [block for _, block in items]


# ─────────────────────────────────────────────────────────────
# 변환 진입점
# ─────────────────────────────────────────────────────────────
def convert_pdf(pdf_path: Path, out_path: Path, image_dir: Path) -> None:
    import pdfplumber

    print("[1/3] 이미지 개수 파악 중...")
    page_image_counts = _count_images_per_page(pdf_path)
    if not page_image_counts:
        print("       (pymupdf 없음 — 이미지 정보 생략. 설치: pip install pymupdf)")

    print("[2/3] 텍스트 및 표 추출 중...")
    all_blocks: list[str] = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        total = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages):
            print(f"       페이지 {page_num + 1}/{total} 처리 중...")

            img_count = page_image_counts.get(page_num, 0)
            blocks = _page_to_blocks_ai(page, img_count)
            all_blocks.extend(blocks)

    print("[3/3] Markdown 저장 중...")
    md = "\n\n".join(b for b in all_blocks if b)
    md = _postprocess(md)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="PDF 파일을 Markdown으로 변환합니다. (AI-Optimized Mode)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python pdf_to_markdown_ai.py 보고서.pdf
  python pdf_to_markdown_ai.py 양식.pdf 출력.md
        """,
    )
    parser.add_argument("input",  help="변환할 .pdf 파일 경로")
    parser.add_argument("output", nargs="?", help="출력 .md 파일 경로 (기본: 입력파일명.md)")
    parser.add_argument(
        "--image-dir", default="images",
        help="이미지 저장 디렉토리 (AI 모드에서는 미사용, 호환성용)",
    )
    args = parser.parse_args()

    missing = check_dependencies()
    if missing:
        print(f"[오류] 필요한 패키지가 없습니다: {', '.join(missing)}")
        print(f"설치: pip install {' '.join(missing)}")
        sys.exit(1)

    pdf_path = Path(args.input)
    if not pdf_path.exists():
        print(f"[오류] 파일을 찾을 수 없습니다: {pdf_path}")
        sys.exit(1)

    out_path = Path(args.output) if args.output else pdf_path.with_suffix(".md")
    image_dir = out_path.parent / args.image_dir

    print(f"입력: {pdf_path}")
    print(f"출력: {out_path}")
    print()

    try:
        convert_pdf(pdf_path, out_path, image_dir)
    except Exception as exc:
        print(f"\n[오류] 변환 실패: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    md_text = out_path.read_text(encoding="utf-8")
    print(f"\n완료!")
    print(f"  Markdown: {out_path} ({len(md_text):,} 자)")


if __name__ == "__main__":
    main()
