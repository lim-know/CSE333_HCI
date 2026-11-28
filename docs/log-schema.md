# 로그 형식 v1.2 (제안, 합의 전)

담당: 구현(노태림) + 분석(정원준). **바꿀 때는 두 사람이 합의하고 이 문서부터 고친다.**
코드 기준은 `analysis/logdata.py`이며, 이 문서와 함께 고친다.

## 변경 이력

| 버전 | 날짜 | 내용 |
|---|---|---|
| 1.0 | 11/4 | 최초 확정 (PR #1, 노태림 승인) |
| 1.2 (제안) | 11/20 | 제시문형 과제(PR #10)와 PR #11 반영: 단계 정의, `return` 단계, 완료를 일찍 누르면 `skipped`, 굵기 1~8pt, `build`로 버전 구분, `activation`의 `n_still` 뜻 변경. 11/21에 PR #11 `f140813`과 11/20 파일럿 결과로 갱신. 11/26: 단계별 시간 제한 없앰(팀 결정), 분석 코드 v1.2 구현(`analysis/`), `schema_version` 값은 1.1 유지(아래). 11/28: PR #11 `515b823` 단계 구성 변경(1번, 5번), build `exp-2026-11-28`. 아래 [v1.2 변경 제안과 PR 의존 관계](#v12-변경-제안과-pr-의존-관계) 참고. **노태림 합의 전** |
| 1.1 | 11/4 | 11/4 설계 결정 반영: 따라쓰기 한국어 고정, 완료 버튼, 단계별 시간 제한(`time_limit_ms`), 펜 다운의 `source`(canvas/ui), 손→펜 간격 기준 기록(`touch_to_pen_ms`), participants의 `english_proficiency` 삭제 |

v1.0에서 바뀐 부분 중 **구현에 영향이 있는 것**은 아래 세 가지다.
1. 펜 `pointerdown`/`pointerup`에 `source`를 적는다. 필기 영역이면 `canvas`, 툴바·슬라이더·완료 버튼이면 `ui`.
2. `block_start` detail에 `touch_to_pen_ms`를 적는다. 상한을 쓰지 않으면 `touch_to_pen_ms=none`.
3. 스크립트의 `time_limit_ms`가 지나면 `step_end`를 `outcome=timeout`으로 남기고 다음 단계로 간다. (v1.2에서 없앰, 위 12번)

## v1.2 변경 제안과 PR 의존 관계

11/18 팀 결정으로 과제가 **제시문형**으로 바뀌었다 (위 제시문을 아래 칸에 옮겨 쓰면서, 표시된 곳만 지정한 펜·굵기로 표시).
이에 맞춰 아래를 바꾼다. **열(컬럼)은 그대로**이고, 값의 뜻과 규칙이 바뀐다.

### 바뀌는 것

| # | 항목 | v1.1 | v1.2 |
|---|---|---|---|
| 1 | 단계 | 지시 하나 = 단계 하나, 완료 버튼으로 끝남 | **참가자가 할 일 하나 = 단계** (`515b823`부터). 본문은 글씨 표시마다 끊겨 "본문 쓰기" 단계(`task_type=return`, `text`에 쓸 본문 전체)가 되고 글씨 표시와 번갈아 나온다. 밑줄·동그라미·칠하기는 그 뒤에 한꺼번에. `f140813`까지는 펜 상태를 바꿔야 하는 곳만 단계였다 (차이는 no_change 단계뿐) |
| 2 | 단계 진행 | 완료 버튼 | 목표 상태로 그은 획이 끝나면 자동으로 다음 단계. 마지막 단계만 완료 버튼 |
| 3 | `cue_shown` | 지시가 화면에 그려진 때 | 앞 단계 정답 획이 끝나 다음 표시가 강조된 때. **주 지표의 기준점이 아니다** (분석 계획 4.1) |
| 4 | `step_end` outcome | completed / timeout / skipped | 값은 그대로. 표시가 남은 채 완료를 누르면 **진행 중 단계는 `skipped`**, 남은 단계는 `step_end`가 없다 (단계표와 비교해 찾는다). 진행자 건너뛰기(`s` 키)와는 다음 이벤트로 구분한다: `skipped` 바로 뒤가 `block_end`면 참가자가 완료를 누른 것, 다음 단계의 `cue_shown`이면 진행자 |
| 5 | `step_type` | `copy` 있음 | `copy` 없음. switch_only / size_only / switch_size / **no_change**(`515b823`부터. 펜 상태가 바로 앞과 같음. 본문으로 시작하는 제시문의 첫 단계. 분석은 시간을 재지 않는다) |
| 6 | 굵기 | 프리셋 0.5·1·2·4·8pt, 로그 눈금 | 1~8pt, 선형 눈금. **프리셋은 정수 8개**이고 근처(`snap_px`)에 오면 프리셋에 붙는다. 그 사이는 0.1pt 단위 값이 나온다. `on_preset`은 정수면 1 |
| 7 | C3 슬롯 변경 | 펜 다운(`activation`) 때 | 손가락이 멈춘 순간(IDLE→ARMED) **닿아 있는 손가락 수**로 정하고, 그 뒤에 닿는 손가락은 반영하지 않는다 (팀 결정 11/20). `slot_change`(source=gesture)가 `activation` 없이 생길 수 있다 |
| 8 | 지우개 | 실험 중 끔 | 실험 중 켬. 새 이벤트 없이 펜 `pointerdown`의 `buttons`(32 또는 2)로 찾는다 |
| 9 | `script_id` | `exp2A` | 제시문마다 `exp2A_0` ~ `exp2A_4` |
| 10 | `build` | 권장 | **필수, 코드를 고칠 때마다 바꾼다.** 분석은 이 값으로 버전별 규칙을 고른다 |
| 11 | `activation`의 `n_still` | 정지로 판정된 손가락 수 | **닿아 있는 손가락 수** (PR #11 `0cf62ef`부터). 정지 손가락 수는 펜 `pointerdown` 줄의 `n_still`을 쓴다 (그쪽은 v1.1 그대로) |
| 12 | 단계별 시간 제한 | `time_limit_ms` 필수, 지나면 `timeout` | **없음** (팀 결정 11/26). `time_limit_ms` 열은 남아도 되고 비어도 된다. 분석은 이 값을 쓰지 않는다 |
| 13 | `schema_version` 값 | 1.1 | **1.1 그대로** 둔다. 열 구성이 같아서 `logger.js`를 고치지 않는다. 규칙 차이는 `build`로 구분한다. 분석은 1.1과 1.2를 모두 받는다 |

저장 규칙(블록마다 파일 저장, 단계표 `script_*.csv` 저장)은 **v1.1 그대로 유지**한다. `exp-2026-11-21`부터 블록이 끝날 때마다 `events`, 조건이 끝날 때 본과제 `script` 5개, 세션이 끝날 때 `session`·`participant`를 내려받는다 (세션당 35개, [장비 체크리스트](device-setup.md)).
브라우저 백업(localStorage)은 한도가 약 5MB라 블록 3~4개만 남는다 (11/20 파일럿). **대비책으로 믿지 않는다.**

### PR 의존 관계

v1.2의 일부는 PR #11(리뷰 중)에 기대고 있다. **PR이 머지되지 않거나 일부만 반영되면, 해당 항목만 "안 되면" 칸으로 돌아간다.** 문서 전체를 되돌리지 않는다.

"PR #11에 반영"은 prototype2 브랜치에 들어갔지만 PR #11이 아직 머지되지 않았다는 뜻이다.

| 항목 (위 표 #) | 근거 | 상태 (11/21) | 안 되면 |
|---|---|---|---|
| 1, 2, 3, 5 | PR #10 | 머지됨 | — (확정) |
| 단계 순서: 글씨 먼저, 밑줄·동그라미·칠하기 나중 | PR #11 | 리뷰 중. 파일럿에서 "본문 먼저, 표시는 뒤로" 의견 | PR #10의 읽는 순서. 열과 규칙은 같다 |
| 4 완료 시 `skipped` | PR #11 `f140813` | PR #11에 반영 | 완료로 끝난 블록의 마지막 단계는 분석에서 뺀다 |
| 6 굵기 | PR #11 | 팀 확인 (11/20) | v1.1 프리셋 |
| 7 C3 슬롯 변경 시점 | PR #11 `0cf62ef` | 팀 결정 (11/20). PR #11에 반영 | v1.1 (펜 다운 때) |
| 8 지우개 | PR #11 | 팀 확인 (11/20) | v1.1 (실험 중 끔) |
| 9 `script_id` | PR #11 | 리뷰 중 | v1.1 |
| 10 `build` | PR #11 `f140813` | PR #11에 반영 (`exp-2026-11-21`) | `sessions.csv` notes에 사용한 브랜치·커밋을 적는다 |
| 11 `activation`의 `n_still` | PR #11 `0cf62ef` | PR #11에 반영 | v1.1 (정지 손가락 수) |
| 저장 규칙 유지 | PR #11 `f140813` | PR #11에 반영 | 단계표는 코드에서 다시 만든다. 빠진 블록은 결측 처리 (브라우저 백업은 대비책이 아니다) |

### 버전 구분

| `build` 값 | 코드 | 적용 |
|---|---|---|
| `exp-2026-11-18` | PR #10 (prototype 6b56854), PR #11 (7e8c4bb, 0cf62ef) **모두** | 이 값만으로는 구분이 안 된다. 11/20 파일럿은 시각으로 구분한다: 11:04 전 세션은 `7e8c4bb`, 뒤는 `0cf62ef` |
| `exp-2026-11-21` | PR #11 `f140813` (블록마다 다운로드, script 저장, 완료 시 `skipped`) | v1.2. 60초 제한 있음 |
| `exp-2026-11-28` | PR #11 `515b823` (단계 = 할 일 단위, `no_change`, UI 위치 조정) | v1.2. **60초 제한이 아직 코드에 있음** (11/28 확인) |
| `exp-2026-11-29` | `fix/no-time-limit` `f941f1b` (515b823 + 시간 제한 없앰, 디버그 로그 정리). main 병합 후 본실험용 | v1.2. 시간 제한 없음. **본실험은 이 값이어야 한다.** 다음에 코드를 고치면 이 표와 `analysis/logdata.py`의 `KNOWN_BUILDS`에 같이 넣는다 (안 넣으면 `validate_log.py`가 주의를 띄운다) |

## 원칙

1. **브라우저는 사실만 기록한다.** 판정(오류, 오작동, 정답 시각)은 기록하지 않는다.
2. **판정은 Python에서 한다.** `analysis/build_steps.py`만 고치면 재수집 없이 다시 계산할 수 있다.
3. **원본 로그는 고치지 않는다.** 실험 중 문제가 생기면 `sessions.csv`의 `notes`에 적는다.

## 파일 구조

`data/raw/`(본실험)와 `data/pilot/`(파일럿)은 아래 구조를 따르며, 저장소에는 올리지 않는다.
가짜 데이터 예시는 `data/sample/`에 있다.

| 파일 | 작성 주체 | 내용 |
|---|---|---|
| `events/events_<session_id>_b<블록 2자리>.csv` | 프로토타입 | 원시 이벤트. 블록이 끝날 때마다 저장 |
| `scripts/script_<script_id>.csv` | 프로토타입 (`passage.js`) | 단계별 지시와 목표값. 조건이 끝날 때 본과제 제시문 5개를 저장. **연습 제시문은 저장하지 않는다** (연습은 분석 안 함) |
| `sessions.csv` | 프로토타입 + 진행자 | 세션별 조건 순서, 장비, 특이사항. 브라우저가 `session_<id>.csv` 한 줄을 내려받고, `analysis/collect.py`가 합친다. 진행자는 `notes`에 커밋·특이사항을 적는다 |
| `participants.csv` | 프로토타입 | 참가자 정보 (이름 X). `participant_<id>.csv`를 `collect.py`가 합친다 |
| `questionnaire.csv` | 실험 진행자 | 조건별 NASA-TLX, 선호도 |
| `steps.csv` | `build_steps.py` | 단계별 분석 표. 직접 고치지 않고 언제든 다시 생성 |

- **세션:** 참가자 한 명의 실험 한 번. `session_id`는 `P01-1` 형식이다. 중단 후 다시 시작하면 `P01-2`로 기록한다.
- **블록:** 조건 × phase × exp 하나를 끝까지 진행하는 단위. 세션 안에서 1부터 번호를 매긴다.

## events: 원시 이벤트

한 줄 = 이벤트 하나. 값이 없으면 빈칸으로 둔다.

| 컬럼 | 예시 | 설명 |
|---|---|---|
| schema_version | 1.1 | 이 문서의 버전 |
| session_id | P01-1 | 세션 ID |
| participant | P01 | 참가자 ID (이름 X) |
| block | 9 | 세션 안의 블록 번호 |
| condition | C3 | C1 / C2 / C3 |
| phase | main | practice / main |
| exp | exp2 | exp1 / exp2 |
| script_id | exp2C | 사용한 스크립트 |
| step_id | s03 | 현재 단계. 단계 사이의 이벤트는 빈칸 |
| seq | 120 | 블록 안 순번. 1씩 증가 |
| t_event | 10234.5 | 사건 시각 (ms). 입력은 `event.timeStamp`, 나머지는 `performance.now()` |
| t_logged | 10236.0 | 기록 시각 (ms, `performance.now()`) |
| event | activation | 아래 이벤트 목록 참고 |
| source | gesture | 앱 이벤트: toolbar / slider / gesture / pen. 포인터 이벤트: 닿은 곳 canvas / ui (펜은 필수) |
| pointer_id, pointer_type | 11, touch | `pointerId`, pen / touch / mouse |
| x, y, width, height | 900, 500, 30, 30 | CSS 픽셀 좌표와 접촉 크기 |
| buttons | 1 | `event.buttons` (펜 호버는 0) |
| slot, size | 3, 2.0 | 이벤트 직후의 펜 슬롯, 굵기(pt) |
| rec_state | ARMED | IDLE / ARMED / TUNING |
| n_touch, n_still | 2, 2 | 펜 다운 때 닿아 있는 손가락 수, 정지로 판정된 손가락 수 |
| detail | outcome=timeout | `키=값;키=값` 형식. **쉼표 금지** |

### 이벤트 목록

| 이벤트 | 기록 시점 | 필수 값 |
|---|---|---|
| pointerdown / pointermove / pointerup / pointercancel | 펜·터치 모두. `getCoalescedEvents()`로 받은 점 포함, 호버 포함 | pointer_id, pointer_type, x, y, width, height, buttons. 펜 pointerdown은 n_touch, n_still, source(canvas/ui)도 |
| block_start | 블록 시작 | detail: `build`, `still_px`, `still_ms`, `epoch_ms` (`Date.now()`). C2·C3는 `touch_to_pen_ms`(숫자 또는 `none`)도 |
| block_end | 블록 끝 | |
| cue_shown | 지시가 **화면에 그려진 뒤** (`requestAnimationFrame` 두 번 뒤의 시각) | step_id, slot, size |
| step_end | 단계 종료 | step_id, slot, size, detail: `outcome=completed/timeout/skipped` |

`step_end`의 outcome은 아래처럼 정한다.
- **completed:** v1.2: 목표 상태로 그은 획이 끝났다 (마지막 단계는 그 뒤 완료 버튼). v1.1: 참가자가 완료 버튼을 눌렀다. 버튼을 누른 펜 탭은 `source=ui`인 pointerdown/up으로 남고, 그 직후에 `step_end`를 남긴다.
- **완료를 일찍 누른 경우 (v1.2):** 새 값을 만들지 않는다. 진행 중 단계는 `skipped`, 남은 단계는 `step_end` 없음. 구분법은 위 v1.2 표 4번.
- **timeout:** 스크립트의 `time_limit_ms`가 지났다. 참가자에게 제한 시간은 보이지 않는다. 인식이 계속 실패해 단계에 갇히는 것을 막는 안전장치였다. **v1.2(11/26)에서 없앰.** 그 전 build 로그에만 나온다.
- **skipped:** 진행자가 건너뛰었다 (장비 문제 등). 이유는 `sessions.csv`의 `notes`에 적는다.
| toolbar_tap | 툴바 펜 선택 | source, slot, size |
| slider_start / slider_end | 슬라이더 조작 시작·끝 | source, slot, size |
| slot_change / size_change | 슬롯·굵기가 바뀔 때마다 | source, slot, size |
| activation | C2·C3 제스처가 인식된 순간. **슬롯이 안 바뀌어도 기록** | source, slot, size, rec_state, n_touch, n_still |
| gesture_commit | 펜 업으로 확정 | source, slot, size |
| rec_state | 인식기 상태 전환 | rec_state |
| ink_start / ink_end | 실제로 잉크가 남는 획의 시작·끝 | source, slot, size |

- 제스처로 처리된 펜 다운에는 `ink_start`를 남기지 않는다. 이 차이로 "먹힌 획"을 찾는다.
- 정지 판정 임계값이나 손→펜 간격을 바꿔 재계산하려면 터치의 `pointerdown`과 `pointermove`가 모두 필요하다.
- 분석의 펜 다운 수(`n_pen_downs`)는 `source=canvas`인 펜 다운만 센다. 툴바와 완료 버튼을 누른 횟수는 섞이지 않는다.

### 저장 규칙

- 블록이 끝날 때마다 파일로 저장한다. 탭이 죽어도 끝난 블록은 남아야 한다.
- 페이지를 새로고침하면 `performance.now()` 기준이 바뀌므로, 같은 블록을 이어 쓰지 말고 다시 시작한다.

### 구현 참고

필수 구현은 아니다. 기존 `Logger.log`를 이 정도로 바꾸면 형식을 맞출 수 있다.

```js
const EVENT_COLUMNS = ["schema_version", "session_id", "participant", "block", "condition",
  "phase", "exp", "script_id", "step_id", "seq", "t_event", "t_logged", "event", "source",
  "pointer_id", "pointer_type", "x", "y", "width", "height", "buttons", "slot", "size",
  "rec_state", "n_touch", "n_still", "detail"];

const LoggerSketch = {
  rows: [],
  seq: 0,
  meta: { schema_version: "1.1" },   // session_id, participant, block, condition 등을 블록마다 설정

  // domEvent를 넘기면 입력이 일어난 시각을 쓴다.
  log(event, fields = {}, domEvent = null) {
    const now = performance.now();
    this.seq += 1;
    this.rows.push({
      ...this.meta, seq: this.seq, event,
      t_event: domEvent ? domEvent.timeStamp : now, t_logged: now, ...fields,
    });
  },

  toCsv() {
    const lines = this.rows.map((row) => EVENT_COLUMNS.map((c) => row[c] ?? "").join(","));
    return [EVENT_COLUMNS.join(","), ...lines].join("\n") + "\n";
  },
};

// 펜 pointerdown의 source: 필기 영역(canvas) 밖이면 ui
const pointerSource = (e) => (e.target.closest("#canvas") ? "canvas" : "ui");
```

`#canvas`는 예시다. 실제 필기 영역 요소의 선택자로 바꾼다.

## scripts: 과제 스크립트

| 컬럼 | 예시 | 설명 |
|---|---|---|
| script_id, step_id | exp2C, s03 | 둘을 합쳐 고유해야 함 |
| exp | exp2 | exp1 / exp2 |
| step_type | switch_size | switch_only / size_only / switch_size / no_change (v1.1의 copy는 v1.2에서 없음) |
| task_type | circle | underline / highlight / circle / word / return(본문으로 돌아가기, v1.2) |
| language | ko | 쓰는 언어. 11/4 결정으로 **ko만 허용**. 언어가 없는 과제는 빈칸. copy는 필수 |
| cue_text | 빨간 펜 2pt | 상단 배너에 보이는 지시 (펜 이름 + 굵기) |
| target_slot | 3 | 빈칸 = 슬롯을 평가하지 않음 |
| target_size | 2.0 | 빈칸 = 굵기를 평가하지 않음 |
| on_preset | 1 | 목표 굵기가 프리셋이면 1, 사이값이면 0 |
| target_x, target_y | 400, 300 | 다음 획의 목표 위치 |
| text | 실험 설계 | 쓸 내용 |
| time_limit_ms | 60000 | 안전용 시간 제한 (ms). v1.1은 필수. **v1.2(11/26)에서 없앰** — 열은 비어도 된다 |

## sessions, participants, questionnaire

- **sessions.csv:** session_id, participant, condition_order(`C1-C3-C2`), script_variant, date, device, browser, windows, screen_w, screen_h, dpr, experimenter, notes
- **participants.csv:** participant, handedness, native_language(ko만 허용), note_language(평소 필기 습관 ko/en/mixed, 기술통계용), tablet_note_months
- **questionnaire.csv:** participant, condition, item(`tlx_mental`, `preference_rank` 등), value

## steps: 분석 표 (자동 생성, v1.2)

`build_steps.py`가 만든다. 한 줄 = 단계 하나. 단계표에 있는데 지시가 안 나온 단계도 `outcome=not_reached`로 남는다. 정의는 [분석 계획](analysis-plan.md) 4장.

| 묶음 | 컬럼 |
|---|---|
| 식별 | session_id, participant, block, condition, order_index, phase, exp, script_id, step_id, build |
| 과제 | step_type, task_type, target_slot, target_size, on_preset |
| 상태 | prev_slot, prev_size (이전 상태), needs_change (이전 상태가 이미 목표면 False), start_slot, start_size (지시 때 펜 상태) |
| 결과 | outcome (completed / skipped / timeout / not_reached / missing), skipped_by (participant / experimenter), prev_ink_fallback |
| 시각 | t_cue, t_prev_ink_end, t_first_action (제스처는 손가락이 닿은 때), t_first_action_event, t_last_action, t_first_attempt, t_first_correct, t_end |
| 시간 | time_prev_ink_to_correct (주 지표), time_cue_to_correct, time_reaction, time_manipulate, time_acquire, duration |
| 첫 시도 | first_slot, first_size, first_correct, first_size_log2_err |
| 횟수 | n_ink, n_body_strokes, n_wrong_slot, n_wrong_size, n_wrong_strokes, n_pen_downs, n_eraser_downs, n_toolbar_taps, n_slider_drags, n_activations, n_gestures, n_gesture_used, n_gesture_reverted, n_gesture_unchanged, n_penless_slot_change, n_possible_missed, n_pointercancel |

의도치 않은 발동률의 분모는 `n_pen_downs`(필기 영역 펜 다운 수)다. C3의 트리거가 펜 다운이고, 제시문마다 펜 다운 수가 다르기 때문이다.

`duration`(지시 → 단계 끝)은 본문 필기 시간까지 포함하므로 보조 지표로만 쓴다.

## 정해진 것 (11/4)

- [x] (노태림, 정원준) 형식 v1.0 승인 (PR #1)
- [x] (최유진) 언어: 지시문과 따라쓰기 모두 한국어 고정, 한국어 모국어 화자로 제한
- [x] (최유진) 지시: 상단 배너에 펜 이름 + 굵기. 슬롯 번호와 펜의 대응은 시작 전 설명문으로 안내
- [x] (최유진) 진행: 연습은 모두 같은 분량, 완료 버튼으로 다음 단계. 참가자에게 안 보이는 안전용 시간 제한을 단계마다 둔다 (값은 제시문 길이를 보고 조정)
- [x] (전원) 교수님 피드백: C1~C3는 유지. 다른 제스처 가능성은 논의에서 다룸

## 합의할 것

코드에는 잠정값이 들어가 있다. 결정되면 `build_steps.py`만 고치고 다시 실행한다.

- [ ] (노태림, 정원준) 손→펜 간격 규칙. 손가락이 닿은 뒤 몇 ms 안에 펜이 와야 제스처로 볼지 (`touch_to_pen_ms`). 내부 테스트 로그를 `replay_thresholds.py --window`로 다시 계산해 전환 단계는 살리고 따라쓰기 단계는 걸러지는 값을 고른다. DualKey, Consecutive Distant Taps 논문 참고
- [x] (전원) 단계별 시간 제한: 없앤다 (11/26)
- [ ] (최유진, 강민진) 슬롯별 굵기 기억 여부. `switch_only`의 굵기 평가 방식에 영향
- [x] (전원) 주 지표: `time_prev_ink_to_correct`(제안서 정의). 11/18 제시문형 결정으로 지시 시점보다 "이전 필기 획 끝"이 자연스러워졌다. v1.2에서 `t_prev_ink_end`는 목표 상태 첫 획 앞에서 **이전 상태로 그은 마지막 획**으로 바꾼다 ([분석 계획](analysis-plan.md) 4.1, 11/26 구체화)
- [ ] (파일럿 후) 굵기 정답 허용 범위. 잠정값: 목표의 1.10배 이내 (`SIZE_TOL_RATIO`)
- [ ] (파일럿 후) 의도치 않은 발동의 정의. v1.1 잠정값(copy 구간의 모든 `activation`)은 copy 단계가 없어져 못 쓴다. 후보는 [분석 계획](analysis-plan.md) 4.3
- [ ] (파일럿 후) 인식 실패 후보의 정의. 잠정값: 전환 단계에서 손가락이 닿았지만 `n_still = 0`인 펜 다운
