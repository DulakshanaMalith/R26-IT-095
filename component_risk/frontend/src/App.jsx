import { useCallback, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";
import Loader from "./components/Loader";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Projects from "./pages/Projects";
import ProjectAnalytics from "./pages/ProjectAnalytics";
import { getMe, login, logout, registerAccount } from "./api";

export default function App() {
  const [user, setUser] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    getMe()
      .then((data) => setUser(data.user))
      .catch(() => setUser(null))
      .finally(() => setAuthChecked(true));
  }, []);

  const handleLogin = useCallback(async (email, password) => {
    const data = await login(email, password);
    setUser(data.user);
  }, []);

  const handleSignup = useCallback(async (payload) => {
    const data = await registerAccount(payload);
    setUser(data.user);
  }, []);

  const handleLogout = useCallback(async () => {
    try {
      await logout();
    } finally {
      setUser(null);
    }
  }, []);

  if (!authChecked) {
    return (
      <main className="login-page">
        <Loader label="Checking session..." />
      </main>
    );
  }

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login onLogin={handleLogin} />} />
        <Route path="/signup" element={<Signup onSignup={handleSignup} />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <div className="app-shell">
      <Sidebar user={user} onLogout={handleLogout} />
      <div className="app-content">
        <Topbar user={user} />
        <Routes>
          <Route path="/projects" element={<Projects user={user} />} />
          <Route path="/projects/:projectId" element={<ProjectAnalytics user={user} />} />
          <Route path="*" element={<Navigate to="/projects" replace />} />
        </Routes>
      </div>
    </div>
  );
}
