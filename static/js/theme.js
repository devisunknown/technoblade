(function () {
  const STORAGE_KEY = "technoblade-theme";

  function getPreferredTheme() {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark") {
      return saved;
    }
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function applyTheme(theme) {
    document.documentElement.classList.toggle("dark", theme === "dark");
    document.querySelectorAll("[data-theme-label]").forEach((label) => {
      label.textContent = theme === "dark" ? "Light mode" : "Dark mode";
    });
  }

  window.toggleTheme = function () {
    const nextTheme = document.documentElement.classList.contains("dark") ? "light" : "dark";
    localStorage.setItem(STORAGE_KEY, nextTheme);
    applyTheme(nextTheme);
  };

  applyTheme(getPreferredTheme());
})();
