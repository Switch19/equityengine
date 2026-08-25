import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import NotificationBell from "./NotificationBell";

/**
 * Shared shell for all three role dashboards (candidate, recruiter,
 * admin). Desktop (md breakpoint, 768px, and up): fixed sidebar,
 * always visible, exactly as before. Mobile (below md): sidebar
 * becomes a slide-in drawer triggered by a hamburger button in a
 * fixed top bar, with a backdrop that closes it on tap — the
 * standard responsive-sidebar pattern, no new dependency needed.
 */
export default function DashboardLayout({ navItems, roleLabel }) {
  const { user, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen">
      {/* Mobile-only top bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 h-14 bg-white border-b border-ink-100 flex items-center justify-between px-4 z-40">
        <button
          onClick={() => setMobileOpen(true)}
          aria-label="Open menu"
          className="p-2 -ml-2"
        >
          <HamburgerIcon />
        </button>
        <span className="font-display font-semibold">EquityEngine</span>
        <NotificationBell />
      </div>

      {/* Backdrop, mobile only, shown while the drawer is open */}
      {mobileOpen && (
        <div
          className="md:hidden fixed inset-0 bg-ink/40 z-40"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      <div className="flex">
        <aside
          className={`fixed md:static top-0 left-0 h-full w-64 md:w-60 shrink-0 bg-white border-r
            border-ink-100 flex flex-col z-50 transform transition-transform duration-200 ease-out
            ${mobileOpen ? "translate-x-0" : "-translate-x-full"} md:translate-x-0`}
        >
          <div className="px-5 py-5 border-b border-ink-100 flex items-center justify-between">
            <div>
              <h1 className="font-display font-semibold text-lg">EquityEngine</h1>
              <p className="text-xs text-slate mt-0.5">{roleLabel}</p>
            </div>
            <div className="hidden md:block">
              <NotificationBell />
            </div>
            <button
              onClick={() => setMobileOpen(false)}
              className="md:hidden p-1 text-slate"
              aria-label="Close menu"
            >
              ✕
            </button>
          </div>

          <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={() => setMobileOpen(false)}
                className={({ isActive }) =>
                  `block px-3 py-2 rounded text-sm font-medium transition-colors ${
                    isActive ? "bg-ink text-paper" : "text-ink-600 hover:bg-ink-50"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="px-5 py-4 border-t border-ink-100">
            <p className="text-sm font-medium truncate">{user.full_name}</p>
            <button onClick={logout} className="text-xs text-slate hover:text-ink mt-1 underline underline-offset-2">
              Log out
            </button>
          </div>
        </aside>

        <main className="flex-1 min-w-0 overflow-y-auto pt-14 md:pt-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function HamburgerIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M3 6H19M3 11H19M3 16H19" stroke="#14163A" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}
