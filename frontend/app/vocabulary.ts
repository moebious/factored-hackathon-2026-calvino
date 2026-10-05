// Vocabulary Registry (Policy-Agnostic domain mapping).
// Maps raw audit log identifiers to accessible i18n labels and visual tones.
// Rule: NEVER crash on unknown keys from future policy versions (V3). If an ID
// is unknown, it falls back to raw rendering.

export const percent = (value: number): string => `${(value * 100).toFixed(1)}%`;

export type KnownRoute = "agents" | "clarify" | "human" | "out_of_scope";
export type Route = KnownRoute | (string & {});

export type KnownStage = "hard_rules" | "classifier" | "gate" | "verifier" | "human";
export type Stage = KnownStage | (string & {});

export type KnownVerdict = "allow" | "ask" | "block" | "pass" | "fail" | "agents" | "clarify" | "human" | "out_of_scope" | "operator_queue";
export type Verdict = KnownVerdict | (string & {});

export type Tone = "info" | "ok" | "warn" | "danger" | "neutral";

export type TermMetadata = {
  label: string;
  tone: Tone;
  description?: string;
};

type Lang = "es" | "pt";

const RULES_DICT: Record<Lang, Record<string, TermMetadata>> = {
  es: {
    // Hard Rules
    "HR-FRAUD": { label: "Alerta de Fraude", tone: "danger", description: "Cliente o cuenta con marcas de seguridad previas" },
    "HR-AUTH": { label: "Fallo de Autenticación", tone: "danger", description: "Múltiples intentos fallidos de validación" },
    "HR-AMOUNT": { label: "Monto Superior a Límite", tone: "warn", description: "El importe supera el umbral de autonomía del agente" },
    "HR-ASKS-HUMAN": { label: "Petición de Humano", tone: "info", description: "El cliente solicitó expresamente hablar con una persona" },
    "HR-REGULATOR": { label: "Mención Regulatoria", tone: "warn", description: "Señal de intervención o reclamo formal" },
    "HR-VULNERABLE": { label: "Atención Prioritaria", tone: "info", description: "Protocolo especial de protección al cliente" },

    // Route Rules
    "RT-ACT": { label: "Resolución Autónoma", tone: "ok", description: "El agente puede consultar y explicar la evidencia" },
    "RT-CLARIFY-CONFIDENCE": { label: "Aclaración por Certeza", tone: "warn", description: "Baja certeza; se requiere confirmar la intención" },
    "RT-CLARIFY-UNCLEAR": { label: "Aclaración de Mensaje", tone: "warn", description: "Mensaje ambiguo; se requiere precisar el pago" },
    "RT-CLARIFY-BAND": { label: "Banda de Consulta", tone: "info", description: "Consulta intermedia que requiere elección guiada" },
    "RT-ESCALATE": { label: "Derivación a Especialista", tone: "warn", description: "El caso requiere criterio de un operador bancario" },
    "RT-DISPUTE-FRAUD": { label: "Gestión de Disputa", tone: "danger", description: "Sospecha de transacción no autorizada" },
    "RT-OUT-OF-SCOPE": { label: "Fuera de Alcance", tone: "neutral", description: "Consulta ajena a los servicios del banco" },
    "RT-INJECTION": { label: "Bloqueo Preventivo", tone: "danger", description: "Patrón de entrada no admitido por seguridad" },

    // Gate Rules
    "GATE-ALLOW": { label: "Operación Autorizada", tone: "ok", description: "Acción dentro de los límites y con token único" },
    "GATE-LIMIT": { label: "Aprobación Requerida", tone: "warn", description: "El importe requiere confirmación explícita del cliente" },
    "GATE-UNCLEAR": { label: "Confirmación Necesaria", tone: "warn", description: "Se solicita confirmación antes de ejecutar la acción" },
    "GATE-LOW-CONFIDENCE": { label: "Validación Preventiva", tone: "warn", description: "Confianza baja; se valida con el cliente" },
    "GATE-NOT-OWNER": { label: "Titularidad No Coincide", tone: "danger", description: "La transacción no pertenece a la cuenta activa" },
    "GATE-INELIGIBLE": { label: "Estado No Apto", tone: "warn", description: "La transacción no admite la acción solicitada" },
    "GATE-INJECTION": { label: "Acción Denegada", tone: "danger", description: "Violación de directiva de seguridad" },

    // Tool Refusals
    "TOOL-NOT-OWNER": { label: "Acceso Denegado", tone: "danger", description: "Datos restringidos a otro titular" },
    "TOOL-NOT-ALLOWED": { label: "Herramienta Restringida", tone: "danger", description: "Operación no habilitada para esta etapa" },
  },
  pt: {
    // Hard Rules
    "HR-FRAUD": { label: "Alerta de Fraude", tone: "danger", description: "Cliente ou conta com sinalizações prévias de segurança" },
    "HR-AUTH": { label: "Falha de Autenticação", tone: "danger", description: "Múltiplas tentativas falhas de validação" },
    "HR-AMOUNT": { label: "Valor Acima do Limite", tone: "warn", description: "O valor excede o limite de autonomia do agente" },
    "HR-ASKS-HUMAN": { label: "Solicitação de Humano", tone: "info", description: "O cliente solicitou expressamente falar com uma pessoa" },
    "HR-REGULATOR": { label: "Menção Regulatória", tone: "warn", description: "Sinal de intervenção ou reclamação formal" },
    "HR-VULNERABLE": { label: "Atendimento Prioritário", tone: "info", description: "Protocolo especial de proteção ao cliente" },

    // Route Rules
    "RT-ACT": { label: "Resolução Autônoma", tone: "ok", description: "O agente pode consultar e explicar a evidência" },
    "RT-CLARIFY-CONFIDENCE": { label: "Esclarecimento por Certeza", tone: "warn", description: "Baixa certeza; confirmação da intenção necessária" },
    "RT-CLARIFY-UNCLEAR": { label: "Mensagem Ambígua", tone: "warn", description: "Mensagem ambígua; é necessário especificar o pagamento" },
    "RT-CLARIFY-BAND": { label: "Faixa de Consulta", tone: "info", description: "Consulta intermediária que requer escolha guiada" },
    "RT-ESCALATE": { label: "Encaminhado a Especialista", tone: "warn", description: "O caso requer avaliação de um operador bancário" },
    "RT-DISPUTE-FRAUD": { label: "Gestão de Disputa", tone: "danger", description: "Suspeita de transação não autorizada" },
    "RT-OUT-OF-SCOPE": { label: "Fora de Escopo", tone: "neutral", description: "Consulta fora dos serviços do banco" },
    "RT-INJECTION": { label: "Bloqueio Preventivo", tone: "danger", description: "Padrão de entrada não admitido por segurança" },

    // Gate Rules
    "GATE-ALLOW": { label: "Operação Autorizada", tone: "ok", description: "Ação dentro dos limites e com token único" },
    "GATE-LIMIT": { label: "Aprovação Necessária", tone: "warn", description: "O valor requer confirmação explícita do cliente" },
    "GATE-UNCLEAR": { label: "Confirmação Necessária", tone: "warn", description: "Confirmação solicitada antes de executar a ação" },
    "GATE-LOW-CONFIDENCE": { label: "Validação Preventiva", tone: "warn", description: "Confiança baixa; validação com o cliente" },
    "GATE-NOT-OWNER": { label: "Titularidade Incompatível", tone: "danger", description: "A transação não pertence à conta ativa" },
    "GATE-INELIGIBLE": { label: "Status Não Elegível", tone: "warn", description: "A transação não admite a ação solicitada" },
    "GATE-INJECTION": { label: "Ação Negada", tone: "danger", description: "Violação da diretriz de segurança" },

    // Tool Refusals
    "TOOL-NOT-OWNER": { label: "Acesso Negado", tone: "danger", description: "Dados restritos a outro titular" },
    "TOOL-NOT-ALLOWED": { label: "Ferramenta Restrita", tone: "danger", description: "Operação não habilitada para esta etapa" },
  },
};

const STAGES_DICT: Record<Lang, Record<string, string>> = {
  es: {
    hard_rules: "Reglas de Seguridad",
    classifier: "Clasificación de Intención",
    gate: "Control de Operación",
    verifier: "Auditoría de Consistencia",
    human: "Atención Humana",
  },
  pt: {
    hard_rules: "Regras de Segurança",
    classifier: "Classificação de Intenção",
    gate: "Controle de Operação",
    verifier: "Auditoria de Consistência",
    human: "Atendimento Humano",
  },
};

const VERDICTS_DICT: Record<Lang, Record<string, { label: string; tone: Tone }>> = {
  es: {
    allow: { label: "Permitido", tone: "ok" },
    ask: { label: "Requiere Confirmación", tone: "warn" },
    block: { label: "Detenido", tone: "danger" },
    pass: { label: "Verificado", tone: "ok" },
    fail: { label: "No Verificado", tone: "warn" },
    agents: { label: "Ruta Asistente", tone: "ok" },
    clarify: { label: "Ruta Aclaración", tone: "info" },
    human: { label: "Ruta Humana", tone: "warn" },
    out_of_scope: { label: "Fuera de Dominio", tone: "neutral" },
    operator_queue: { label: "En Cola de Operador", tone: "warn" },
  },
  pt: {
    allow: { label: "Permitido", tone: "ok" },
    ask: { label: "Requer Confirmação", tone: "warn" },
    block: { label: "Bloqueado", tone: "danger" },
    pass: { label: "Verificado", tone: "ok" },
    fail: { label: "Não Verificado", tone: "warn" },
    agents: { label: "Rota Assistente", tone: "ok" },
    clarify: { label: "Rota Esclarecimento", tone: "info" },
    human: { label: "Rota Humana", tone: "warn" },
    out_of_scope: { label: "Fora de Escopo", tone: "neutral" },
    operator_queue: { label: "Fila do Operador", tone: "warn" },
  },
};

export function resolveRule(ruleId: string | null, lang: Lang = "es"): TermMetadata {
  const isPt = lang === "pt";
  if (!ruleId) return { label: isPt ? "Regra do sistema" : "Regla del sistema", tone: "neutral" };
  const entry = RULES_DICT[lang]?.[ruleId];
  if (entry) return entry;

  // Fallback pattern matching for future policy versions (V3)
  if (ruleId.startsWith("HR-")) {
    return {
      label: isPt ? `Regra de Segurança (${ruleId})` : `Regla de Seguridad (${ruleId})`,
      tone: "danger",
    };
  }
  if (ruleId.startsWith("RT-")) {
    return {
      label: isPt ? `Critério de Rota (${ruleId})` : `Criterio de Ruta (${ruleId})`,
      tone: "info",
    };
  }
  if (ruleId.startsWith("GATE-")) {
    return {
      label: isPt ? `Controle de Operação (${ruleId})` : `Control de Operación (${ruleId})`,
      tone: "warn",
    };
  }
  if (ruleId.startsWith("FC-")) {
    return {
      label: isPt ? `Proteção Preventiva (${ruleId})` : `Protección Preventiva (${ruleId})`,
      tone: "danger",
    };
  }

  return { label: ruleId, tone: "neutral" };
}

export function resolveStage(stage: string, lang: Lang = "es"): string {
  return STAGES_DICT[lang]?.[stage] ?? stage;
}

export function resolveVerdict(verdict: string, lang: Lang = "es"): { label: string; tone: Tone } {
  return VERDICTS_DICT[lang]?.[verdict] ?? { label: verdict, tone: "neutral" };
}
