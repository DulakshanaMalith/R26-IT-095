import { useState } from "react";
import { LoaderCircle, LogIn, ShieldAlert, TriangleAlert } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

export default function Login({ onLogin }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submitLogin(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await onLogin(email, password);
      navigate("/projects", { replace: true });
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
            <ShieldAlert size={22} />
          </div>
          <div>
            <strong>IPMS Risk</strong>
            <span>Predictive Risk Monitoring &amp; Contribution Analytics</span>
          </div>
        </div>
        <div>
          <span className="eyebrow">Sign In</span>
          <h1>Sign in to continue</h1>
          <p>Supervisors see the projects they supervise. Students see their own team's analytics.</p>
        </div>
        {error && (
          <div className="error-card">
            <TriangleAlert size={18} />
            <span>{error}</span>
          </div>
        )}
        <form className="login-form" onSubmit={submitLogin}>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              autoComplete="email"
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              autoComplete="current-password"
            />
          </label>
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? <LoaderCircle className="spin" size={17} /> : <LogIn size={17} />}
            {loading ? "Signing In..." : "Sign In"}
          </button>
        </form>
        <p className="auth-switch">
          New here? <Link to="/signup">Create an account</Link>
        </p>
      </section>
    </main>
  );
}
