// Count & Tune 실험 설문 폼(NASA-TLX + 선호 순위)을 만드는 Google Apps Script.
// 담당: 정원준 (분석). 응답은 analysis/form_to_questionnaire.py 로 questionnaire.csv 가 된다.
//
// 쓰는 법: script.google.com → 새 프로젝트 → 이 파일 내용을 붙여넣기 → makeForm 실행 → 권한 승인.
// 실행 로그에 응답용 주소와 편집용 주소가 나온다. 다시 실행하면 폼이 하나 더 생긴다 (기존 폼은 그대로).
//
// 구조 (참가자 한 명이 조건마다 한 번씩, 모두 세 번 낸다):
//   1쪽: 참가자 번호, 방금 끝난 방법이 몇 번째인지, NASA-TLX 6문항
//        → 첫째·둘째면 제출, 셋째면 2쪽으로
//   2쪽: 세 방법 선호 순위 (열마다 하나만), 의견(선택)
// 조건 이름(C1~C3)은 묻지 않는다. 참가자 번호와 "몇 번째"로 배정표(task.js ORDERS)에서 찾는다.
//
// NASA-TLX 척도: 원래는 0~100을 21칸(5점 간격)으로 받지만, 구글 폼 선형 배율은 최대 0~10이라
// 0~10(11칸)으로 받고 분석에서 ×10 한다 (analysis-plan.md 5장). 점수가 높을수록 부하가 크다.
// 수행(performance)도 원래 TLX처럼 0 = 완벽, 10 = 실패 방향이다.
//
// 참가자가 어느 방법이 우리 팀 기법인지 알지 못하게, 폼에는 Count & Tune 이라는 이름을 쓰지 않는다
// (다른 팀 학생이 참가자라 프로젝트 이름을 안다. 요구 특성 방지).
//
// 문항 제목을 바꾸면 form_to_questionnaire.py 의 대응표도 같이 고친다.

const TLX = [
  ["정신적 요구", "생각하기, 기억하기, 판단하기 등 정신적으로 얼마나 부담이 되었나요?", "매우 낮음", "매우 높음"],
  ["신체적 요구", "손과 팔을 움직이는 등 신체적으로 얼마나 부담이 되었나요?", "매우 낮음", "매우 높음"],
  ["시간적 요구", "과제를 하는 동안 얼마나 시간에 쫓기거나 서둘러야 한다고 느꼈나요?", "매우 낮음", "매우 높음"],
  ["수행", "과제를 얼마나 잘 해냈다고 생각하나요? (0이 완벽, 10이 실패)", "완벽", "실패"],
  ["노력", "그만큼 해내려고 얼마나 애써야 했나요?", "매우 낮음", "매우 높음"],
  ["좌절감", "과제를 하는 동안 얼마나 불안하거나, 짜증 나거나, 스트레스를 받았나요?", "매우 낮음", "매우 높음"],
];

const METHODS = [
  "툴바 + 슬라이더 (펜은 툴바에서 누르고, 굵기는 슬라이더로)",
  "툴바 + 손가락 굵기 (펜은 툴바에서 고르고, 굵기는 손가락을 댄 채 펜을 끌어서)",
  "손가락 개수 + 펜 끌기 (손가락 개수로 펜을 고르고, 그대로 펜을 끌어 굵기까지)",
];

function makeForm() {
  const form = FormApp.create("펜 전환 방법 비교 실험 설문");
  form.setDescription(
    "방법 하나가 끝날 때마다 이 설문을 한 번씩 작성합니다 (모두 세 번).\n" +
    "이름이나 연락처는 적지 않습니다. 진행자가 알려 준 참가자 번호만 적어 주세요.",
  );
  form.setCollectEmail(false);
  form.setAllowResponseEdits(false);
  form.setShowLinkToRespondAgain(true);   // 같은 기기에서 다음 방법 설문을 바로 이어서 낸다
  form.setProgressBar(false);
  form.setConfirmationMessage("제출했습니다. 진행자에게 알려 주세요.");

  form.addTextItem()
    .setTitle("참가자 번호")
    .setHelpText("진행자가 알려 준 번호 (예: P03)")
    .setRequired(true)
    .setValidation(FormApp.createTextValidation()
      .setHelpText("P와 두 자리 숫자로 적어 주세요 (예: P03)")
      .requireTextMatchesPattern("^[Pp][0-9]{2}$")
      .build());

  const order = form.addMultipleChoiceItem()
    .setTitle("방금 끝난 방법은 몇 번째인가요?")
    .setRequired(true);

  form.addSectionHeaderItem()
    .setTitle("방금 끝난 방법에 대한 질문")
    .setHelpText("방금 사용한 방법으로 과제를 할 때를 떠올리며, 각 문항에 0~10 중 하나를 고르세요.");
  TLX.forEach(([title, help, low, high]) => {
    form.addScaleItem()
      .setTitle(title)
      .setHelpText(help)
      .setBounds(0, 10)
      .setLabels(low, high)
      .setRequired(true);
  });

  const last = form.addPageBreakItem()
    .setTitle("세 방법 비교")
    .setHelpText("세 방법을 모두 써 보셨습니다. 쓰고 싶은 순서대로 순위를 매겨 주세요.");
  order.setChoices([
    order.createChoice("첫 번째", FormApp.PageNavigationType.SUBMIT),
    order.createChoice("두 번째", FormApp.PageNavigationType.SUBMIT),
    order.createChoice("세 번째 (마지막)", last),
  ]);

  form.addGridItem()
    .setTitle("선호 순위")
    .setHelpText("가장 쓰고 싶은 방법이 1위입니다. 순위마다 방법 하나씩만 고를 수 있어요.")
    .setRows(METHODS)
    .setColumns(["1위", "2위", "3위"])
    .setValidation(FormApp.createGridValidation()
      .setHelpText("순위마다 하나씩만 골라 주세요.")
      .requireLimitOneResponsePerColumn()
      .build())
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle("의견 (선택)")
    .setHelpText("좋았던 점, 불편했던 점, 헷갈렸던 점 등 자유롭게 적어 주세요.");

  Logger.log("응답용 주소: " + form.getPublishedUrl());
  Logger.log("편집용 주소: " + form.getEditUrl());
}
