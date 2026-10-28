(function () {
  "use strict";

  var STORAGE_KEY = "kingdomsheet-dark-mode";
  var root = document.documentElement;
  var toggle = document.getElementById("dark-mode-toggle");
  var icon = document.getElementById("dark-mode-icon");
  var systemQuery = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

  function isDark() {
    return root.classList.contains("dark-mode");
  }

  function showIcon() {
    icon.textContent = isDark() ? "\u2600\uFE0F" : "\uD83C\uDF19";
  }

  function apply(dark) {
    root.classList.toggle("dark-mode", dark);
    showIcon();
  }

  toggle.addEventListener("click", function () {
    var dark = !isDark();
    localStorage.setItem(STORAGE_KEY, String(dark));
    apply(dark);
  });

  // Follow the system setting only until the visitor picks one.
  if (systemQuery) {
    var followSystem = function (event) {
      if (localStorage.getItem(STORAGE_KEY) === null) {
        apply(event.matches);
      }
    };
    if (systemQuery.addEventListener) {
      systemQuery.addEventListener("change", followSystem);
    } else if (systemQuery.addListener) {
      systemQuery.addListener(followSystem);
    }
  }

  showIcon();
})();
