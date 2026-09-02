"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { DraftOut, OpportunityOut } from "@/lib/types";
import { useLocale } from "@/lib/i18n";
import { DraftsIcon, OpportunitiesIcon, PerformanceIcon, SettingsIcon, TodayIcon } from "./Icons";

const NAV_ITEMS = [
  { key: "today", labelKey: "shell.navToday", href: "/today", icon: TodayIcon },
  { key: "opportunities", labelKey: "shell.navOpportunities", href: "/opportunities", icon: OpportunitiesIcon },
  { key: "drafts", labelKey: "shell.navDrafts", href: "/drafts", icon: DraftsIcon },
  { key: "performance", labelKey: "shell.navPerformance", href: "/performance", icon: PerformanceIcon },
  { key: "settings", labelKey: "shell.navSettings", href: "/settings", icon: SettingsIcon },
] as const;

const TITLES: Record<string, [string, string]> = {
  "/today": ["shell.todayTitle", "shell.todaySub"],
  "/opportunities": ["shell.opportunitiesTitle", "shell.opportunitiesSub"],
  "/drafts": ["shell.draftsTitle", "shell.draftsSub"],
  "/performance": ["shell.performanceTitle", "shell.performanceSub"],
  "/settings": ["shell.settingsTitle", "shell.settingsSub"],
};

export function Shell({ children, hideTopbar, wide, full }:
  { children: React.ReactNode; hideTopbar?: boolean; wide?: boolean; full?: boolean }) {
  const pathname = usePathname();
  const { t, locale, toggleLocale } = useLocale();
  const [oppCount, setOppCount] = useState<number | null>(null);
  const [draftCount, setDraftCount] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.opportunities().then((rows) => {
      if (!cancelled) setOppCount((rows as OpportunityOut[]).filter((o) => o.status === "new").length);
    }).catch(() => {});
    api.drafts().then((rows) => {
      if (!cancelled) setDraftCount((rows as DraftOut[]).filter((d) => d.status === "pending_review").length);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [pathname]);

  const badges: Record<string, number | null> = { opportunities: oppCount, drafts: draftCount };
  const [titleKey, subKey] = TITLES[pathname] || ["", ""];

  return (
    <div className="app-shell">
      <div className="sidebar">
        <div className="brand">
          <div className="brand-mark">YA</div>
          <div className="brand-text"><b>{t("shell.brandName")}</b><span>{t("shell.brandSub")}</span></div>
        </div>
        <nav className="nav">
          {NAV_ITEMS.map(({ key, labelKey, href, icon: Icon }) => {
            const active = pathname.startsWith(href);
            const badge = badges[key];
            return (
              <Link key={key} href={href} className={`nav-item ${active ? "active" : ""}`}>
                <Icon />
                <span>{t(labelKey)}</span>
                {!!badge && <span className="nav-badge">{badge}</span>}
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-footer">
          <button className="btn btn-ghost btn-sm btn-block" style={{ justifyContent: "flex-start" }} onClick={toggleLocale}>
            {locale === "en" ? "🌐 العربية" : "🌐 English"}
          </button>
          <div className="demo-badge"><span className="demo-dot" />{t("shell.liveConnected")}</div>
          <button
            className="btn btn-ghost btn-sm btn-block"
            style={{ marginTop: 8, justifyContent: "flex-start" }}
            onClick={async () => {
              await fetch("/api/logout", { method: "POST" });
              window.location.href = "/login";
            }}
          >
            {t("common.signOut")}
          </button>
        </div>
      </div>
      <div className="main">
        {!hideTopbar && (
          <div className="topbar">
            <div><h1>{t(titleKey)}</h1><div className="topbar-sub">{t(subKey)}</div></div>
            <div className="topbar-avatar">YA</div>
          </div>
        )}
        <div className={`content ${wide ? "wide" : ""} ${full ? "full" : ""}`}>{children}</div>
      </div>
    </div>
  );
}
