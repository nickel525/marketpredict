import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";

const links = [
  { to: "/", label: "Rankings" },
  { to: "/backtest", label: "Backtest" },
];

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-800 bg-ink-900">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <div className="text-sm font-medium tracking-[0.18em] text-slate-400">MARKETPREDICT</div>
            <div className="text-slate-200">5-day / 5% probability ranking</div>
          </div>
          <nav className="flex gap-6 text-sm">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.to === "/"}
                className={({ isActive }) =>
                  isActive ? "text-white" : "text-slate-400 hover:text-slate-200"
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
      <footer className="mx-auto max-w-6xl px-6 pb-8 text-xs text-slate-500">
        Research prototype. Not investment advice. Predictions are statistical estimates, not guarantees.
      </footer>
    </div>
  );
}
