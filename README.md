# Korean Skills for Claude Code

Claude Code에서 사용할 수 있는 한국어 환경 최적화 스킬 모음입니다.
각 스킬은 `SKILL.md` 파일로 정의되며, 특정 상황에서 자동으로 호출되거나 `/skill-name` 형태로 직접 실행할 수 있습니다.

---

## 스킬 목록

| 스킬 | 설명 |
|---|---|
| [hanguel-to-markdown](#hanguel-to-markdown) | HWP/HWPX 파일을 Markdown으로 변환 |
| [pdf-to-markdown](#pdf-to-markdown) | PDF 파일을 Markdown으로 변환 |
| [agent-team-builder](#agent-team-builder) | 멀티 에이전트 팀 설계 및 프롬프트 생성 |
| [smarter-ai-develop](#smarter-ai-develop) | 코드 작성 후 아키텍처/보안 자동 검토 및 세션 정리 |

---

## hanguel-to-markdown

한컴 워드프로세서 파일(`.hwp`, `.hwpx`)을 Markdown으로 변환합니다.
변환 목적에 따라 **사람이 읽기 위한 포맷**과 **AI 분석 최적화 포맷** 두 가지 모드를 제공합니다.

### 동작 방식

Claude가 의도를 파악하여 적합한 모드를 선택합니다:

- **Human Mode** — 원본 문서의 테이블과 레이아웃을 최대한 보존. 사람이 읽거나 공유할 때 사용.
- **AI Mode** — 2D 테이블 구조를 1D `Key: Value` 형태로 평탄화. 토큰 절감 및 RAG에 최적화.

### 사용법

HWP 파일 경로를 언급하면 스킬이 자동 활성화됩니다.

```
이 파일 읽어줘: C:/documents/지원서.hwp
```

```
contract.hwpx를 AI가 분석할 수 있게 변환해줘
```

의도가 불분명한 경우 Claude가 먼저 확인 질문을 합니다.

### 변환 스크립트

| 모드 | 스크립트 |
|---|---|
| Human | `scripts/hwp_to_markdown_human.py` |
| AI | `scripts/hwp_to_markdown_ai.py` |

```bash
python scripts/hwp_to_markdown_human.py C:/documents/report.hwp
python scripts/hwp_to_markdown_ai.py C:/documents/report.hwp
```

---

## pdf-to-markdown

PDF 파일을 Markdown으로 변환합니다. 정부 양식, 계약서, 보고서 등 복잡한 레이아웃의 PDF에 최적화되어 있습니다.

### 동작 방식

`hanguel-to-markdown`과 동일한 이중 모드 구조를 따릅니다:

- **Human Mode** — Markdown pipe 테이블과 페이지 구분선으로 원본 레이아웃 재현. 이미지는 참조로 삽입.
- **AI Mode** — 테이블 구조를 평탄화하고 체크박스를 `[미선택]`/`[선택됨]` 태그로 변환. 이미지는 `[이미지 N개]`로 표기.

### 사용법

```
이 PDF 내용 요약해줘: C:/downloads/annual_report.pdf
```

```
계약서.pdf를 사람이 읽기 좋게 변환해줘
```

### 필수 패키지

```bash
pip install pdfplumber Pillow
pip install pymupdf  # 선택사항 — 이미지 추출/참조
```

### 제약 사항

- 스캔된 PDF(이미지 전용)는 OCR 도구(`pytesseract` 등)가 별도로 필요합니다.
- 원시 바이트로 직접 파싱하지 않고 항상 변환 스크립트를 먼저 실행합니다.

---

## agent-team-builder

Claude Code의 멀티 에이전트 시스템(Agent Teams, Subagents)을 설계하고, 즉시 실행 가능한 팀 생성 프롬프트를 만들어 드립니다.

### 동작 방식

**Chief Cognitive Architect** 역할로 구조화된 대화를 통해 요구사항을 수집합니다.
한 번에 1–2개의 질문만 하며, 모든 설계 결정이 완료되면 실행 가능한 프롬프트를 출력합니다.

```
에이전트 팀 설계 결정 항목:
  1. 팀 구조 (Orchestrator + Worker 정의)
  2. 각 에이전트의 페르소나 및 역할 분담
  3. 도구/MCP 서버 요구사항
  4. AGENTS.md 필요 여부
  5. 자기 검증(hallucination 방지) 제약 조건
```

### 언제 사용하는가

- 여러 에이전트가 협업하는 자동화 워크플로우를 구축할 때
- Orchestrator + 전문 Worker 구조의 시스템을 설계할 때
- `AGENTS.md`를 포함한 멀티 에이전트 프롬프트를 작성할 때

### 사용 예시

```
에이전트 팀 만들어줘 — 프론트엔드 코드 리뷰 + DB 스키마 검토를 병렬로 하고 싶어
```

```
orchestrator와 worker 에이전트로 구성된 데이터 파이프라인 설계해줘
```

```
멀티 에이전트 프롬프트 작성해줘: 문서 수집 → 요약 → 보고서 생성
```

### 출력 결과물

생성된 프롬프트에는 다음이 포함됩니다:
- 목표 및 범위
- 에이전트 로스터 (이름, 페르소나, 책임, 입출력)
- `AGENTS.md` 참조 규칙
- 자기 검증 제약 조건
- 필요한 환경 변수

```bash
# Agent Teams 사용 시 필요한 환경 변수
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

---

## smarter-ai-develop

코드 작성/변경 후 **아키텍처 검토**, **보안 감사**, **세션 마무리**를 자동으로 수행하는 통합 개발 가드레일입니다.
3개의 서브 스킬로 구성되어 있으며, 상황에 따라 필요한 스킬을 선택적으로 실행합니다.

### 서브 스킬 구조

```
smarter-ai-develop (오케스트레이터)
├── architecture-review   — 코드 로직 변경 시 자동 실행
├── security-audit        — 신뢰 경계 교차 코드에 자동 실행
└── session-wrapup        — 세션 종료 시 실행
```

---

### architecture-review

코드를 사용자에게 전달하기 전에 품질을 자동 검토합니다.

**검사 항목:**

| 항목 | 내용 |
|---|---|
| A1 — 중복 탐지 | 동일 책임의 함수/클래스가 이미 존재하는지 확인 |
| A2 — 단일 책임 원칙 | 하나의 함수/클래스가 여러 관심사를 처리하는지 확인 |
| A3 — 비동기 패턴 일관성 | 기존 코드베이스의 async/await, Promise, callback 패턴과 일치하는지 확인 |
| A4 — N+1 쿼리 탐지 | 루프 내부에서 DB 쿼리가 실행되는지 확인 |

위반 사항은 사용자에게 전달 전에 자동으로 수정됩니다.

---

### security-audit

신뢰 경계(user → app, app → DB, app → HTML)를 넘나드는 코드에 자동 실행됩니다.

**검사 항목:**

| 항목 | 내용 |
|---|---|
| B1 — ARIA 정확성 | 불필요한 ARIA 속성 → 네이티브 HTML 요소로 교체 |
| B2 — 키보드 내비게이션 | tab 순서 및 동적 콘텐츠의 aria-live 설정 확인 |
| B3 — 대체 텍스트 & 색상 대비 | `alt` 속성 누락, WCAG AA(4.5:1) 대비율 검사 |
| B4 — SQL 인젝션 | 문자열 연결 방식 쿼리 → 파라미터화된 쿼리로 교체 |
| B5 — XSS | innerHTML/dangerouslySetInnerHTML에 사용자 입력 삽입 탐지 |
| B6 — 로그 인젝션 | 로그에 raw 사용자 입력 기록 시 이스케이프 처리 |
| B7 — 하드코딩된 시크릿 | API 키, 비밀번호, 토큰이 소스 코드에 포함된 경우 탐지 |

---

### session-wrapup

작업 세션 종료 시 변경 사항을 정리하고 지식을 영속화합니다.

**실행 단계:**

| 단계 | 내용 |
|---|---|
| C1 — 변경 요약 | 세션에서 수정된 파일 목록 및 커밋 단위 제안 |
| C2 — 사전 품질 게이트 | architecture-review / security-audit 미실행 시 지금 실행 |
| C3 — Git 커밋 | `feat(scope): summary` 형식의 커밋 메시지로 커밋 생성 |
| C4 — 새 지식 추출 | 비즈니스 엣지케이스, 아키텍처 결정, 반복 수정 패턴, 외부 시스템 특이사항 수집 |
| C5 — CLAUDE.md 업데이트 | 수집된 지식을 프로젝트 루트 CLAUDE.md에 추가 |
| C6 — 최종 보고 | 커밋 해시, CLAUDE.md 추가 항목, 다음 세션 주의사항 요약 |

### 세션 종료 예시

```
오늘 작업 마무리해줘
```

```
커밋하고 끝내줘
```

```
세션 종료, 오늘 배운 거 CLAUDE.md에 저장해줘
```

---

## 디렉토리 구조

```
Korean-skills/
├── README.md
├── agent-team-builder/
│   └── SKILL.md
├── hanguel-to-markdown/
│   ├── SKILL.md
│   └── scripts/
│       ├── hwp_to_markdown_human.py
│       └── hwp_to_markdown_ai.py
├── pdf-to-markdown/
│   ├── SKILL.md
│   └── script/
│       ├── pdf_to_markdown_human.py
│       └── pdf_to_markdown_ai.py
└── smarter-ai-develop/
    ├── SKILL.md
    ├── architecture-review/
    │   └── SKILL.md
    ├── security-audit/
    │   └── SKILL.md
    └── session-wrapup/
        └── SKILL.md
```
