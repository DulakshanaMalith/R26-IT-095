import { House, LogOut } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

const ANALYTICS_TABS = [
  { id: "risk", label: "Risk Prediction" },
  { id: "contributions", label: "Contribution Index" },
  { id: "dashboard", label: "Dashboard" }
];

export default function Topbar({ user, onLogout }) {
  const location = useLocation();
  const projectId = location.pathname.match(/^\/projects\/(\d+)(?:\/|$)/)?.[1];
  const requestedSection = projectId
    ? location.hash.slice(1)
    : new URLSearchParams(location.search).get("section");
  const activeSection = projectId ? requestedSection || "dashboard" : requestedSection || "projects";

  return (
    <header className="topbar">
      <div className="topbar-heading">
        <span className="eyebrow">Intelligent Project Management System</span>
        <h1>{projectId ? "Project Analytics" : requestedSection ? "Select a Project" : user.role === "supervisor" ? "My Projects" : "My Project"}</h1>
      </div>
      <div className="topbar-controls">
        <nav className="topbar-nav" aria-label="Risk component navigation">
          <Link to="/projects" className={activeSection === "projects" ? "active" : ""}
            aria-current={activeSection === "projects" ? "page" : undefined}>
            {user.role === "supervisor" ? "My Projects" : "My Project"}
          </Link>
          {ANALYTICS_TABS.map(({ id, label }) => (
            <Link key={id} to={projectId ? `/projects/${projectId}#${id}` : `/projects?section=${id}`}
              className={activeSection === id ? "active" : ""}
              aria-current={activeSection === id ? "page" : undefined}>
              {label}
            </Link>
          ))}
        </nav>
        <div className="topbar-user">
          <strong>{user.full_name}</strong>
          <span className={`role-pill ${user.role}`}>{user.role}</span>
          <a className="topbar-home" href="http://127.0.0.1:8000/home"><House size={14} /> IPMS Home</a>
          <button type="button" className="topbar-logout" onClick={onLogout}><LogOut size={14} /> Sign out</button>
        </div>
      </div>
    </header>
  );
}
