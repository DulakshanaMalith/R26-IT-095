import { useState } from "react";
import { BarChart3, LoaderCircle, LogIn, TriangleAlert } from "lucide-react";
import { Link, Navigate, useNavigate } from "react-router-dom";

export default function Login({ authenticated, backendOnline, backendChecked, tempDevLoginBypass = false, onDevLogin, onLogin }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  if (authenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  async function submitLogin(event) {
    event.preventDefault();
    if (tempDevLoginBypass) {
      setLoading(true);
      setError("");
      try {
        await onDevLogin();
        navigate("/dashboard", { replace: true });
      } catch (loginError) {
        setError(loginError.message || "Development login failed.");
      } finally {
        setLoading(false);
      }
      return;
    }
    setLoading(true);
    setError("");
    try {
      await onLogin({ email, password });
    } catch (loginError) {
      setError(loginError.message || "Invalid email or password.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-panel">
        <div className="login-brand">
          <div className="brand-icon">
            <BarChart3 size={22} />
          </div>
          <div>
            <strong>ResearchPilot</strong>
            <span>Supervisor Workflow</span>
          </div>
        </div>
        <div>
          <span className="eyebrow">Supervisor Login</span>
          <h1>Sign in to continue</h1>
          <p>Use your supervisor account to access assigned students and proposal reviews.</p>
        </div>
        {!backendOnline && backendChecked && (
          <div className="error-card">
            <TriangleAlert size={18} />
            <span>Backend is unavailable. Start FastAPI before signing in.</span>
          </div>
        )}
        {error && (
          <div className="error-card">
            <TriangleAlert size={18} />
            <span>{error}</span>
          </div>
        )}
        <form className="login-form" onSubmit={submitLogin} noValidate={tempDevLoginBypass}>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required={!tempDevLoginBypass}
              autoComplete="email"
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required={!tempDevLoginBypass}
              autoComplete="current-password"
            />
          </label>
          <button className="primary-button" type="submit" disabled={loading || (!tempDevLoginBypass && !backendOnline)}>
            {loading ? <LoaderCircle className="spin" size={17} /> : <LogIn size={17} />}
            {loading ? "Signing In..." : "Sign In"}
          </button>
        </form>
        <p className="auth-switch">
          New supervisor? <Link to="/signup">Create an account</Link>
        </p>
      </section>
    </main>
  );
}
