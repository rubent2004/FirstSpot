import { computed, ref } from "vue";

export type ThemeMode = "dark" | "light";

const currentTheme = ref<ThemeMode>("dark");

function getStorageItem(key: string): string | null {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      return window.localStorage.getItem(key);
    }
  } catch {
    // Ignore storage errors in test or restricted environments
  }
  return null;
}

function setStorageItem(key: string, value: string): void {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      window.localStorage.setItem(key, value);
    }
  } catch {
    // Ignore storage errors in test or restricted environments
  }
}

function applyThemeToDom(theme: ThemeMode): void {
  if (typeof document === "undefined" || !document.documentElement) return;
  const root = document.documentElement;
  if (theme === "dark") {
    root.classList.add("dark", "theme-dark");
    root.classList.remove("theme-light");
    root.style.colorScheme = "dark";
  } else {
    root.classList.remove("dark", "theme-dark");
    root.classList.add("theme-light");
    root.style.colorScheme = "light";
  }
}

// Initialize theme from localStorage or default to dark
const saved = getStorageItem("eoc_theme") as ThemeMode | null;
if (saved === "light" || saved === "dark") {
  currentTheme.value = saved;
} else {
  currentTheme.value = "dark";
}
applyThemeToDom(currentTheme.value);

export function useTheme() {
  const isDark = computed(() => currentTheme.value === "dark");

  function toggleTheme(): void {
    setTheme(currentTheme.value === "dark" ? "light" : "dark");
  }

  function setTheme(theme: ThemeMode): void {
    currentTheme.value = theme;
    setStorageItem("eoc_theme", theme);
    applyThemeToDom(theme);
  }

  return {
    theme: currentTheme,
    isDark,
    toggleTheme,
    setTheme,
  };
}
