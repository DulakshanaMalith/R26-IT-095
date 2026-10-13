import { useState } from "react";
import { BarChart3, LoaderCircle, UserPlus, TriangleAlert } from "lucide-react";
import { Link, Navigate, useNavigate } from "react-router-dom";

export default function Signup({ authenticated, backendOnline, backendChecked, onRegister }) {
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  if (authenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  async function submitRegistration(event) {
    event.preventDefault();
    setError("");
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      await onRegister({
        full_name: fullName,
        email,
        password,
        confirm_password: confirmPassword,
      });
      navigate("/dashboard", { replace: true });
    } catch (registrationError) {
      const message = registrationError.message === "Email already registered."
        ? "An account with this email already exists."
        : registrationError.message || "Registration failed.";
      setError(message);
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
          <span className="eyebrow">Supervisor Sign Up</span>
          <h1>Create account</h1>
          <p>Create a supervisor account to manage assigned students and proposal reviews.</p>
        </div>
        {!backendOnline && backendChecked && (
          <div className="error-card">
            <TriangleAlert size={18} />
            <span>Backend is unavailable. Start FastAPI before creating an account.</span>
          </div>
        )}
        {error && (
          <div className="error-card">
            <TriangleAlert size={18} />
            <span>{error}</span>
          </div>
        )}
        <form className="login-form" onSubmit={submitRegistration}>
          <label>
            Full Name
            <input
              type="text"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              required
              autoComplete="name"
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
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              autoComplete="new-password"
            />
          </label>
          <label>
            Confirm Password
            <input
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              required
              autoComplete="new-password"
            />
          </label>
          <button className="primary-button" type="submit" disabled={loading || !backendOnline}>
            {loading ? <LoaderCircle className="spin" size={17} /> : <UserPlus size={17} />}
            {loading ? "Creating Account..." : "Create Account"}
          </button>
        </form>
        <p className="auth-switch">
          Already have an account? <Link to="/login">Sign In</Link>
        </p>
      </section>
    </main>
  );
}
