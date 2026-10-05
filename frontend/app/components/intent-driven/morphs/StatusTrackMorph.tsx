import { ShieldCheck, Search } from "lucide-react";
import type { Lang } from "../../../i18n";
import { strings } from "../../../i18n";

export function StatusTrackMorph({
  reference,
  lang = "es",
}: {
  reference: string;
  lang?: Lang;
}) {
  const s = strings(lang);

  return (
    <div className="morph-widget morph-status-track" aria-label={s.statusTrackAriaLabel}>
      <div className="morph-badge status-badge">
        <Search size={14} />
        <span>{s.statusTrackActive}</span>
      </div>
      <div className="morph-ref">
        <code>{reference}</code>
      </div>
      <div className="morph-hint">
        <ShieldCheck size={14} />
        <span>{s.statusTrackHint}</span>
      </div>
    </div>
  );
}
