"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Filter,
  Search,
  ShieldAlert,
  ShieldCheck,
  User,
} from "lucide-react";
import type { OperatorQueueItem } from "../../types/case-study";
import type { Strings } from "../../i18n";

type FilterStatus = "all" | "pending_approval" | "in_investigation" | "refused" | "resolved";

interface OperatorQueueTableProps {
  cases: OperatorQueueItem[];
  selectedRef: string | null;
  onSelectCase: (caseRef: string) => void;
  strings: Strings;
}

export function OperatorQueueTable({
  cases,
  selectedRef,
  onSelectCase,
  strings: s,
}: OperatorQueueTableProps) {
  const [filter, setFilter] = useState<FilterStatus>("all");
  const [search, setSearch] = useState("");

  const filteredCases = useMemo(() => {
    return cases.filter((item) => {
      const matchesFilter = filter === "all" || item.status === filter;
      const q = search.toLowerCase().trim();
      const matchesSearch =
        !q ||
        item.case_ref.toLowerCase().includes(q) ||
        item.persona.toLowerCase().includes(q) ||
        item.reason_rule_id.toLowerCase().includes(q) ||
        item.customer_message.toLowerCase().includes(q);
      return matchesFilter && matchesSearch;
    });
  }, [cases, filter, search]);

  const counts = useMemo(() => {
    return {
      all: cases.length,
      pending_approval: cases.filter((c) => c.status === "pending_approval").length,
      in_investigation: cases.filter((c) => c.status === "in_investigation").length,
      refused: cases.filter((c) => c.status === "refused").length,
      resolved: cases.filter((c) => c.status === "resolved").length,
    };
  }, [cases]);

  return (
    <div className="operator-queue-table-component">
      <div className="table-controls">
        <div className="search-box">
          <Search size={13} className="search-icon" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por caso, titular o regla…"
            aria-label="Buscar expedientes"
          />
        </div>

        <div className="filter-pills" role="tablist" aria-label="Filtro de estado">
          <button
            type="button"
            className={`filter-pill ${filter === "all" ? "active" : ""}`}
            onClick={() => setFilter("all")}
          >
            Todos ({counts.all})
          </button>
          <button
            type="button"
            className={`filter-pill ${filter === "pending_approval" ? "active" : ""}`}
            onClick={() => setFilter("pending_approval")}
          >
            <Clock size={11} /> {s.statusPendingApproval} ({counts.pending_approval})
          </button>
          <button
            type="button"
            className={`filter-pill ${filter === "in_investigation" ? "active" : ""}`}
            onClick={() => setFilter("in_investigation")}
          >
            <AlertTriangle size={11} /> {s.statusInInvestigation} ({counts.in_investigation})
          </button>
          <button
            type="button"
            className={`filter-pill ${filter === "refused" ? "active" : ""}`}
            onClick={() => setFilter("refused")}
          >
            <ShieldAlert size={11} /> {s.statusRefusedRule} ({counts.refused})
          </button>
          <button
            type="button"
            className={`filter-pill ${filter === "resolved" ? "active" : ""}`}
            onClick={() => setFilter("resolved")}
          >
            <CheckCircle2 size={11} /> {s.statusResolvedCase} ({counts.resolved})
          </button>
        </div>
      </div>

      <div className="table-scroll-wrap">
        <table className="queue-data-table">
          <thead>
            <tr>
              <th>{s.tableColRef}</th>
              <th>{s.tableColPersona}</th>
              <th>{s.tableColReason}</th>
              <th>{s.tableColAmount}</th>
              <th>{s.tableColStatus}</th>
              <th>{s.tableColDate}</th>
            </tr>
          </thead>
          <tbody>
            {filteredCases.length === 0 ? (
              <tr>
                <td colSpan={6} className="empty-table-cell">
                  {s.noCasesFound}
                </td>
              </tr>
            ) : (
              filteredCases.map((item) => {
                const isSelected = item.case_ref === selectedRef;
                return (
                  <tr
                    key={item.case_ref}
                    className={`queue-row ${isSelected ? "selected-row" : ""} status-${item.status}`}
                    onClick={() => onSelectCase(item.case_ref)}
                  >
                    <td className="cell-ref">
                      <strong>{item.case_ref}</strong>
                      {item.target_action && (
                        <span className="sub-action">{item.target_action}</span>
                      )}
                    </td>
                    <td className="cell-persona">
                      <span className="persona-chip">
                        <User size={11} /> @{item.persona}
                      </span>
                    </td>
                    <td className="cell-rule">
                      <code className="rule-code">{item.reason_rule_id}</code>
                    </td>
                    <td className="cell-amount">
                      {item.amount ? (
                        <span className="amount-val">
                          {item.amount} <small>{item.currency}</small>
                        </span>
                      ) : (
                        <span className="dash">—</span>
                      )}
                    </td>
                    <td className="cell-status">
                      <span className={`status-badge badge-${item.status}`}>
                        {item.status === "pending_approval"
                          ? s.statusPendingApproval
                          : item.status === "in_investigation"
                          ? s.statusInInvestigation
                          : item.status === "refused"
                          ? s.statusRefusedRule
                          : s.statusResolvedCase}
                      </span>
                    </td>
                    <td className="cell-date">
                      <time dateTime={item.created_at}>
                        {new Date(item.created_at).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </time>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
