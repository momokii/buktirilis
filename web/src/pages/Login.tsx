import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth";
import { errorMessage } from "../api";
import { Button, Field, Notice, TextInput } from "../ui";

export function LoginPage() {
  const { login, bootstrap, needsBootstrap, webBootstrapAllowed, error, demoEnabled } = useAuth();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setFormError(null);
    try {
      if (needsBootstrap) {
        await bootstrap(email, name, password);
      } else {
        await login(email, password);
      }
    } catch (caught) {
      setFormError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-page">
      <main className="auth-card" aria-labelledby="auth-title">
        <div className="auth-brand">
          <img className="brand-logo auth-logo" src="/logo-mark.svg" alt="" width={38} height={38} />
          <div>
            <h1 id="auth-title" style={{ fontSize: "1.2rem" }}>
              BuktiRilis
            </h1>
            <p className="auth-tagline">See what was tested. Verify what changed.</p>
          </div>
        </div>
        {needsBootstrap && webBootstrapAllowed ? (
          <Notice tone="info" title="First launch">
            No administrator exists yet. Create the installation administrator to begin.
          </Notice>
        ) : null}
        {needsBootstrap && !webBootstrapAllowed ? (
          <Notice tone="warn" title="Administrator setup required">
            No administrator exists. Web bootstrap is disabled in this environment; run
            <code className="mono"> python -m app.cli bootstrap-admin --email &lt;email&gt; </code>
            on the server, then sign in here.
          </Notice>
        ) : null}
        {demoEnabled ? (
          <Notice tone="info" title="Demo installation">
            Demo credentials are written to <code className="mono">var/demo-credentials.txt</code>{" "}
            by <code className="mono">make demo</code>.
          </Notice>
        ) : null}
        {needsBootstrap && !webBootstrapAllowed ? null : (
        <form className="stack" onSubmit={submit}>
          <Field label="Email" htmlFor="login-email">
            <TextInput
              id="login-email"
              name="email"
              type="email"
              autoComplete="username"
              inputMode="email"
              autoCapitalize="none"
              spellCheck={false}
              autoFocus
              placeholder="you@company.com"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </Field>
          {needsBootstrap ? (
            <Field label="Display name" htmlFor="login-name">
              <TextInput
                id="login-name"
                name="name"
                autoComplete="name"
                required
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </Field>
          ) : null}
          <Field
            label="Password"
            htmlFor="login-password"
            hint={needsBootstrap ? "At least 12 characters." : undefined}
          >
            <TextInput
              id="login-password"
              name="password"
              type="password"
              autoComplete={needsBootstrap ? "new-password" : "current-password"}
              placeholder="Enter your password"
              required
              minLength={needsBootstrap ? 12 : undefined}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </Field>
          {formError ?? error ? (
            <p className="field-error" role="alert">
              {formError ?? error}
            </p>
          ) : null}
          <Button type="submit" variant="primary" busy={busy}>
            {needsBootstrap ? "Create administrator" : "Sign in"}
          </Button>
        </form>
        )}
        <p className="auth-footer">
          Authorized internal use only. Sessions are cookie-based; every action is checked
          server-side. <Link to="/guide">Read the user guide</Link>.
        </p>
      </main>
    </div>
  );
}
