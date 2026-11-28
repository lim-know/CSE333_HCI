# Count & Tune — CSE333 Team 4

왼손 손가락 개수로 펜 슬롯을 고르고(Count), 펜 드래그로 굵기를 조절하는(Tune) 양손 제스처 기법과
툴바+슬라이더 방식을 비교하는 CSE333(Introduction to HCI) 팀 프로젝트입니다.

- 팀원: 노태림 · 강민진 · 최유진 · 정원준
- 실험 장비: Galaxy Book4 Pro 360 + S Pen (본실험), Galaxy Book Pro 360 (개발·파일럿 연습)
- 플랫폼: Windows 펜 노트북 + 웹 브라우저

## 폴더 구조

| 폴더 | 내용 | 담당 |
|---|---|---|
| `prototype/` | 실험용 웹 앱 (C1 툴바+슬라이더, C2 1손가락+드래그, C3 Count & Tune) | 노태림, 강민진 |
| `analysis/` | 로그 분석 코드 (pandas, pingouin, matplotlib·seaborn) | 정원준 |
| `docs/` | 로그 형식, 분석 계획, 장비 세팅 체크리스트 | 전원 |
| `data/sample/` | 분석 코드 테스트용 **가짜** 데이터만 | 정원준 |
| `tools/` | 기술 검증용 터치 테스트 페이지 | - |

**참가자 데이터는 이 저장소에 올리지 않습니다.** `data/raw/`는 `.gitignore`로 막혀 있습니다.
실제 로그는 팀 구글 드라이브에 보관합니다.

## 실행 방법

### 프로토타입
**실험용 최신 코드는 `main`이 아니라 `prototype` 브랜치에 있습니다.** `main`의 `prototype/` 폴더는 초기 뼈대라 실험에 쓰지 않습니다.

- 웹에서 열기: https://lim-know.github.io/CSE333_HCI/ (GitHub Pages)
  - Pages가 어느 브랜치를 보여 주는지는 저장소 Settings → Pages에서 바뀔 수 있습니다. 11/20 기준 `prototype2`(PR #11, 머지 전)입니다.
- 내려받아 열기: `prototype` 브랜치를 받아 `prototype/index.html`을 Chrome이나 Edge로 엽니다. 별도 설치는 필요 없습니다.

실험·파일럿 전 [장비 세팅 체크리스트](docs/device-setup.md)를 꼭 확인하세요 (3·4손가락 제스처 끄기, 사용한 브랜치·커밋 기록 등).
**어느 버전으로 진행했는지 모르면 그 로그는 분석에 쓰기 어렵습니다.**

### 분석
분석 방법은 [분석 계획](docs/analysis-plan.md)(PR #12, 검토 중), 로그 형식은 [docs/log-schema.md](docs/log-schema.md)를 봅니다.
분석 코드는 로그 형식 v1.2(제시문형 과제) 기준입니다 (11/26).

Python 3.12 기준이며, 패키지 버전은 `analysis/requirements.txt`에 고정되어 있습니다. 저장소 루트에서 실행합니다.
```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r analysis\requirements.txt
cd analysis
..\.venv\Scripts\python validate_log.py ..\data\sample
..\.venv\Scripts\python analyze.py ..\data\sample
```

**본실험 세션이 끝날 때마다** (다운로드 폴더 → `data/raw`, 참가자 데이터라 커밋되지 않음):
```powershell
cd analysis
..\.venv\Scripts\python collect.py "$env:USERPROFILE\Downloads"   # 파일 정리 + 세션당 35개인지 확인
..\.venv\Scripts\python validate_log.py ..\data\raw                # 오류 0건인지 확인
..\.venv\Scripts\python form_to_questionnaire.py <폼 응답.csv>    # 설문(구글 폼) → data\raw\questionnaire.csv
..\.venv\Scripts\python analyze.py ..\data\raw                     # 결과 표는 analysis\output\
```

| 파일 | 용도 |
|---|---|
| `collect.py` | 브라우저가 내려받은 파일을 `data/raw` 구조로 정리 (중복 사본 처리, 빠진 블록 확인) |
| `validate_log.py` | 세션 직후 로그 점검 (누락, 순서 오류, 세션 중 코드 버전 변경, 배정표와 다른 순서 등) |
| `build_steps.py` | 원시 이벤트로 단계별 분석 표 생성 (측정값 정의는 분석 계획 4장) |
| `form_to_questionnaire.py` | 구글 폼 설문 응답 CSV → `questionnaire.csv` (TLX ×10, 몇 번째 → 조건). 폼은 `tools/questionnaire-form.gs`로 만든다 |
| `stats.py` | 가설 검정 H1~H5 (분석 계획 5·6장) |
| `analyze.py` | 점검 → 단계 표 → 제외 규칙 → H1~H5 → 표를 `analysis/output/`에 저장 |
| `replay_thresholds.py` | 정지 임계값과 손→펜 간격을 바꿔 재계산 (`--still 12 120 --window 500 1000`) |
| `make_sample_data.py` | 테스트용 가짜 데이터 생성 |

테스트는 `analysis` 폴더에서 `..\.venv\Scripts\python -m unittest discover -s tests`로 실행합니다.

## 작업 규칙

1. `main`에 직접 커밋하지 않고, 작업마다 브랜치를 만들어 Pull Request로 합칩니다.
   - 브랜치 이름 예: `feat/recognition`, `fix/logger-timestamp`, `docs/log-schema`
2. 자기 담당 파일을 주로 수정합니다. 남의 파일을 고칠 때는 PR에서 담당자에게 리뷰를 요청합니다.
3. 할 일은 GitHub Issues에 올리고, 마일스톤에 연결합니다.
4. 로그 형식([docs/log-schema.md](docs/log-schema.md))을 바꿀 때는 구현·분석 담당이 함께 합의합니다.

## 일정 (마일스톤)

11/20 기준. 회의록과 세부 일정은 노션에서 관리합니다 (11/15 미팅 결정).

| 마일스톤 | 기한 | 내용 |
|---|---|---|
| 로그 형식 합의 | 11/4 완료 | v1.0 확정 (PR #1), 같은 날 v1.1 (PR #6, 11/20 머지). v1.2 제안은 PR #12 |
| Prototype | 11/17–20 | 실험 흐름(PR #9), 제시문형 과제(PR #10), 수정(PR #11 검토 중) |
| Pilot | 11/20–21 | 11/20 1차, 11/21 수정 후 2차. 임계값·제시문·분석 기준 확정 |
| Half Report | 11/22 (일) | 파일럿 결과 포함 |
| Main Study | 11/30 (월) | 본실험 12명 (11/26 팀 결정: 주말에서 월요일로). 이어서 분석 |
