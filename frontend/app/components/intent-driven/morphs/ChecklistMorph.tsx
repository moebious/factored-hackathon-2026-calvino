import { CheckSquare } from "lucide-react";
import type { Lang } from "../../../i18n";
import { strings } from "../../../i18n";

export function ChecklistMorph({
  items,
  lang = "es",
}: {
  items: string[];
  lang?: Lang;
}) {
  const s = strings(lang);

  return (
    <div className="morph-widget morph-checklist" aria-label={s.checklistAriaLabel}>
      <div className="morph-items">
        {items.slice(0, 4).map((item, idx) => (
          <label key={`${item}-${idx}`} className="morph-checkbox-item">
            <CheckSquare size={13} className="text-mint" />
            <span>{item}</span>
          </label>
        ))}
      </div>
      {items.length > 4 && <span className="morph-more">+{items.length - 4} {s.checklistMore}</span>}
    </div>
  );
}
