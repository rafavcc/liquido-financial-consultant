import { useCallback, useEffect, useState } from "react";
import { readStore, writeStore } from "./storage";

export type Tema = "claro" | "escuro" | "sistema";
const KEY = "liquido.tema";

function applyTheme(t: Tema) {
  const dark = t === "escuro" || (t === "sistema" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
}

export function useTheme(): [Tema, (t: Tema) => void] {
  const [tema, setTemaState] = useState<Tema>(() => {
    const v = readStore(KEY);
    return v === "claro" || v === "escuro" ? v : "sistema";
  });

  useEffect(() => {
    applyTheme(tema);
    if (tema !== "sistema") return;
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const on = () => applyTheme("sistema");
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [tema]);

  const setTema = useCallback((t: Tema) => {
    writeStore(KEY, t);
    setTemaState(t);
  }, []);
  return [tema, setTema];
}
