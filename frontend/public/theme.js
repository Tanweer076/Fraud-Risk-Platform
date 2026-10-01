// Applies the saved or system colour theme before the app renders, so the page never flashes.
(function () {
  var theme = "light";
  try {
    var saved = localStorage.getItem("theme");
    var dark =
      saved === "dark" ||
      (saved !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    theme = dark ? "dark" : "light";
  } catch (e) {
    // Storage can be blocked; fall back to light.
  }
  document.documentElement.dataset.theme = theme;
})();
