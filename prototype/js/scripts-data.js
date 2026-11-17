// 담당: 최유진 (과제 내용) · 형식: docs/log-schema.md 의 scripts 표
// !! 지금 들어 있는 과제는 11/17 정원준이 만든 '임시' 과제입니다. 유진님이 정하면 통째로 바꿔 주세요.
//    (유형별 4개 = 12단계 + 따라쓰기 3개. 세트 A/B/C는 구조·위치가 같고 단어만 다름)
// 고치는 법: 엑셀/구글 시트에서 같은 컬럼으로 만들고 CSV로 저장 → 아래 ` ` 안에 통째로 붙여넣기.
//  - target_x, target_y: 필기 영역 왼쪽 위 기준 위치(px). 화면 밖이면 안쪽으로 당겨서 보여 줌
//  - time_limit_ms: 참가자에게 안 보이는 안전용 시간 제한
//  - 세션이 끝나면 사용한 스크립트가 script_<id>.csv 로 같이 저장됨 (분석용)

const SCRIPT_CSV = {
  practice: `script_id,step_id,exp,step_type,task_type,language,cue_text,target_slot,target_size,on_preset,target_x,target_y,text,time_limit_ms
practice,p01,exp2,switch_size,circle,,빨간 펜 2pt,2,2,1,980,340,연습,30000
practice,p02,exp2,size_only,underline,,지금 펜 8pt,,8,1,600,300,예시,30000
practice,p03,exp2,switch_only,highlight,,노란 형광펜,3,,,340,280,도구,30000
practice,p04,exp2,copy,copy,ko,아래 문장을 따라 쓰세요,,,,280,300,천천히 따라 써 보세요,60000
practice,p05,exp2,size_only,highlight,,지금 펜 1pt,,1,1,260,200,굵기,30000
practice,p06,exp2,switch_only,circle,,검정 펜,1,,,520,300,형광,30000
practice,p07,exp2,switch_size,underline,,빨간 펜 1pt,2,1,1,660,320,표시,30000
`,
  exp2A: `script_id,step_id,exp,step_type,task_type,language,cue_text,target_slot,target_size,on_preset,target_x,target_y,text,time_limit_ms
exp2A,s01,exp2,size_only,underline,,지금 펜 4pt,,4,1,980,220,가설,30000
exp2A,s02,exp2,switch_size,underline,,빨간 펜 8pt,2,8,1,860,420,표본,30000
exp2A,s03,exp2,switch_only,underline,,검정 펜,1,,,400,540,분산,30000
exp2A,s04,exp2,copy,copy,ko,아래 문장을 따라 쓰세요,,,,280,300,표본이 클수록 추정이 안정된다,60000
exp2A,s05,exp2,switch_size,underline,,빨간 펜 2pt,2,2,1,320,360,평균,30000
exp2A,s06,exp2,switch_only,circle,,검정 펜,1,,,960,540,회귀,30000
exp2A,s07,exp2,size_only,underline,,지금 펜 2pt,,2,1,640,420,상관,30000
exp2A,s08,exp2,copy,copy,ko,아래 문장을 따라 쓰세요,,,,280,300,분산은 퍼진 정도를 나타낸다,60000
exp2A,s09,exp2,switch_only,highlight,,노란 형광펜,3,,,980,560,검정력,30000
exp2A,s10,exp2,size_only,highlight,,지금 펜 0.5pt,,0.5,1,680,200,유의수준,30000
exp2A,s11,exp2,switch_size,circle,,빨간 펜 4pt,2,4,1,700,200,효과크기,30000
exp2A,s12,exp2,copy,copy,ko,아래 문장을 따라 쓰세요,,,,280,300,검정 전에 가정을 확인한다,60000
exp2A,s13,exp2,switch_only,circle,,검정 펜,1,,,640,360,표준편차,30000
exp2A,s14,exp2,size_only,circle,,지금 펜 1pt,,1,1,280,580,중앙값,30000
exp2A,s15,exp2,switch_size,highlight,,노란 형광펜 2pt,3,2,1,880,560,신뢰구간,30000
`,
  exp2B: `script_id,step_id,exp,step_type,task_type,language,cue_text,target_slot,target_size,on_preset,target_x,target_y,text,time_limit_ms
exp2B,s01,exp2,size_only,underline,,지금 펜 4pt,,4,1,980,220,세포막,30000
exp2B,s02,exp2,switch_size,underline,,빨간 펜 8pt,2,8,1,860,420,효소,30000
exp2B,s03,exp2,switch_only,underline,,검정 펜,1,,,400,540,단백질,30000
exp2B,s04,exp2,copy,copy,ko,아래 문장을 따라 쓰세요,,,,280,300,효소는 반응 속도를 높인다,60000
exp2B,s05,exp2,switch_size,underline,,빨간 펜 2pt,2,2,1,320,360,유전자,30000
exp2B,s06,exp2,switch_only,circle,,검정 펜,1,,,960,540,삼투압,30000
exp2B,s07,exp2,size_only,underline,,지금 펜 2pt,,2,1,640,420,광합성,30000
exp2B,s08,exp2,copy,copy,ko,아래 문장을 따라 쓰세요,,,,280,300,세포막은 물질 출입을 조절한다,60000
exp2B,s09,exp2,switch_only,highlight,,노란 형광펜,3,,,980,560,호흡,30000
exp2B,s10,exp2,size_only,highlight,,지금 펜 0.5pt,,0.5,1,680,200,항상성,30000
exp2B,s11,exp2,switch_size,circle,,빨간 펜 4pt,2,4,1,700,200,미토콘드리아,30000
exp2B,s12,exp2,copy,copy,ko,아래 문장을 따라 쓰세요,,,,280,300,광합성은 빛 에너지를 쓴다,60000
exp2B,s13,exp2,switch_only,circle,,검정 펜,1,,,640,360,리보솜,30000
exp2B,s14,exp2,size_only,circle,,지금 펜 1pt,,1,1,280,580,염색체,30000
exp2B,s15,exp2,switch_size,highlight,,노란 형광펜 2pt,3,2,1,880,560,촉매,30000
`,
  exp2C: `script_id,step_id,exp,step_type,task_type,language,cue_text,target_slot,target_size,on_preset,target_x,target_y,text,time_limit_ms
exp2C,s01,exp2,size_only,underline,,지금 펜 4pt,,4,1,980,220,수요,30000
exp2C,s02,exp2,switch_size,underline,,빨간 펜 8pt,2,8,1,860,420,공급,30000
exp2C,s03,exp2,switch_only,underline,,검정 펜,1,,,400,540,탄력성,30000
exp2C,s04,exp2,copy,copy,ko,아래 문장을 따라 쓰세요,,,,280,300,가격이 오르면 수요가 준다,60000
exp2C,s05,exp2,switch_size,underline,,빨간 펜 2pt,2,2,1,320,360,균형가격,30000
exp2C,s06,exp2,switch_only,circle,,검정 펜,1,,,960,540,기회비용,30000
exp2C,s07,exp2,size_only,underline,,지금 펜 2pt,,2,1,640,420,한계효용,30000
exp2C,s08,exp2,copy,copy,ko,아래 문장을 따라 쓰세요,,,,280,300,관세는 수입품 가격을 올린다,60000
exp2C,s09,exp2,switch_only,highlight,,노란 형광펜,3,,,980,560,독점,30000
exp2C,s10,exp2,size_only,highlight,,지금 펜 0.5pt,,0.5,1,680,200,관세,30000
exp2C,s11,exp2,switch_size,circle,,빨간 펜 4pt,2,4,1,700,200,환율,30000
exp2C,s12,exp2,copy,copy,ko,아래 문장을 따라 쓰세요,,,,280,300,환율은 수출에 영향을 준다,60000
exp2C,s13,exp2,switch_only,circle,,검정 펜,1,,,640,360,물가,30000
exp2C,s14,exp2,size_only,circle,,지금 펜 1pt,,1,1,280,580,소비자잉여,30000
exp2C,s15,exp2,switch_size,highlight,,노란 형광펜 2pt,3,2,1,880,560,외부효과,30000
`,
};
