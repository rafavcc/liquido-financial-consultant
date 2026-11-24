import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useTheme, type Tema } from "../lib/theme";
import { IconBox, IconCompare, IconGear, IconImport, IconMonitor, IconMoon, IconSun, IconTrend } from "./Icons";

const NAV = [
  { to: "/", label: "Comparador", icon: <IconCompare />, end: true },
  { to: "/produtos", label: "Produtos", icon: <IconBox />, end: false },
  { to: "/importar", label: "Importar", icon: <IconImport />, end: false },
  { to: "/configuracoes", label: "Configurações", icon: <IconGear />, end: false },
  { to: "/mercado", label: "Mercado", icon: <IconTrend />, end: false },
];

const TEMAS: { id: Tema; label: string; icon: ReactNode }[] = [
  { id: "claro", label: "Tema claro", icon: <IconSun /> },
  { id: "sistema", label: "Tema do sistema", icon: <IconMonitor /> },
  { id: "escuro", label: "Tema escuro", icon: <IconMoon /> },
];

function ThemeToggle() {
  const [tema, setTema] = useTheme();
  return (
    <div role="radiogroup" aria-label="Tema" className="flex rounded-full border border-line bg-subtle p-0.5">
      {TEMAS.map((t) => (
        <button
          key={t.id}
          type="button"
          role="radio"
          aria-checked={tema === t.id}
          aria-label={t.label}
          title={t.label}
          onClick={() => setTema(t.id)}
          className={`flex h-7 w-7 items-center justify-center rounded-full transition ${
            tema === t.id ? "bg-surface text-accent shadow-card" : "text-muted hover:text-ink"
          } [&_svg]:h-4 [&_svg]:w-4`}
        >
          {t.icon}
        </button>
      ))}
    </div>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen pb-24 sm:pb-10">
      <header className="sticky top-0 z-20 border-b border-line bg-surface/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-6 px-4">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-sm font-bold text-accent-fg">L</span>
            <span className="text-lg font-semibold tracking-tight">Liquido</span>
          </div>
          <nav className="hidden flex-1 gap-1 sm:flex" aria-label="Principal">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                    isActive ? "bg-subtle text-accent" : "text-muted hover:text-ink"
                  }`
                }
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto sm:ml-0">
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-5">{children}</main>

      <nav
        aria-label="Principal"
        className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur sm:hidden"
      >
        <ul className="grid grid-cols-5">
          {NAV.map((n) => (
            <li key={n.to}>
              <NavLink
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  `flex flex-col items-center gap-0.5 py-2 text-[11px] font-medium ${isActive ? "text-accent" : "text-muted"}`
                }
              >
                {n.icon}
                {n.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
