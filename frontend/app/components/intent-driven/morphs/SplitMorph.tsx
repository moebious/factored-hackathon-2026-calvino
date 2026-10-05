import { Users, DollarSign } from "lucide-react";
import type { Lang } from "../../../i18n";
import { strings } from "../../../i18n";

export function SplitMorph({
  total,
  people,
  perPerson,
  lang = "es",
}: {
  total: number;
  people: number;
  perPerson: number;
  lang?: Lang;
}) {
  const s = strings(lang);

  return (
    <div className="morph-widget morph-split" aria-label={s.splitAriaLabel}>
      <div className="morph-badge">
        <Users size={14} />
        <span>{people} {s.splitPeople}</span>
      </div>
      <div className="morph-metric">
        <DollarSign size={14} />
        <span>{s.splitTotal}: <strong>{total > 0 ? total.toFixed(2) : "—"}</strong></span>
        <span className="morph-divider">→</span>
        <span className="morph-result"><strong>{perPerson > 0 ? perPerson.toFixed(2) : "—"}</strong> {s.splitEach}</span>
      </div>
    </div>
  );
}
