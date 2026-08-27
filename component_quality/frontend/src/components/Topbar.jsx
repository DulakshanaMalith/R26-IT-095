import { LogOut } from "lucide-react";
import { NavLink } from "react-router-dom";

const navItems = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/students", label: "My Students" },
];

export default function Topbar({ currentSupervisor, onLogout, onRetry }) {
  return (
    <header className="topbar">
      <div>
        <h1>ResearchPilot</h1>
        <p>Automated Quality Assessment &amp; Adaptive Mentorship</p>
      </div>
      <div className="topbar-actions">
        {currentSupervisor && (
          <div className="supervisor-chip">
            <span>Supervisor</span>
            <strong>{currentSupervisor.name}</strong>
            {onLogout && (
              <button type="button" onClick={onLogout} aria-label="Logout">
                <LogOut size={15} />
              </button>
            )}
          </div>
        )}
        <nav className="pill-nav" aria-label="Page shortcuts">
          {navItems.map((item) => (
            <NavLink className={({ isActive }) => (isActive ? "active" : "")} key={item.to} to={item.to} end={item.to === "/dashboard"}>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  );
}
