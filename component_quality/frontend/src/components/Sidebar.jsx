import { Activity, BarChart3, Clock3, LayoutDashboard, LogOut, UsersRound } from "lucide-react";
import { NavLink } from "react-router-dom";

const links = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/students", label: "My Students", icon: UsersRound },
];

export default function Sidebar({ currentSupervisor, onLogout }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-icon">
          <BarChart3 size={22} />
        </div>
        <div>
          <strong>ResearchPilot</strong>
          <span>Proposal Quality Intelligence</span>
        </div>
      </div>
      <span className="version-badge">v1.0 AI Prototype</span>

      <nav className="side-nav" aria-label="Main navigation">
        <p>Navigation</p>
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink className={({ isActive }) => `side-link ${isActive ? "active" : ""}`} key={to} to={to} end={to === "/dashboard"}>
            <Icon size={18} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      {currentSupervisor && (
        <div className="project-card">
          <span>Supervisor</span>
          <strong>{currentSupervisor.name}</strong>
          {onLogout && (
            <button className="sidebar-logout" type="button" onClick={onLogout}>
              <LogOut size={15} />
              Logout
            </button>
          )}
        </div>
      )}
    </aside>
  );
}
