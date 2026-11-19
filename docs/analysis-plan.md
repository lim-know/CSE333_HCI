# 분석 계획 (초안)

담당: 정원준. 상태: **초안 (팀 검토 전)**, 11/20 작성.
본실험(12월 초) 시작 전에 이 문서를 확정하고, 그 뒤에 바꾸면 아래 "변경 이력"에 이유와 함께 남긴다.

- 로그 형식: [`docs/log-schema.md`](log-schema.md) v1.2 (제안)
- 실험 구조와 이 계획이 어떤 PR에 기대고 있는지: [3. 전제와 PR 의존 관계](#3-전제와-pr-의존-관계)
- 가설 원문: 제안서(`docs/submissions/Proposal_Team4_submitted.pptx`) 9쪽

## 변경 이력

| 날짜 | 내용 |
|---|---|
| 11/20 | 초안. 제시문형 과제(PR #10)와 PR #11(리뷰 중) 기준 |

## 1. 기본 방침

교수님 피드백을 고려해 **해석이 단순하고 타당성을 설명하기 쉬운 쪽**을 고른다.

1. **가설마다 one-way 반복측정 하나.** 요인은 조건(C1·C2·C3) 하나뿐이다. 단계 종류는 요인으로 넣지 않고, 가설에 맞는 단계만 골라 쓴다 (H1은 펜+굵기 단계, H2는 굵기만 단계). 조건 × 단계 종류 같은 two-way는 쓰지 않는다.
2. **참가자 × 조건 한 칸에 값 하나.** 같은 사람의 여러 시행을 독립 표본으로 세지 않는다. 시간은 로그로 바꾼 뒤 평균한다 (= 기하평균).
3. **모수 검정이 주, 비모수 검정으로 확인.** 모든 시간 분석은 RM-ANOVA와 Friedman을 같이 보고한다. 둘의 결론이 다르면 그 사실을 그대로 쓰고 강한 결론을 내리지 않는다. 데이터를 본 뒤에 검정을 고르지 않기 위해서다.
4. **양측 검정이 기본.** 단측은 비열등성(H3)처럼 가설 자체가 한쪽인 경우에만 쓴다.
5. **판단 기준은 데이터 수집 전에 고정.** 제외 규칙, 이상치 기준, TOST 마진을 본실험 전에 확정한다. 파일럿 데이터는 기준을 정하는 데만 쓰고 결과에 넣지 않는다.
6. **효과크기와 신뢰구간을 p값과 같이 보고.** n = 12라 p값만으로 판단하지 않는다.

도구: Python 3.12, pandas, **pingouin 0.7.0** (`analysis/requirements.txt`). 코드 예시는 [부록](#부록-pingouin-코드-예시).

## 2. 실험 구조 (분석 관점)

- 참가자 12명, 조건 3개 모두 수행 (within-subject). 조건 순서 6가지 × 2명, 제시문 세트(A·B·C)도 같이 돌린다.
- 조건 하나 = 연습 제시문 1개 + 본과제 제시문 5개. **연습은 분석하지 않는다.**
- 제시문을 아래 칸에 옮겨 쓰면서, 표시된 곳을 지정한 펜·굵기로 표시한다. 본문은 검정 1pt.
- **단계 = 펜 상태(슬롯·굵기)를 바꿔야 하는 곳.** 표시마다 "표시 상태로 바꾸기" 단계가 있고, 뒤에 본문이 이어지면 "본문으로 돌아가기"(`return`) 단계가 붙는다.
- PR #11 기준 조건 하나의 본과제 단계 (세트 A·B·C 모두 같음, 코드로 확인):

| 단계 종류 | 표시 단계 | 본문 복귀 단계 | 쓰는 가설 |
|---|---|---|---|
| `switch_size` (펜 + 굵기) | 5 | 0 | H1 |
| `size_only` (굵기만) | 8 | 3 | H2 |
| `switch_only` (펜만) | 2 | 2 | 보조 |
| 합계 | 15 | 5 | |

H1은 참가자 × 조건마다 5번이라 적은 편이다. 한 번이 timeout이면 그 칸은 4번으로 계산한다.

## 3. 전제와 PR 의존 관계

이 계획은 아래 구현을 전제로 한다. **전제가 바뀌면 이 표의 "안 되면" 칸대로 계획을 고친다.** 로그만 보고 어느 버전인지 알 수 있도록 `block_start`의 `build` 값으로 버전을 구분한다 ([log-schema v1.2](log-schema.md#v12-변경-제안과-pr-의존-관계)).

| 전제 | 근거 | 상태 (11/20) | 안 되면 |
|---|---|---|---|
| 제시문형 과제, `return` 단계 | PR #10 | 머지됨 | — |
| 정답 획이 나오면 다음 단계로 자동 진행 | PR #10 | 머지됨 | — |
| 글씨 표시를 먼저, 밑줄·동그라미·칠하기는 나중에 | PR #11 | 리뷰 중 | PR #10의 읽는 순서. 단계 수만 다시 센다 |
| 조건당 본과제 제시문 5개 | PR #11 | 리뷰 중 | PR #10의 1개 (단계 12개). H1 시행이 칸당 2번이라 **H1 검정이 어려워진다** |
| 표시를 남기고 완료하면 `incomplete` 기록 | PR #11 리뷰 1번 | 수정 요청 | 그 블록의 마지막 단계는 판정을 못 믿으므로 분석에서 뺀다 |
| 블록마다 로그 파일 저장, 단계표(script) 저장 | PR #11 리뷰 2·3번 | 수정 요청 | 단계표는 코드에서 다시 만든다. 로그가 빠진 블록은 결측 처리 |
| 버전마다 `build` 값 변경 | PR #11 리뷰 3번 | 수정 요청 | 실험 기록(`sessions.csv` notes)에 커밋을 적어 구분 |
| 굵기 1~8pt 정수 선형 눈금 | PR #11 | 리뷰 중 | 0.5~8pt 로그 눈금. 굵기 오차는 log2 비율이라 계산은 그대로 |
| C3 펜 결정 시점 | PR #11 리뷰 4번 | 팀 결정 필요 | 펜 다운 시점(v1.1). 의도치 않은 발동 정의 ②가 없어진다 |

## 4. 측정값 정의

모두 `analysis/build_steps.py`가 원시 로그에서 계산한다. 브라우저는 판정을 하지 않는다.

### 4.1 한 단계 안의 시각

```
 이전 상태로 필기 ... [마지막 필기 획 끝] → [첫 조작] ... [마지막 조작] → [목표 상태 첫 획 시작]
                      t_prev_ink_end      t_first_action  t_last_action   t_first_correct
```

- **이전 상태**: 바로 앞 단계의 목표 상태. 블록의 첫 단계는 본문 상태(검정 1pt).
- **조작**: 펜 상태를 바꾸려는 입력. C1·C2는 툴바·슬라이더를 누른 펜 다운(`source=ui`), C2·C3는 제스처를 만든 손가락 터치.
- **t_prev_ink_end**: 첫 조작 **직전**에 끝난 필기 획. v1.1은 "지시가 뜨기 전 마지막 획"이었으나, 제시문형에서는 지시가 뜬 뒤에도 본문을 이어 쓰므로 바꾼다. 블록 안에 앞선 획이 없으면 지시 시각(`cue_shown`)을 쓰고 표시해 둔다.
- **t_first_correct**: 지시 이후 목표 슬롯과 목표 굵기(1.10배 이내)로 그은 첫 획의 시작.

### 4.2 지표

| 지표 | 정의 | 쓰는 곳 |
|---|---|---|
| **전환 시간** (주 지표) | t_first_correct − t_prev_ink_end. 제안서 정의와 같다 | H1, H2 |
| 반응 / 조작 / 획 시작 | t_first_action − t_prev_ink_end / t_last_action − t_first_action / t_first_correct − t_last_action | 보조 (어디서 시간이 드는지) |
| 첫 시도 굵기 오차 | 첫 조작 이후 첫 획의 \|log2(굵기 / 목표)\|. 0이면 정확 | H3 |
| 첫 시도 정답률 | 첫 조작 이후 첫 획이 목표 상태인 비율 | H3 보조 |
| 오답 획 | 이전 상태도 목표 상태도 아닌 펜·굵기로 그은 획. **이전 상태로 쓴 본문 획은 오답이 아니다** | H4 |
| 의도치 않은 발동 | 4.3 참고 | H4 |
| 인식 실패 후보 | 손가락이 닿아 있는데 정지로 판정되지 않은 펜 다운 (`n_touch ≥ 1`, `n_still = 0`) | 보조 |
| NASA-TLX | 6문항 평균 (가중치 없는 Raw TLX) | H5 |
| 선호 순위 | 1~3위 | H5 |

**최종 굵기 오차는 쓰지 않는다.** 맞는 굵기로 그어야 다음 단계로 넘어가므로 최종 오차는 항상 허용 범위 안이다. 그래서 H3은 첫 시도로 본다.

### 4.3 의도치 않은 발동 (파일럿 후 확정)

v1.1은 "따라쓰기(copy) 단계의 모든 발동"이었는데, 제시문형에는 copy 단계가 없다. 후보:

1. **되돌린 발동**: 제스처로 상태가 바뀐 뒤, 목표 상태로 쓰지 않고 이전 상태로 되돌려 필기를 이어간 경우.
2. **펜 없는 슬롯 변경** (C3, PR #11 동작일 때만): 펜을 대지 않았는데 손가락 정지만으로 슬롯이 바뀐 경우 (`slot_change`가 `activation` 없이 생김).

**파일럿 영상과 로그를 맞춰 보고** 실제로 의도치 않은 경우를 잘 잡는 정의를 고른다. 비율의 분모는 필기 영역 펜 다운 수다.

## 5. 가설별 분석

모든 가설에 공통으로, 본과제(`phase=main`) 단계만 쓰고 6장의 제외 규칙을 먼저 적용한다.

| 가설 | 데이터 | 주 검정 | 확인용 검정 |
|---|---|---|---|
| **H1** 펜+굵기 단계: C3가 C1·C2보다 빠름 | `switch_size` 표시 단계의 전환 시간 (로그) | one-way RM-ANOVA → 대응 t 검정 3쌍 (Holm) | Friedman → Wilcoxon 3쌍 (Holm) |
| **H2** 굵기만 단계: C2 ≈ C3, 둘 다 C1보다 빠름 | `size_only` 표시 단계의 전환 시간 (로그) | ① one-way RM-ANOVA → C1–C2, C1–C3 대응 t (Holm) ② C2–C3 동등성 TOST | ① Friedman → Wilcoxon |
| **H3** 굵기 오차: C3가 C1보다 나쁘지 않음 | 굵기를 바꾸는 표시 단계(`switch_size`, `size_only`)의 첫 시도 굵기 오차 | C3–C1 비열등성 (단측 대응 t, 마진 log2(1.10)) | 첫 시도 정답률 Friedman |
| **H4** 모드 오류: C3가 C1보다 많음 (예상되는 비용) | 펜 다운 100회당 (오답 획 + 의도치 않은 발동) | Friedman → Wilcoxon 3쌍 (Holm) | 구성요소별 기술통계 |
| **H5** 작업 부하: C3가 낮고 선호됨 | NASA-TLX 평균, 선호 순위 | Friedman → Wilcoxon (Holm) | 문항별 기술통계 |

- **H4·H5는 비모수가 주 검정**이다. 오류 횟수는 0이 많고, TLX·순위는 순서 척도이기 때문이다.
- **TOST 마진 (H2)**: 로그 시간 차이 ±ln(1.25), 즉 "한쪽이 다른 쪽의 0.8~1.25배 안이면 같다". 생물학적 동등성 시험에서 쓰는 관례 범위다. 파일럿에서 이 폭이 너무 넓거나 좁아 보이면 **본실험 전에만** 바꾼다.
- **비열등성 마진 (H3)**: log2(1.10). 정답으로 인정하는 굵기 허용 범위와 같은 폭이다. "C3의 첫 시도 오차가 C1보다 허용 범위 이상 나쁘지 않다"를 본다.
- n = 12라 TOST로 동등성이 안 나와도 "다르다"는 뜻이 아니다. 신뢰구간을 같이 보고한다.
- 다중 비교: **가설 하나 안에서만** Holm 보정한다. 가설끼리는 따로 세운 질문으로 본다.

### 보조 분석 (가설 검정 아님, 기술통계와 그림)

- `switch_only` 단계와 `return` 단계의 전환 시간
- 반응 / 조작 / 획 시작으로 나눈 시간: 조건 차이가 어디서 생기는지
- **순서 효과 점검**: 조건 순서상 위치(첫째·둘째·셋째)를 요인으로 전환 시간을 one-way로 본다. 카운터밸런싱으로 상쇄되지만, 학습 효과가 크면 보고한다.
- 인식 실패 후보, 지우개 사용 (`pointerdown`의 `buttons`로 확인)

## 6. 제외와 이상치

| 대상 | 규칙 | 보고 |
|---|---|---|
| 연습 블록 | 분석 안 함 | — |
| timeout · skipped · incomplete 단계 | 시간 지표에서 뺀다. 오류·완료율에는 넣는다 | 조건별 개수 |
| 앞선 필기 획이 없는 단계 | 지시 시각을 기준으로 계산하고, 뺀 결과도 같이 본다 (민감도 분석) | 개수 |
| 이상치 | 참가자 × 조건 × 단계 종류 안에서 로그 전환 시간이 중앙값 ± 3 MAD 밖 | 조건별 개수 |
| 장비 문제 | 진행자가 `sessions.csv` notes에 적은 블록 | 사유 |
| 참가자 | 한 조건에서 본과제 단계의 25% 넘게 제외되면 그 참가자를 빼고, 가능하면 같은 순서로 1명 추가 모집 | 사유 |

반복측정 ANOVA는 빈 칸이 있으면 그 참가자 전체가 빠진다. 빠진 참가자 수를 같이 보고한다.

## 7. 파일럿에서 정할 것

| 항목 | 지금 잠정값 | 정하는 방법 |
|---|---|---|
| 굵기 정답 허용 범위 | 목표의 1.10배 | 파일럿에서 "맞게 고른" 획의 굵기 분포 |
| 의도치 않은 발동 정의 | 4.3의 후보 1·2 | 파일럿 영상과 로그 대조 |
| TOST 마진 | ±ln(1.25) | 파일럿 전환 시간의 참가자 내 변동 |
| 단계별 시간 제한 | 60초 | timeout 비율 |
| 이상치 기준 | 3 MAD | 파일럿에서 몇 개가 걸리는지 |

파일럿 데이터(`data/pilot/`)는 위 기준을 정하는 데만 쓰고 본실험 결과에 합치지 않는다.

## 8. 보고할 그림·표

- 조건별 전환 시간: 참가자 한 명당 점 하나 + 선으로 연결 (가설마다 한 그림)
- 조건별 첫 시도 굵기 오차, 모드 오류율
- NASA-TLX 문항별, 선호 순위 분포
- 제외된 단계 수 표

## 부록: pingouin 코드 예시

`analysis/stats.py`로 옮길 때의 틀이다. `steps`는 `build_steps.py`가 만든 표(한 줄 = 단계 하나)라고 가정한다.

```python
import numpy as np
import pandas as pd
import pingouin as pg


def cell_means(steps: pd.DataFrame, step_type: str) -> pd.DataFrame:
    """가설 하나에 쓸 표를 만든다: 참가자 × 조건마다 값 하나.

    결과 예시 (긴 형식, pingouin 이 받는 모양):
        participant  condition  log_t
        P01          C1         7.31
        P01          C2         7.02
        ...
    """
    use = steps[
        (steps["phase"] == "main")              # 연습 블록 제외
        & (steps["task_type"] != "return")       # 본문 복귀 단계는 보조 분석으로
        & (steps["step_type"] == step_type)      # H1 이면 "switch_size", H2 면 "size_only"
        & (steps["outcome"] == "completed")      # timeout·skipped·incomplete 는 시간에서 제외
        & ~steps["is_outlier"]                   # 6장의 3 MAD 규칙으로 미리 표시해 둔 열
    ].copy()
    # 시간은 오른쪽으로 꼬리가 긴 분포라 로그로 바꾼 뒤 평균한다 (= 기하평균).
    use["log_t"] = np.log(use["time_prev_ink_to_correct"])
    # 한 참가자의 같은 조건 단계들을 평균 하나로 줄인다. 이렇게 해야 시행을 독립 표본으로 세지 않는다.
    return use.groupby(["participant", "condition"], as_index=False)["log_t"].mean()


def one_way(cells: pd.DataFrame, dv: str = "log_t") -> dict:
    """조건 하나(C1·C2·C3)짜리 반복측정 분석. 모수와 비모수를 같이 낸다."""
    common = dict(data=cells, dv=dv, within="condition", subject="participant")
    return {
        # 반복측정 ANOVA. correction=True 면 구형성이 깨졌을 때 쓰는
        # Greenhouse-Geisser 보정 p값(p_GG_corr)도 같이 나온다.
        # 효과크기 ng2 = 일반화 에타 제곱 (반복측정 설계끼리 비교하기 좋은 값).
        "anova": pg.rm_anova(**common, correction=True, effsize="ng2"),
        # 세 쌍(C1-C2, C1-C3, C2-C3) 대응 t 검정 + Holm 보정. 효과크기는 Hedges g.
        "pairs": pg.pairwise_tests(**common, padjust="holm", effsize="hedges"),
        # 확인용 비모수: Friedman 검정 (효과크기 W = Kendall 일치도).
        "friedman": pg.friedman(**common),
        # 확인용 비모수 사후 비교: Wilcoxon 부호순위 검정 + Holm.
        "pairs_np": pg.pairwise_tests(**common, parametric=False, padjust="holm"),
    }


def wide(cells: pd.DataFrame, dv: str = "log_t") -> pd.DataFrame:
    """긴 형식 → 넓은 형식 (행 = 참가자, 열 = C1·C2·C3). 두 조건만 비교할 때 쓴다."""
    return cells.pivot(index="participant", columns="condition", values=dv)


# H2 의 C2 ≈ C3 동등성 (TOST).
# bound = ln(1.25): 로그 시간 차이가 ±ln(1.25) 안이면 "같다"고 본다.
# paired=True: 같은 참가자의 두 조건을 짝지어 비교한다.
# 결과의 pval < .05 이면 동등하다고 말할 수 있다.
def h2_equivalence(cells: pd.DataFrame) -> pd.DataFrame:
    w = wide(cells)
    return pg.tost(w["C2"], w["C3"], bound=np.log(1.25), paired=True)


# H3 의 비열등성: "C3 의 오차가 C1 보다 margin 이상 크지 않다".
# 귀무가설: (C3 - C1) >= margin.  대립가설: (C3 - C1) < margin.
# C3 에서 margin 을 빼고 C1 과 단측(less) 대응 t 검정을 하면 같은 검정이 된다.
def h3_noninferiority(err_cells: pd.DataFrame, margin: float = np.log2(1.10)) -> pd.DataFrame:
    w = wide(err_cells, dv="abs_log2_err")
    return pg.ttest(w["C3"] - margin, w["C1"], paired=True, alternative="less")
```
