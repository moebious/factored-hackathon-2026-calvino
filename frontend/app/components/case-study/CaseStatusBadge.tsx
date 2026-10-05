"use client";

import type { CaseStudyStatus } from "../../types/case-study";
import { AlertCircle, CheckCircle2, Clock, HelpCircle, Loader2, ShieldAlert } from "lucide-react";
import type { Lang } from "../../i18n";
import { strings } from "../../i18n";

export function CaseStatusBadge({
  status,
  lang = "es",
}: {
  status: CaseStudyStatus;
  lang?: Lang;
}) {
  const s = strings(lang);

  const getBadgeConfig = () => {
    switch (status) {
      case "draft":
        return { label: s.statusDraft, icon: Clock, className: "badge-neutral" };
      case "analyzing":
        return { label: s.statusAnalyzing, icon: Loader2, className: "badge-analyzing" };
      case "needs_information":
        return { label: s.statusNeedsInfo, icon: HelpCircle, className: "badge-warn" };
      case "awaiting_action":
        return { label: s.statusAwaitingAction, icon: AlertCircle, className: "badge-warn" };
      case "in_operator_queue":
        return { label: s.statusInOperatorQueue, icon: Clock, className: "badge-warn" };
      case "resolved":
        return { label: s.statusResolved, icon: CheckCircle2, className: "badge-ok" };
      case "refused":
        return { label: s.statusRefused, icon: ShieldAlert, className: "badge-danger" };
    }
  };

  const { label, icon: Icon, className } = getBadgeConfig();

  return (
    <span className={`case-status-badge ${className}`}>
      <Icon size={12} className={status === "analyzing" ? "animate-spin" : ""} />
      <span>{label}</span>
    </span>
  );
}
