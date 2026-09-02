"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale } from "@/lib/i18n";

export default function LoginPage() {
  const router = useRouter();
  const { t, locale, toggleLocale } = useLocale();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const resp = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        setError(body.error || t("login.signInFailed"));
        return;
      }
      router.push("/today");
      router.refresh();
    } catch {
      setError(t("login.genericError"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", position: "relative" }}>
      <button
        type="button"
        className="btn btn-ghost btn-sm"
        style={{ position: "absolute", top: 20, insetInlineEnd: 20 }}
        onClick={toggleLocale}
      >
        {locale === "en" ? "🌐 العربية" : "🌐 English"}
      </button>
      <form onSubmit={handleSubmit} className="card card-pad" style={{ width: "min(380px, 92vw)" }}>
        <div className="brand" style={{ padding: "0 0 18px" }}>
          <div className="brand-mark">YA</div>
          <div className="brand-text"><b>{t("shell.brandName")}</b><span>{t("shell.brandSub")}</span></div>
        </div>

        <label className="field" htmlFor="email">{t("login.email")}</label>
        <div className="field-wrap">
          <input
            id="email" type="email" className="input" required autoFocus
            value={email} onChange={(e) => setEmail(e.target.value)}
          />
        </div>

        <label className="field" htmlFor="password">{t("login.password")}</label>
        <div className="field-wrap">
          <input
            id="password" type="password" className="input" required
            value={password} onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        {error && <p style={{ color: "var(--danger)", fontSize: 13, marginBottom: 12 }}>{error}</p>}

        <button type="submit" className="btn btn-primary btn-block" disabled={busy}>
          {busy ? t("common.signingIn") : t("common.signIn")}
        </button>
      </form>
    </div>
  );
}
