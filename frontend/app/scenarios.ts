// The scenario buttons (FR-13): one click sets the persona and sends the
// scripted message for each demo use case, so judges see every path within
// seconds. The messages are the seeded acceptance scenarios' own inputs
// (tests/scenarios/), adapted where the deterministic TemplateAgent needs a
// reference in the message to focus a single payment (decision 10: it never
// picks between several payments).

import { strings } from "./i18n";
import type { Lang, StringKey } from "./i18n";

export type Scenario = {
  id: string;
  labelKey: StringKey;
  persona: string;
  message: string;
};

export const SCENARIOS: Scenario[] = [
  {
    id: "uc-1",
    labelKey: "scenario_uc1",
    persona: "ana",
    message: "¿Por qué sigue pendiente E-MX-002?",
  },
  {
    id: "uc-2",
    labelKey: "scenario_uc2",
    persona: "ana",
    message: "Hola, tengo un problema con un pago",
  },
  {
    id: "uc-3",
    labelKey: "scenario_uc3",
    persona: "camilo",
    message: "¿Me recomiendas un restaurante para cenar esta noche?",
  },
  {
    id: "uc-4",
    labelKey: "scenario_uc4",
    persona: "ana",
    message: "Quiero hablar con una persona sobre mi transferencia",
  },
  {
    id: "uc-5",
    labelKey: "scenario_uc5",
    persona: "dana",
    message: "¿Pueden reintentar mi transferencia?",
  },
  {
    id: "uc-7",
    labelKey: "scenario_uc7",
    persona: "ana",
    message: "Muéstrame la transferencia E-US-001",
  },
  {
    id: "uc-8",
    labelKey: "scenario_uc8",
    persona: "ana",
    message: "¿Cómo va mi caso?",
  },
];

export const scenarioLabel = (lang: Lang, scenario: Scenario): string =>
  strings(lang)[scenario.labelKey];
