import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { api, ApiError, type DemoUser } from "../api/client";
import { useAuth } from "../auth/AuthContext";

const DEMO_PASSWORD = "demo1234";

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [demoUsers, setDemoUsers] = useState<DemoUser[]>([]);

  useEffect(() => {
    api.demoUsers().then(setDemoUsers).catch(() => setDemoUsers([]));
  }, []);

  if (user) return <Navigate to={from} replace />;

  async function signIn(emailToUse: string, passwordToUse: string) {
    setError("");
    setSubmitting(true);
    try {
      await login(emailToUse, passwordToUse);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not sign in. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void signIn(email, password);
  }

  return (
    <main className="login-page">
      <div className="card login-card">
        <div className="login-brand">
          <img src="/favicon.svg" alt="" width={30} height={40} />
          <h1>Ajaia Docs</h1>
        </div>
        <p className="muted">Sign in to continue</p>

        <form onSubmit={handleSubmit} noValidate>
          <label className="field">
            <span>Email</span>
            <input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button className="btn btn-primary btn-block" type="submit" disabled={submitting || !email || !password}>
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        {demoUsers.length > 0 && (
          <section className="demo-accounts">
            <h2>Demo accounts</h2>
            {demoUsers.map((demo) => (
              <button
                key={demo.email}
                className="btn btn-block demo-button"
                disabled={submitting}
                onClick={() => void signIn(demo.email, DEMO_PASSWORD)}
              >
                Sign in as {demo.name.split(" ")[0]}
                <span className="muted">{demo.email}</span>
              </button>
            ))}
            <p className="muted small">
              All demo accounts use the password <code>{DEMO_PASSWORD}</code>.
            </p>
          </section>
        )}
      </div>
    </main>
  );
}
