import { useLocation } from "react-router-dom";

export default function Topbar({ user }) {
  const location = useLocation();
  const isDetail = /^\/projects\/\d+/.test(location.pathname);

  return (
    <header className="topbar">
      <div>
        <span className="eyebrow">Intelligent Project Management System</span>
        <h1>{isDetail ? "Project Analytics" : user.role === "supervisor" ? "My Projects" : "My Project"}</h1>
      </div>
      <div className="topbar-user">
        <strong>{user.full_name}</strong>
        <span className={`role-pill ${user.role}`}>{user.role}</span>
      </div>
    </header>
  );
}
