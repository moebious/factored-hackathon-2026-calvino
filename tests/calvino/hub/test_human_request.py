"""Unit tests for the deterministic human request detector (TSD-029, T-208)."""

import pytest

from calvino.hub.human_request import detects_human_request, normalize_text


class TestNormalization:
    def test_strips_accents_and_casefolds(self):
        assert normalize_text("PÁSAME con un ASESOR!") == "pasame con un asesor!"
        assert normalize_text("comunícame") == "comunicame"
        assert normalize_text("atenção") == "atencao"
        assert normalize_text("alguém") == "alguem"


class TestPositiveRequests:
    @pytest.mark.parametrize(
        "message",
        [
            # Frozen suite cases
            "Necesito hablar con un humano urgente, mi transferencia no llega.",  # AC-4
            "Quiero hablar con una persona.",  # ORC-020
            "Necesito que un humano revise mi cuenta.",  # ORC-021
            "Quiero hablar con alguien del banco.",
            # Spanish natural variations
            "pásame con un asesor",
            "pasame a un asesor",
            "por favor pásame con un asesor",
            "quiero hablar con un humano",
            "comunícame con un agente",
            "comunicame con un asesor por favor",
            "quiero que me atienda una persona",
            "que me atienda un operador",
            "necesito una persona real ahora mismo",
            "solicito un representante",
            "atención con un asesor",
            # Portuguese natural variations
            "quero falar com um atendente",
            "preciso falar com uma pessoa",
            "me transfira para um humano",
            "preciso de um atendente humano agora",
            "quero que me atenda uma pessoa",
            "atendimento com um operador",
            # English natural variations
            "let me talk to an agent",
            "speak to a person",
            "talk to a human",
            "connect me to an agent",
            "I want to speak with a representative",
            "real person please",
        ],
    )
    def test_detects_positive_requests(self, message: str):
        assert detects_human_request(message) is True, f"Failed to detect request in: {message!r}"


class TestNegativeLookAlikes:
    @pytest.mark.parametrize(
        "message",
        [
            # Legal / corporate roles
            "El representante legal de mi empresa cambió la firma.",
            "Necesito el poder del representante legal.",
            # Insurance / third-party agents
            "Mi agente humano de seguros me recomendó revisar esto.",
            "El agente de seguros me dijo que consultara el banco.",
            "Hablé con un agente inmobiliario.",
            # Personal / family references
            "Voy a hablar con alguien de mi familia sobre esto.",
            "Tengo que hablar con mi esposa antes de transferir.",
            "Vou falar com minha familia antes.",
            "Quiero hablar con un amigo sobre el pago.",
            # Routine banking queries (must NOT trigger human escalation)
            "¿Por qué sigue pendiente mi pago E-MX-002?",
            "Mi pago E-MX-002 sigue pendiente, ¿qué pasa?",
            "Tengo un problema con una transferencia.",
            "Quiero cancelar una transferencia.",
            "Por favor reintenten mi pago de alquiler que falló ayer.",
            "¿Cómo va el caso que abrí por mi pago?",
            # Out of scope / greetings
            "Hola, buenos días.",
            "¿Cuál es la capital de Francia?",
            "",
            "   ",
        ],
    )
    def test_rejects_negative_look_alikes(self, message: str):
        assert detects_human_request(message) is False, f"False positive detected in: {message!r}"
