# 로그 CSV 형식 (초안, 11/1까지 확정)

담당: 구현(노태림) + 분석(정원준). **바꿀 때는 두 사람이 합의하고 이 문서부터 고친다.**

한 줄 = 과제 한 단계(step). 획 단위 원시 이벤트는 별도 파일로 저장할지 합의 필요.

| 컬럼 | 예시 | 설명 |
|---|---|---|
| participant | P01 | 참가자 ID (이름 X) |
| condition | C3 | C1 툴바+슬라이더 / C2 1손가락+드래그 / C3 Count & Tune |
| phase | main | practice / main (연습은 분석에서 제외) |
| exp | exp2 | exp1 굵기 맞추기 / exp2 필기 스크립트 |
| trial | 12 | 조건 안에서의 단계 번호 |
| step_type | switch_size | switch_only / size_only / switch_size / copy(따라쓰기) |
| target_slot | 3 | 지시된 펜 슬롯 (copy면 빈칸) |
| target_size | 2.0 | 지시된 굵기 pt |
| t_cue | 10234.5 | 지시 배너가 뜬 시각 (ms, performance.now) |
| t_first_correct | 11890.2 | 올바른 펜·굵기로 첫 획을 시작한 시각 |
| final_slot | 3 | 실제로 쓴 펜 슬롯 |
| final_size | 2.1 | 실제로 쓴 굵기 pt |
| n_actions | 2 | 단계 안에서 조작 횟수 (탭·드래그) |
| error_type | wrong_slot | none / wrong_slot / wrong_size / unintended_activation |
| n_unintended | 0 | 단계 안 의도치 않은 발동 수 (copy 구간에서 핵심) |
| n_strokes | 14 | 단계 안 획 수 (획 100개당 발동률 계산용) |

## 합의할 것
- [ ] 의도치 않은 발동의 정의 (C3: 지시 없이 슬롯이 바뀐 경우?)
- [ ] 획 단위 원시 로그를 따로 남길지
- [ ] 파일명 규칙 (예: `P01_C3_main.csv`)
