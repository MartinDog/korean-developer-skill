#!/usr/bin/env python3
"""
PDF → Markdown 변환기 (Human-Readable Mode)

파이프라인:
  PDF → pdfplumber (텍스트 + 표 추출) → Markdown 파이프 테이블 보존
      + pymupdf (이미지 추출, 선택적)

사용법:
    python pdf_to_markdown_human.py input.pdf [output.md] [--image-dir images]

필요 패키지:
    pip install pdfplumber Pillow
    pip install pymupdf  # 이미지 추출용 (선택적)
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
    lines = []
    for line in md.splitlines():
        if not line.startswith("|"):
            line = line.rstrip()
        lines.append(line)
    return "\n".join(lines).strip() + "\n"


# ─────────────────────────────────────────────────────────────
# 표 → Markdown 파이프 테이블
# ─────────────────────────────────────────────────────────────
def _table_to_markdown(table: list[list]) -> str:
    """pdfplumber 추출 테이블 → Markdown 파이프 테이블"""
    if not table:
        return ""

    # None / 줄바꿈 정제
    rows = []
    for row in table:
        cleaned = [str(cell or "").strip().replace("\n", " ") for cell in row]
        rows.append(cleaned)

    if not rows:
        return ""

    col_count = max(len(r) for r in rows)
    for row in rows:
        while len(row) < col_count:
            row.append("")

    col_widths = [max(len(r[i]) for r in rows) for i in range(col_count)]
    col_widths = [max(w, 3) for w in col_widths]

    def fmt_row(row: list[str]) -> str:
        return "| " + " | ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(row)) + " |"

    lines = [
        fmt_row(rows[0]),
        "| " + " | ".join("-" * col_widths[i] for i in range(col_count)) + " |",
    ]
    for row in rows[1:]:
        lines.append(fmt_row(row))

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# 이미지 추출 (pymupdf, 선택적)
# ─────────────────────────────────────────────────────────────
def _extract_images(pdf_path: Path, image_dir: Path) -> dict[int, list[str]]:
    """페이지 인덱스 → 저장된 이미지 파일명 목록. pymupdf 없으면 빈 dict."""
    try:
        import fitz  # noqa: pymupdf
    except ImportError:
        return {}

    image_dir.mkdir(parents=True, exist_ok=True)
    page_images: dict[int, list[str]] = {}

    doc = fitz.open(str(pdf_path))
    for page_num, page in enumerate(doc):
        imgs = page.get_images(full=True)
        page_images[page_num] = []
        for img_idx, img in enumerate(imgs):
            xref = img[0]
            base = doc.extract_image(xref)
            ext = base.get("ext", "png")
            name = f"page{page_num + 1}_img{img_idx + 1}.{ext}"
            (image_dir / name).write_bytes(base["image"])
            page_images[page_num].append(name)
    doc.close()
    return page_images


# ─────────────────────────────────────────────────────────────
# 페이지 파싱 (텍스트 + 표, 수직 위치 순서 보존)
# ─────────────────────────────────────────────────────────────
def _page_to_blocks(page) -> list[str]:
    """
    페이지의 표 바운딩박스를 기준으로:
      - 표 밖 영역 → 텍스트 단락
      - 표 영역    → Markdown 파이프 테이블
    두 가지를 수직 위치(y 좌표) 순으로 정렬하여 반환.
    """
    items: list[tuple[float, str]] = []  # (y_top, markdown_block)

    # 표 정보 수집
    found_tables = page.find_tables()
    table_bboxes = [t.bbox for t in found_tables]

    for tbl_obj in found_tables:
        y_top = tbl_obj.bbox[1]
        md = _table_to_markdown(tbl_obj.extract())
        if md:
            items.append((y_top, md))

    # 표 영역을 제외한 텍스트 추출
    non_table_page = page
    for bbox in table_bboxes:
        try:
            non_table_page = non_table_page.outside_bbox(bbox)
        except Exception:
            pass

    raw_text = non_table_page.extract_text(x_tolerance=3, y_tolerance=3) or ""
    if raw_text.strip():
        # 텍스트가 어느 y 위치에 있는지 대략적으로 파악 (첫 글자 기준)
        chars = non_table_page.chars
        y_text = chars[0]["top"] if chars else 0.0
        items.append((y_text, raw_text.strip()))

    items.sort(key=lambda x: x[0])
    return [block for _, block in items]


# ─────────────────────────────────────────────────────────────
# 변환 진입점
# ─────────────────────────────────────────────────────────────
def convert_pdf(pdf_path: Path, out_path: Path, image_dir: Path) -> None:
    import pdfplumber

    print("[1/3] 이미지 추출 중...")
    page_images = _extract_images(pdf_path, image_dir)
    if not page_images:
        print("       (pymupdf 없음 — 이미지 건너뜀. 설치: pip install pymupdf)")

    print("[2/3] 텍스트 및 표 추출 중...")
    all_blocks: list[str] = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        total = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages):
            print(f"       페이지 {page_num + 1}/{total} 처리 중...")

            # 페이지 구분 헤딩
            all_blocks.append(f"## 페이지 {page_num + 1}")

            # 이미지 참조 (pymupdf로 추출된 경우)
            for img_name in page_images.get(page_num, []):
                rel = f"{image_dir.name}/{img_name}"
                all_blocks.append(f"![이미지]({rel})")

            # 텍스트 + 표 블록 (수직 위치 순서)
            blocks = _page_to_blocks(page)
            all_blocks.extend(blocks)

            # 페이지 구분선
            if page_num < total - 1:
                all_blocks.append("---")

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
        description="PDF 파일을 Markdown으로 변환합니다. (Human-Readable Mode)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python pdf_to_markdown_human.py 보고서.pdf
  python pdf_to_markdown_human.py 양식.pdf 출력.md --image-dir 이미지
        """,
    )
    parser.add_argument("input",  help="변환할 .pdf 파일 경로")
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

    pdf_path = Path(args.input)
    if not pdf_path.exists():
        print(f"[오류] 파일을 찾을 수 없습니다: {pdf_path}")
        sys.exit(1)

    out_path = Path(args.output) if args.output else pdf_path.with_suffix(".md")
    image_dir = out_path.parent / args.image_dir

    print(f"입력: {pdf_path}")
    print(f"출력: {out_path}")
    print(f"이미지: {image_dir}")
    print()

    try:
        convert_pdf(pdf_path, out_path, image_dir)
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
