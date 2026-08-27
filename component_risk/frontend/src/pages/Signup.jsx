import { useState } from "react";
import { LoaderCircle, ShieldAlert, TriangleAlert, UserPlus } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

export default function Signup({ onSignup }) {
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("student");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submitSignup(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await onSignup({ full_name: fullName, email, password, role });
      navigate("/projects", { replace: true });
    } catch (signupError) {
      setError(signupError.message || "Registration failed.");
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
          <span className="eyebrow">Create Account</span>
          <h1>Join the platform</h1>
          <p>Students are added to teams by their supervisor after registering.</p>
        </div>
        {error && (
          <div className="error-card">
            <TriangleAlert size={18} />
            <span>{error}</span>
          </div>
        )}
        <form className="login-form" onSubmit={submitSignup}>
          <label>
            Full Name
            <input
              type="text"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              required
            />
          </label>
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
            Password (min 8 characters)
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={8}
              required
              autoComplete="new-password"
            />
          </label>
          <label>
            Role
            <select value={role} onChange={(event) => setRole(event.target.value)}>
              <option value="student">Student</option>
              <option value="supervisor">Supervisor</option>
            </select>
          </label>
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? <LoaderCircle className="spin" size={17} /> : <UserPlus size={17} />}
            {loading ? "Creating..." : "Create Account"}
          </button>
        </form>
        <p className="auth-switch">
          Already registered? <Link to="/login">Sign in</Link>
        </p>
      </section>
    </main>
  );
}
