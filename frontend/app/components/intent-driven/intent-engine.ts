import type { DetectedIntent } from "../../types/case-study";
import type { Lang } from "../../i18n";

export function detectIntent(text: string, lang: Lang = "es"): DetectedIntent {
  const isPt = lang === "pt";
  const trimmed = text.trim();
  if (!trimmed) {
    return {
      type: "conversation",
      label: isPt ? "Conversa" : "Conversación",
      hint: isPt
        ? "Escreva, fale ou anexe. Encontrarei a melhor rota."
        : "Escribe, habla o adjunta. Yo encuentro la forma.",
      confidence: 1.0,
      params: {},
    };
  }

  // 1. Transaction reference tracking (E-MX-002, E-US-001, etc.)
  const txMatch = trimmed.match(/\b(E-[A-Z]{2}-\d{3,4})\b/i);
  if (txMatch) {
    const reference = txMatch[1].toUpperCase();
    if (/cancelar|anular/i.test(trimmed)) {
      return {
        type: "action_cancel",
        label: isPt ? "Cancelar transferência" : "Cancelar transferencia",
        hint: isPt
          ? `Solicitação de cancelamento para ${reference}`
          : `Solicitud de cancelación para ${reference}`,
        confidence: 0.95,
        params: { reference },
      };
    }
    if (/reintentar|reintentá|retry|tentar novamente/i.test(trimmed)) {
      return {
        type: "action_retry",
        label: isPt ? "Tentar novamente transferência" : "Reintentar transferencia",
        hint: isPt
          ? `Solicitação de nova tentativa para ${reference}`
          : `Solicitud de reintento para ${reference}`,
        confidence: 0.95,
        params: { reference },
      };
    }
    return {
      type: "status_track",
      label: isPt ? "Rastreamento de pagamento" : "Rastreo de pago",
      hint: isPt
        ? `Inspecionando status de ${reference}`
        : `Inspeccionando estado de ${reference}`,
      confidence: 0.95,
      params: { reference },
    };
  }

  // 2. Dispute or fraud signal
  if (/(?:fraude|desconozco|desconheço|não reconheço|no reconozco|reclamo|reclamação|robo|roubo|disputa)\b/i.test(trimmed)) {
    return {
      type: "dispute",
      label: isPt ? "Disputa / Alerta" : "Disputa / Alerta",
      hint: isPt
        ? "Caso de segurança bancária prioritário"
        : "Caso de seguridad bancaria prioritario",
      confidence: 0.9,
      params: { flagged: true },
    };
  }

  // 3. Split bill / amount
  const splitMatch = trimmed.match(/(?:split|divide|dividir|entre)\s*(\d+(?:[.,]\d+)?)\s*(?:entre|\/|personas?|pessoas?)\s*(\d+)/i);
  if (splitMatch) {
    const total = parseFloat(splitMatch[1].replace(",", "."));
    const people = parseInt(splitMatch[2], 10) || 2;
    const perPerson = people > 0 ? (total / people).toFixed(2) : total.toFixed(2);
    return {
      type: "split",
      label: isPt ? "Dividir valor" : "Dividir importe",
      hint: isPt
        ? `${total} entre ${people} = ${perPerson} cada`
        : `${total} entre ${people} = ${perPerson} c/u`,
      confidence: 0.95,
      params: { total, people, perPerson: parseFloat(perPerson) },
    };
  }
  if (/(?:split|divide|dividir|entre)\b/i.test(trimmed)) {
    return {
      type: "split",
      label: isPt ? "Dividir valor" : "Dividir importe",
      hint: isPt
        ? "Calcula o valor entre várias pessoas"
        : "Calcula la cuota entre varias personas",
      confidence: 0.85,
      params: { total: 0, people: 2, perPerson: 0 },
    };
  }

  // 4. Checklist / Tasks / Requirements
  if (/(?:checklist|recaudos|requisitos|pasos|passos|tarefas|lista|todo|comprar)\b/i.test(trimmed)) {
    const rawItems = trimmed.replace(/^(?:checklist|recaudos|requisitos|pasos|passos|tarefas|lista|todo|comprar)[:\s]*/i, "");
    const items = rawItems
      .split(/[,;\n]+/)
      .map((item) => item.trim())
      .filter(Boolean);
    return {
      type: "checklist",
      label: isPt ? "Lista de passos" : "Lista de pasos",
      hint: items.length
        ? (isPt ? `${items.length} itens detectados` : `${items.length} elementos detectados`)
        : (isPt ? "Transforme ideias em passos práticos" : "Convierte ideas en pasos accionables"),
      confidence: 0.85,
      params: { items: items.length ? items : [isPt ? "Revisar comprovante" : "Revisar comprobante", isPt ? "Validar titular" : "Validar titular"] },
    };
  }

  // 5. Timer / Wait duration
  const timerMatch = trimmed.match(/(\d+)\s*(?:min|minutos?|m\b)/i);
  if (timerMatch || /(?:timer|temporizador|minutos?|segundos?|esperar?)\b/i.test(trimmed)) {
    const minutes = timerMatch ? parseInt(timerMatch[1], 10) : 15;
    return {
      type: "timer",
      label: isPt ? "Temporizador" : "Temporizador",
      hint: isPt
        ? `Janela de tempo: ${minutes} minutos`
        : `Ventana de tiempo: ${minutes} minutos`,
      confidence: 0.85,
      params: { minutes },
    };
  }

  // 6. Event / Deadline schedule
  if (/(?:mañana|amanhã|cita|reunión|reunião|evento|vencimiento|vencimento|plazo|prazo|fecha|data)\b/i.test(trimmed)) {
    return {
      type: "event",
      label: isPt ? "Agendar data" : "Agendar fecha",
      hint: isPt
        ? "Agendar acompanhamento ou prazo limite"
        : "Programar seguimiento o plazo límite",
      confidence: 0.8,
      params: { scheduled: true },
    };
  }

  // 7. Color / Visual code
  const colorMatch = trimmed.match(/(?:#([0-9a-f]{3,8})|(?:color|cor)\s+([a-z]+))/i);
  if (colorMatch) {
    const hex = colorMatch[1] ? `#${colorMatch[1]}` : "#75e1c4";
    return {
      type: "color",
      label: isPt ? "Paleta de cores" : "Paleta de color",
      hint: isPt ? `Cor hexadecimal: ${hex}` : `Color hexadecimal: ${hex}`,
      confidence: 0.9,
      params: { hex },
    };
  }

  // Default: General Banking Conversation
  return {
    type: "conversation",
    label: isPt ? "Conversa" : "Conversación",
    hint: isPt
      ? "Consulta verificada contra os dados do banco"
      : "Consulta verificada contra los datos del banco",
    confidence: 1.0,
    params: {},
  };
}
