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
| `docs/` | 로그 형식, 장비 세팅 체크리스트, 회의록 | 전원 |
| `data/sample/` | 분석 코드 테스트용 **가짜** 데이터만 | 정원준 |
| `tools/` | 기술 검증용 터치 테스트 페이지 | - |

**참가자 데이터는 이 저장소에 올리지 않습니다.** `data/raw/`는 `.gitignore`로 막혀 있습니다.
실제 로그는 팀 구글 드라이브에 보관합니다.

## 실행 방법

### 프로토타입
`prototype/index.html`을 Edge나 Chrome으로 엽니다. 별도 설치는 필요 없습니다.
실험 전 [장비 세팅 체크리스트](docs/device-setup.md)를 꼭 확인하세요 (3·4손가락 제스처 끄기 등).

### 분석
```
cd analysis
pip install -r requirements.txt
python analyze.py ../data/sample/sample_log.csv
```

## 작업 규칙

1. `main`에 직접 커밋하지 않고, 작업마다 브랜치를 만들어 Pull Request로 합칩니다.
   - 브랜치 이름 예: `feat/recognition`, `fix/logger-timestamp`, `docs/log-schema`
2. 자기 담당 파일을 주로 수정합니다. 남의 파일을 고칠 때는 PR에서 담당자에게 리뷰를 요청합니다.
3. 할 일은 GitHub Issues에 올리고, 마일스톤에 연결합니다.
4. 로그 형식([docs/log-schema.md](docs/log-schema.md))을 바꿀 때는 구현·분석 담당이 함께 합의합니다.

## 일정 (마일스톤)

| 마일스톤 | 기한 | 내용 |
|---|---|---|
| 로그 형식 합의 | 11/1 (일) | CSV 컬럼 확정 |
| Prototype v0 | 11/6 (금) | C1·C2·C3 + 연습 블록 + 로그 |
| Pilot | 11/15 (일) | 파일럿 3~4명, 임계값·스크립트 확정 |
| Half Report | 11/16–20 | 파일럿 결과 포함 |
| Main Study | 11/21 이후 | 본실험 12명 (기말 마감에서 역산해 확정) |
