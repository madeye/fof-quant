"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark";

function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
  document.documentElement.dataset.theme = theme;
}

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    const stored = window.localStorage.getItem("fof-theme");
    const next: Theme =
      stored === "dark" || stored === "light"
        ? stored
        : window.matchMedia("(prefers-color-scheme: dark)").matches
          ? "dark"
          : "light";
    setTheme(next);
    applyTheme(next);
  }, []);

  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    window.localStorage.setItem("fof-theme", next);
    applyTheme(next);
  };

  return (
    <button
      type="button"
      onClick={toggle}
      className="btn min-h-9 px-3 py-1.5"
      aria-label={theme === "dark" ? "切换到浅色主题" : "切换到深色主题"}
    >
      <span>{theme === "dark" ? "Light" : "Dark"}</span>
    </button>
  );
}
