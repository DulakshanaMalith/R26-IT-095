import { Activity, FolderKanban, LogOut, ShieldAlert } from "lucide-react";
import { NavLink } from "react-router-dom";

export default function Sidebar({ user, onLogout }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-icon">
          <ShieldAlert size={22} />
        </div>
        <div>
          <strong>IPMS Risk</strong>
          <span>Predictive Risk Monitoring</span>
        </div>
      </div>

      <span className="version-badge">
        <Activity size={12} /> Contribution Analytics
      </span>

      <nav className="sidebar-nav">
        <NavLink to="/projects" className={({ isActive }) => (isActive ? "active" : "")}>
          <FolderKanban size={17} />
          {user.role === "supervisor" ? "My Projects" : "My Project"}
        </NavLink>
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-user">
          <strong>{user.full_name}</strong>
          <span className={`role-pill ${user.role}`}>{user.role}</span>
        </div>
        <button type="button" className="ghost-button" onClick={onLogout}>
          <LogOut size={15} /> Sign out
        </button>
      </div>
    </aside>
  );
}
