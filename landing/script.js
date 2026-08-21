// Highlights the download button matching the visitor's OS — both buttons
// always stay real links either way, this just reorders visual emphasis
// rather than hiding a platform.
(function () {
  var ua = navigator.userAgent || '';
  var platform = navigator.platform || '';
  var isMac = /Mac/i.test(platform) || /Macintosh/i.test(ua);
  var isWin = /Win/i.test(platform) || /Windows/i.test(ua);

  var macBtn = document.getElementById('btn-download-mac');
  var winBtn = document.getElementById('btn-download-win');
  if (!macBtn || !winBtn) return;

  if (isWin) {
    winBtn.classList.add('btn--primary');
    winBtn.classList.remove('btn--secondary');
    macBtn.classList.add('btn--secondary');
    macBtn.classList.remove('btn--primary');
  } else if (isMac) {
    macBtn.classList.add('btn--recommended');
  }
})();
