# 로그 형식 v1.0 (제안, 합의 전)

담당: 구현(노태림) + 분석(정원준). **바꿀 때는 두 사람이 합의하고 이 문서부터 고친다.**
코드 기준은 `analysis/logdata.py`이며, 이 문서와 함께 고친다.

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
| `scripts/script_<script_id>.csv` | 실험 설계 | 단계별 지시와 목표값 |
| `sessions.csv` | 실험 진행자 | 세션별 조건 순서, 장비, 특이사항 |
| `participants.csv` | 실험 진행자 | 참가자 정보 (이름 X) |
| `questionnaire.csv` | 실험 진행자 | 조건별 NASA-TLX, 선호도 |
| `steps.csv` | `build_steps.py` | 단계별 분석 표. 직접 고치지 않고 언제든 다시 생성 |

- **세션:** 참가자 한 명의 실험 한 번. `session_id`는 `P01-1` 형식이다. 중단 후 다시 시작하면 `P01-2`로 기록한다.
- **블록:** 조건 × phase × exp 하나를 끝까지 진행하는 단위. 세션 안에서 1부터 번호를 매긴다.

## events: 원시 이벤트

한 줄 = 이벤트 하나. 값이 없으면 빈칸으로 둔다.

| 컬럼 | 예시 | 설명 |
|---|---|---|
| schema_version | 1.0 | 이 문서의 버전 |
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
| source | gesture | toolbar / slider / gesture / pen |
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
| pointerdown / pointermove / pointerup / pointercancel | 펜·터치 모두. `getCoalescedEvents()`로 받은 점 포함, 호버 포함 | pointer_id, pointer_type, x, y, width, height, buttons. 펜 pointerdown은 n_touch, n_still도 |
| block_start | 블록 시작 | detail: `build`, `still_px`, `still_ms`, `epoch_ms` (`Date.now()`) |
| block_end | 블록 끝 | |
| cue_shown | 지시가 **화면에 그려진 뒤** (`requestAnimationFrame` 두 번 뒤의 시각) | step_id, slot, size |
| step_end | 단계 종료 | step_id, slot, size, detail: `outcome=completed/timeout/skipped` |
| toolbar_tap | 툴바 펜 선택 | source, slot, size |
| slider_start / slider_end | 슬라이더 조작 시작·끝 | source, slot, size |
| slot_change / size_change | 슬롯·굵기가 바뀔 때마다 | source, slot, size |
| activation | C2·C3 제스처가 인식된 순간. **슬롯이 안 바뀌어도 기록** | source, slot, size, rec_state, n_touch, n_still |
| gesture_commit | 펜 업으로 확정 | source, slot, size |
| rec_state | 인식기 상태 전환 | rec_state |
| ink_start / ink_end | 실제로 잉크가 남는 획의 시작·끝 | source, slot, size |

- 제스처로 처리된 펜 다운에는 `ink_start`를 남기지 않는다. 이 차이로 "먹힌 획"을 찾는다.
- 정지 판정 임계값을 바꿔 재계산하려면 터치의 `pointermove`가 모두 필요하다.

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
  meta: { schema_version: "1.0" },   // session_id, participant, block, condition 등을 블록마다 설정

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
```

## scripts: 과제 스크립트

| 컬럼 | 예시 | 설명 |
|---|---|---|
| script_id, step_id | exp2C, s03 | 둘을 합쳐 고유해야 함 |
| exp | exp2 | exp1 / exp2 |
| step_type | switch_size | switch_only / size_only / switch_size / copy |
| task_type | circle | underline / highlight / circle / word / copy / line 등 |
| language | ko | 쓰는 언어 ko / en. 언어가 없는 과제는 빈칸. copy는 필수 |
| cue_text | 빨간 펜 2pt | 화면 지시 |
| target_slot | 3 | 빈칸 = 슬롯을 평가하지 않음 |
| target_size | 2.0 | 빈칸 = 굵기를 평가하지 않음 |
| on_preset | 1 | 목표 굵기가 프리셋이면 1, 사이값이면 0 |
| target_x, target_y | 400, 300 | 다음 획의 목표 위치 |
| text | 실험 설계 | 쓸 내용 |

## sessions, participants, questionnaire

- **sessions.csv:** session_id, participant, condition_order(`C1-C3-C2`), script_variant, date, device, browser, windows, screen_w, screen_h, dpr, experimenter, notes
- **participants.csv:** participant, handedness, native_language, note_language(ko/en/mixed), english_proficiency, tablet_note_months
- **questionnaire.csv:** participant, condition, item(`tlx_mental`, `preference_rank` 등), value

## steps: 분석 표 (자동 생성)

| 묶음 | 컬럼 |
|---|---|
| 식별 | session_id, participant, block, condition, order_index, phase, exp, script_id, step_id |
| 과제 | step_type, task_type, language, target_slot, target_size, on_preset |
| 시작 상태 | start_slot, start_size |
| 결과 | outcome, first_slot, first_size, final_slot, final_size |
| 시각 | t_cue, t_prev_ink_end, t_first_action, t_last_action, t_first_ink, t_first_correct, t_end |
| 시간 | time_cue_to_correct, time_prev_ink_to_correct, time_reaction, time_manipulate, time_acquire, duration |
| 굵기 오차 | first_size_log2_err, final_size_log2_err |
| 횟수 | n_pen_downs, n_ink, n_toolbar_taps, n_slider_drags, n_gestures, n_activations, n_unintended, n_possible_missed, n_wrong_slot, n_wrong_size, n_pointercancel |

의도치 않은 발동률의 분모는 `n_pen_downs`다. C3의 트리거가 펜 다운이고, 언어에 따라 펜 다운 수가 달라질 수 있기 때문이다.

## 합의할 것

코드에는 잠정값이 들어가 있다. 결정되면 `build_steps.py`만 고치고 다시 실행한다.

- [ ] (노태림, 정원준) 이 형식 v1.0 승인
- [ ] (최유진) 필기 언어 방식과 스크립트 형식. 제안: 지시문 한국어 고정, 한국어 모국어 화자로 제한, 따라쓰기 구간 한/영 절반씩
- [ ] (최유진, 강민진) 다음 단계로 넘어가는 조건과 단계별 시간 제한
- [ ] (최유진, 강민진) 슬롯별 굵기 기억 여부. `switch_only`의 굵기 평가 방식에 영향
- [ ] (전원) 주 지표. `time_cue_to_correct`(스키마 초안)와 `time_prev_ink_to_correct`(Proposal) 중 선택. 둘 다 계산되므로 파일럿 전에 하나를 주 지표로 정한다.
- [ ] (파일럿 후) 굵기 정답 허용 범위. 잠정값: 목표의 1.10배 이내 (`SIZE_TOL_RATIO`)
- [ ] (파일럿 후) 의도치 않은 발동의 정의. 잠정값: copy 구간의 모든 `activation`
- [ ] (파일럿 후) 인식 실패 후보의 정의. 잠정값: 전환 단계에서 손가락이 닿았지만 `n_still = 0`인 펜 다운
