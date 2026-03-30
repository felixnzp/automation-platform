export const THEME_KEY = "theme-mode";
export const THEME_MODES = ["system", "light", "dark"];

export const getStoredTheme = () => {
  const mode = localStorage.getItem(THEME_KEY);
  return THEME_MODES.includes(mode) ? mode : "system";
};

const getSystemTheme = () =>
  window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";

const applyResolvedTheme = (mode) => {
  document.documentElement.classList.remove("theme-light", "theme-dark");
  document.documentElement.classList.add(`theme-${mode}`);
};

export const applyTheme = (mode) => {
  const normalizedMode = THEME_MODES.includes(mode) ? mode : "system";
  const resolved = normalizedMode === "system" ? getSystemTheme() : normalizedMode;

  applyResolvedTheme(resolved);
  localStorage.setItem(THEME_KEY, normalizedMode);
  return resolved;
};

export const initTheme = () => {
  const mode = getStoredTheme();
  applyTheme(mode);

  if (window.matchMedia) {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", () => {
      if (getStoredTheme() === "system") {
        applyTheme("system");
      }
    });
  }
};
