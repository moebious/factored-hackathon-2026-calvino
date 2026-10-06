"""The code check registry (TSD-004): deterministic criteria, decided without any model.

Each check compares the reply against the ``Evidence`` built from this session's
tool results and returns one ``CriterionVerdict``. Text extraction is deliberately
literal (amounts, dates, quoted merchant names, a fixed status and action-claim
vocabulary): a false fail costs one retry, a false pass reaches the customer, so
the checks err toward failing (DESIGN.md 4.4). What literal extraction cannot see
(mixed language, paraphrased claims) is backed up by the Laya and judge criteria.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date
from decimal import Decimal, InvalidOperation

from calvino.tools.contracts import TransactionStatus
from calvino.verifier.evidence import Evidence
from calvino.verifier.rubric import CheckerKind, Rubric
from calvino.verifier.verdicts import CriterionVerdict

# Currency codes the dataset uses (DATA.md) plus the generic symbol; an amount
# claim is a numeric token with a decimal part or one adjacent to a currency.
_CURRENCY_TOKENS = ("MXN", "COP", "ARS", "USD", "$")

# Numeric token: thousands separators, or a plain digit run with an optional
# decimal part. The separated form requires at least one 3-digit group, so a
# plain contract amount ("5000.00", the way the TSD-002 contracts serialize
# amounts) matches as one token instead of splitting into "500" plus a stray
# "0.00" claim that matches no evidence and fails every correct reply citing it.
_NUMBER_RE = re.compile(r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?")
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_SLASH_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_QUOTED_RE = re.compile(r"«([^»]+)»|\"([^\"]+)\"")

# The status vocabulary: the dataset's four transaction statuses and the words
# a Spanish or Portuguese reply states them with. The check cannot parse
# negation ("no está pendiente" mentions pendiente); a false fail there costs a
# retry, which is cheaper than a false pass (DESIGN 4.4).
_STATUS_WORDS: dict[TransactionStatus, tuple[str, ...]] = {
    TransactionStatus.PENDING: ("pending", "pendiente", "pendente"),
    TransactionStatus.DECLINED: ("declined", "rechazado", "rechazada", "recusado", "recusada"),
    TransactionStatus.REVERSED: ("reversed", "revertido", "revertida", "devuelto", "devolvida"),
    TransactionStatus.APPROVED: (
        "approved",
        "aprobado",
        "aprobada",
        "aprovado",
        "aprovada",
        "completed",
        "completado",
        "completada",
        "concluído",
    ),
}

# The action-claim vocabulary, keyed by the action id the read-back confirms.
_ACTION_CLAIM_WORDS: dict[str, tuple[str, ...]] = {
    "cancel_transfer": (
        "he cancelado",
        "hemos cancelado",
        "cancelé",
        "se canceló",
        "cancelado",
        "cancelada",
        "cancelled",
        "canceled",
    ),
    "retry_payment": (
        "he reintentado",
        "hemos reintentado",
        "reintenté",
        "se reintentó",
        "reintentado",
        "reintentada",
        "retried",
        "resent",
    ),
}

# What counts as a promise that money will move: a refund, a credit, a guarantee. The Gate decides
# what the bank may do, and nothing in a reply may promise more (rubric criterion
# no-money-movement-promise). The detector reads the *forward-looking* forms (future tense,
# "will be", "vamos a", "recibirá su reembolso") and explicit guarantees, not the bare words: the
# playbook itself tells the model to explain a Reversed payment as money already returned, and
# "el monto fue reembolsado a su cuenta" is a fact the verifier must let through. The cost of that
# precision is recall: a paraphrased promise ("cuente con ese dinero mañana") is invisible here and
# stays the judge's job (no-invented-policy). A negated mention ("no habrá reembolso") is honest
# and passes. Spanish, Portuguese and English, since the model can drift between them.
_MONEY_VERBS = (
    r"(?:reembols|devolv|devuel|acredit|abon|estorn|credit|reintegr|ressarc|refund|reimburs)"
)
_PROMISE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern)
    for pattern in (
        # future tense of the money verbs (Spanish and Portuguese): reembolsaremos, devolverá, ...
        r"\b(?:reembols|devolv|acredit|abon|estorn|credit|reintegr|ressarc)"
        r"(?:aremos|eremos|iremos|aré|eré|aría|ará|erá|arán|erán|arei|erei|arão|erão)\b",
        # passive future: será devuelto, serán reembolsados, será estornado
        rf"\b(?:será|serán|serão)\s+(?:\w+\s+){{0,2}}{_MONEY_VERBS}\w*",
        # periphrastic future: vamos a reembolsar, voy a devolver, vou estornar
        rf"\b(?:vamos|voy|va|vou|vão)\s+(?:a\s+)?{_MONEY_VERBS}\w*",
        # English future: will refund, will be credited, we'll return the money, going to reimburse
        r"\b(?:will|'ll|going to)\s+(?:be\s+)?(?:refund|credit|return|reimburs|pay\s+back)\w*",
        # "you will receive a refund" in any of the three languages
        r"\b(?:recibir[áa]|recibir[ée]|receber[áa]|obtendr[áa]|(?:va|vas|vai|vou|voy) (?:a )?"
        r"(?:recibir|receber)|you will (?:get|receive))\b"
        r".{0,40}?(?:reembols|refund|devoluci|devolu|estorno|cr[ée]dito|abono|reimburs)",
        # explicit guarantees
        r"\b(?:garantizamos|le garantizo|te garanto|garantimos|we guarantee|i guarantee)\b",
    )
)

# Distinctive function and domain words per language, for the literal language
# check. Shared words (está, por favor) are deliberately absent: only words one
# language has and the other does not count. Mixed or unclear text passes here;
# the grounding criteria behind Laya and the judge back the criterion up.
_LANGUAGE_WORDS: dict[str, tuple[str, ...]] = {
    "es": (
        "su",
        "sus",
        "usted",
        "hemos",
        "he",
        "gracias",
        "pago",
        "cuenta",
        "transferencia",
        "reembolso",
        "del",
        "los",
        "las",
        "es",
        "está",
    ),
    "pt": (
        "seu",
        "sua",
        "você",
        "obrigado",
        "obrigada",
        "pagamento",
        "conta",
        "transferência",
        "reembolso",
        "do",
        "da",
        "os",
        "as",
        "é",
        "não",
    ),
}

CodeCheck = Callable[[str, Evidence], CriterionVerdict]


def _verdict(criterion_id: str, passed: bool, reason: str) -> CriterionVerdict:
    return CriterionVerdict(
        criterion_id=criterion_id,
        passed=passed,
        checker=CheckerKind.CODE,
        reason=reason,
    )


def _normalize_amount(token: str) -> list[Decimal]:
    """The decimal readings of a numeric token: '.' or ',' as decimal separator.

    Spanish writes 1.234,56 and English 1,234.56; both readings are tried and
    the check accepts the token when either matches the evidence.
    """
    readings = []
    for decimal_sep in (".", ","):
        thousands_sep = "," if decimal_sep == "." else "."
        candidate = token.replace(thousands_sep, "").replace(decimal_sep, ".")
        try:
            readings.append(Decimal(candidate))
        except InvalidOperation:
            continue
    return readings


def _amount_claims(text: str) -> list[str]:
    """Numeric tokens that claim an amount: decimal part or adjacent currency."""
    without_dates = _ISO_DATE_RE.sub(" ", _SLASH_DATE_RE.sub(" ", text))
    claims = []
    for match in _NUMBER_RE.finditer(without_dates):
        token = match.group()
        has_decimal = re.search(r"[.,]\d+$", token) is not None
        window = without_dates[max(0, match.start() - 6) : match.end() + 6].upper()
        has_currency = any(currency in window for currency in _CURRENCY_TOKENS)
        if has_decimal or has_currency:
            claims.append(token)
    return claims


def _date_claims(text: str) -> list[tuple[str, list[date]]]:
    """Date-like tokens with their possible readings (dd/mm vs mm/dd)."""
    claims: list[tuple[str, list[date]]] = []
    for year, month, day in _ISO_DATE_RE.findall(text):
        try:
            claims.append((f"{year}-{month}-{day}", [date(int(year), int(month), int(day))]))
        except ValueError:
            claims.append((f"{year}-{month}-{day}", []))
    for first, second, year in _SLASH_DATE_RE.findall(text):
        readings = []
        for a, b in ((first, second), (second, first)):
            try:
                readings.append(date(int(year), int(b), int(a)))
            except ValueError:
                continue
        claims.append((f"{first}/{second}/{year}", readings))
    return claims


def check_amounts_dates_merchants(text: str, evidence: Evidence) -> CriterionVerdict:
    """Every amount, date and merchant stated matches a tool result."""
    criterion_id = "amounts-dates-merchants-match"
    unmatched = []
    for token in _amount_claims(text):
        if not any(amount in evidence.amounts for amount in _normalize_amount(token)):
            unmatched.append(token)
    for token, readings in _date_claims(text):
        if not readings or not any(reading in evidence.dates for reading in readings):
            unmatched.append(token)
    for quoted in _QUOTED_RE.findall(text):
        name = (quoted[0] or quoted[1]).strip()
        # Quoted spans that are amounts or dates were already checked above.
        if not name or _NUMBER_RE.fullmatch(name.replace(".", "").replace(",", "")):
            continue
        if (
            any(name.casefold() in words for words in _STATUS_WORDS.values())
            or name.upper() in _CURRENCY_TOKENS
            or _ISO_DATE_RE.fullmatch(name) is not None
        ):
            continue
        if not any(name.casefold() in merchant.casefold() for merchant in evidence.merchants):
            unmatched.append(name)
    if unmatched:
        return _verdict(criterion_id, False, f"not in any tool result: {', '.join(unmatched)}")
    return _verdict(criterion_id, True, "every stated amount, date and merchant matches")


def check_stated_status(text: str, evidence: Evidence) -> CriterionVerdict:
    """The stated payment status matches the bank's record from a tool result."""
    criterion_id = "stated-status-matches-record"
    lowered = text.casefold()
    stated = {
        status
        for status, words in _STATUS_WORDS.items()
        for word in words
        if re.search(rf"\b{re.escape(word)}\b", lowered)
    }
    wrong = stated - evidence.statuses
    if wrong:
        return _verdict(
            criterion_id,
            False,
            f"reply states {sorted(s.value for s in wrong)} but the record shows "
            f"{sorted(s.value for s in evidence.statuses) or 'no status'}",
        )
    return _verdict(criterion_id, True, "every stated status matches the bank's record")


def claimed_actions(text: str) -> frozenset[str]:
    """The action ids a reply claims as done, by the literal claim vocabulary."""
    lowered = text.casefold()
    return frozenset(
        action
        for action, phrases in _ACTION_CLAIM_WORDS.items()
        for phrase in phrases
        if phrase in lowered
    )


def promised_money_movement(text: str) -> list[str]:
    """The promise phrases a reply contains, sorted; empty when it promises nothing."""
    lowered = text.casefold()
    found = set()
    for pattern in _PROMISE_PATTERNS:
        for match in pattern.finditer(lowered):
            found.add(match.group(0).strip())
    return sorted(found)


def check_claimed_actions_read_back(text: str, evidence: Evidence) -> CriterionVerdict:
    """Every action claimed as done was verified by reading it back."""
    criterion_id = "claimed-actions-read-back"
    claimed = claimed_actions(text)
    unconfirmed = claimed - evidence.read_backs
    if unconfirmed:
        return _verdict(
            criterion_id, False, f"claimed without a read-back: {', '.join(sorted(unconfirmed))}"
        )
    return _verdict(criterion_id, True, "every claimed action was confirmed by a read-back")


def check_no_money_movement_promise(text: str, evidence: Evidence) -> CriterionVerdict:
    """The reply promises no refund, credit or money movement (literal phrase list)."""
    criterion_id = "no-money-movement-promise"
    found = promised_money_movement(text)
    if found:
        return _verdict(criterion_id, False, f"promises money moving: {', '.join(found)}")
    return _verdict(criterion_id, True, "no refund, credit or guarantee is promised")


def check_no_other_customer_data(text: str, evidence: Evidence) -> CriterionVerdict:
    """No data belonging to another customer appears in the reply."""
    criterion_id = "no-other-customer-data"
    leaked = [marker for marker in sorted(evidence.forbidden_markers) if marker in text]
    if leaked:
        # Name the count, not the markers: the verdict is logged, and the log
        # must not become the place where the leaked data is stored.
        return _verdict(
            criterion_id, False, f"{len(leaked)} identifier(s) of another customer appear"
        )
    return _verdict(criterion_id, True, "no other customer's data appears in the reply")


def check_reply_language(text: str, evidence: Evidence) -> CriterionVerdict:
    """The reply is in the customer's language (literal word markers)."""
    criterion_id = "reply-in-customer-language"
    words = re.findall(r"[\wáéíóúüñãõçà]+", text.casefold())
    scores = {
        language: sum(1 for word in words if word in vocabulary)
        for language, vocabulary in _LANGUAGE_WORDS.items()
    }
    other = "pt" if evidence.customer_language == "es" else "es"
    if scores[other] > scores[evidence.customer_language]:
        return _verdict(
            criterion_id,
            False,
            f"reply reads as {other} ({scores[other]} markers) but the customer writes "
            f"{evidence.customer_language} ({scores[evidence.customer_language]} markers)",
        )
    return _verdict(criterion_id, True, f"reply is in {evidence.customer_language}")


# Criterion id -> check. A rubric whose code criterion has no registered check
# fails loudly rather than skipping the criterion (fail closed).
CODE_CHECKS: dict[str, CodeCheck] = {
    "amounts-dates-merchants-match": check_amounts_dates_merchants,
    "stated-status-matches-record": check_stated_status,
    "claimed-actions-read-back": check_claimed_actions_read_back,
    "no-money-movement-promise": check_no_money_movement_promise,
    "no-other-customer-data": check_no_other_customer_data,
    "reply-in-customer-language": check_reply_language,
}


def run_code_checks(rubric: Rubric, text: str, evidence: Evidence) -> list[CriterionVerdict]:
    """Run every code criterion of the rubric, in rubric order."""
    verdicts = []
    for criterion in rubric.criteria_for(CheckerKind.CODE):
        try:
            check = CODE_CHECKS[criterion.id]
        except KeyError:
            raise KeyError(
                f"rubric {rubric.ref} has a code criterion without a check: {criterion.id!r}"
            ) from None
        verdicts.append(check(text, evidence))
    return verdicts
