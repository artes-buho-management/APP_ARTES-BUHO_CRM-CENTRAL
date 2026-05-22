function doGet() {
  return HtmlService.createTemplateFromFile("Index")
    .evaluate()
    .setTitle(CC_CONFIG.APP_TITLE)
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}
