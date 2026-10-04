// The ES / PT toggle (FR-13): every chrome string of the customer app in
// both demo languages. Calvino's own replies are not translated here — they
// come from the hub, grounded in the verified data.

export type Lang = "es" | "pt";

export const STRINGS = {
  es: {
    title: "Calvino",
    tagline:
      "Respuestas verificadas contra los datos del banco. Nada en esta pantalla es texto generado libremente.",
    persona: "Persona de demo",
    inputPlaceholder: "Escribe tu mensaje…",
    send: "Enviar",
    sending: "Enviando…",
    scenarios: "Escenarios",
    glassBox: "Caja de cristal",
    glassBoxEmpty: "Selecciona un turno de Calvino para ver su razonamiento.",
    stage: "Etapa",
    rule: "Regla",
    verdict: "Veredicto",
    scores: "Puntuaciones",
    summary: "Resumen",
    route: "Ruta",
    escalated: "Escalado a una persona",
    caseRef: "Caso",
    confirm: "Confirmar",
    deny: "Denegar",
    decided: "Decisión enviada",
    operatorDecision: "Decisión del operador",
    operatorResume: "Cerrar turno",
    warmupChecking: "Comprobando el backend…",
    warmupLoading: "Calentando: cargando el modelo Laya. Un arranque en frío puede tardar un minuto.",
    unreachable: "El backend de la demo no responde.",
    you: "Tú",
    calvino: "Calvino",
    // Card labels (the catalog is fixed; each key has one component).
    cardPaymentStatus: "Estado del pago",
    cardProblemTransactions: "Pagos con problemas",
    cardActionConfirmation: "Confirmar la acción",
    cardActionResult: "Resultado de la acción",
    cardCaseOpened: "Caso abierto",
    cardCaseStatus: "Estado del caso",
    cardHumanPath: "Derivado a una persona",
    cardHumanPathText: "Una persona de nuestro equipo continuará por los canales oficiales.",
    cardRefusal: "Acción detenida",
    cardUnknown: "Tarjeta desconocida",
    amount: "Importe",
    status: "Estado",
    date: "Fecha",
    merchant: "Concepto",
    reference: "Referencia",
    action: "Acción",
    nextStep: "Próximo paso",
    actions: {
      request_cancellation: "Cancelar la transferencia",
      retry_payment: "Reintentar el pago",
    } as Record<string, string>,
    scenario_uc1: "UC-1 · Pago explicado con evidencia",
    scenario_uc2: "UC-2 · Pedido ambiguo, elección",
    scenario_uc3: "UC-3 · Fuera de alcance",
    scenario_uc4: "UC-4 · Hablar con una persona",
    scenario_uc5: "UC-5 · Acción con confirmación",
    scenario_uc7: "UC-7 · Datos de otro cliente",
    scenario_uc8: "UC-8 · Seguimiento del caso (tras UC-4)",
  },
  pt: {
    title: "Calvino",
    tagline:
      "Respostas verificadas contra os dados do banco. Nada nesta tela é texto gerado livremente.",
    persona: "Persona de demonstração",
    inputPlaceholder: "Escreva sua mensagem…",
    send: "Enviar",
    sending: "Enviando…",
    scenarios: "Cenários",
    glassBox: "Caixa de vidro",
    glassBoxEmpty: "Selecione um turno do Calvino para ver o raciocínio.",
    stage: "Etapa",
    rule: "Regra",
    verdict: "Veredito",
    scores: "Pontuações",
    summary: "Resumo",
    route: "Rota",
    escalated: "Escalado para uma pessoa",
    caseRef: "Caso",
    confirm: "Confirmar",
    deny: "Negar",
    decided: "Decisão enviada",
    operatorDecision: "Decisão do operador",
    operatorResume: "Fechar turno",
    warmupChecking: "Verificando o backend…",
    warmupLoading: "Aquecendo: carregando o modelo Laya. Uma inicialização fria pode levar um minuto.",
    unreachable: "O backend da demonstração não responde.",
    you: "Você",
    calvino: "Calvino",
    cardPaymentStatus: "Status do pagamento",
    cardProblemTransactions: "Pagamentos com problemas",
    cardActionConfirmation: "Confirmar a ação",
    cardActionResult: "Resultado da ação",
    cardCaseOpened: "Caso aberto",
    cardCaseStatus: "Status do caso",
    cardHumanPath: "Encaminhado para uma pessoa",
    cardHumanPathText: "Uma pessoa da nossa equipe continuará pelos canais oficiais.",
    cardRefusal: "Ação interrompida",
    cardUnknown: "Cartão desconhecido",
    amount: "Valor",
    status: "Status",
    date: "Data",
    merchant: "Descrição",
    reference: "Referência",
    action: "Ação",
    nextStep: "Próximo passo",
    actions: {
      request_cancellation: "Cancelar a transferência",
      retry_payment: "Tentar o pagamento novamente",
    } as Record<string, string>,
    scenario_uc1: "UC-1 · Pagamento explicado com evidência",
    scenario_uc2: "UC-2 · Pedido ambíguo, escolha",
    scenario_uc3: "UC-3 · Fora de escopo",
    scenario_uc4: "UC-4 · Falar com uma pessoa",
    scenario_uc5: "UC-5 · Ação com confirmação",
    scenario_uc7: "UC-7 · Dados de outro cliente",
    scenario_uc8: "UC-8 · Acompanhamento do caso (após UC-4)",
  },
} as const;

// STRINGS is `as const`, so each language's table has literal types; the
// shared shape widens every entry to string (and keeps the actions table a
// lookup), so both languages are assignable to it.
type Widen<T> = T extends Record<string, string> ? Record<string, string> : string;

export type Strings = {
  [K in keyof (typeof STRINGS)["es"]]: Widen<(typeof STRINGS)["es"][K]>;
};

// The keys whose value is a single string (everything except `actions`):
// what labels and chrome text reference.
export type StringKey = {
  [K in keyof Strings]: Strings[K] extends string ? K : never;
}[keyof Strings];

export const strings = (lang: Lang): Strings => STRINGS[lang];

// The action name of a card payload, localized when the catalog knows it
// and shown verbatim otherwise (a payload field is never invented).
export const actionLabel = (lang: Lang, action: unknown): string => {
  const name = typeof action === "string" ? action : "";
  return STRINGS[lang].actions[name] ?? name;
};
