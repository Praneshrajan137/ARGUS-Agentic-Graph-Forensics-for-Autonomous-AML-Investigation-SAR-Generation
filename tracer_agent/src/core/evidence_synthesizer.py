"""Source-linked monetary observations and explicitly scoped ledger comparisons.

A disagreement is a numerical finding for review, not an inference of wrongdoing.
Entity extraction retains lazy spaCy NER and search-mode financial ID patterns.
"""
import re
import logging
from decimal import Decimal, InvalidOperation, localcontext
from dataclasses import dataclass, field

from tracer_agent.src.config import (
    AMOUNT_PATTERNS,
    AMOUNT_BROKEN_NUMBER_PATTERN,
    IFSC_SEARCH_COMPILED,
    PAN_SEARCH_COMPILED,
    SWIFT_SEARCH_COMPILED,
    IBAN_SEARCH_COMPILED,
    EVIDENCE_DISCREPANCY_THRESHOLD_USD,
    EVIDENCE_DISCREPANCY_THRESHOLD_INR,
    SPACY_MODEL_NAME,
)

logger = logging.getLogger(__name__)


@dataclass
class EvidenceResult:
    """Result with source observations and one comparison detail per document.

    checked_count counts performed numeric comparisons; eligible_count counts
    documents with complete equal scopes, valid aggregation and known currency.
    MATCH applies only to the checked subset, never to skipped documents.
    """
    verdict: str
    reasoning: str
    discrepancies: list[dict] = field(default_factory=list)
    extracted_entities: list[dict] = field(default_factory=list)
    extracted_amounts: list[Decimal] = field(default_factory=list)
    observations: list[dict] = field(default_factory=list)
    comparisons: list[dict] = field(default_factory=list)
    checked_count: int = 0
    eligible_count: int = 0


class EvidenceSynthesizer:
    """
    Cross-references ledger data (ground truth) with unstructured text evidence.

    Two-pass entity extraction pipeline:
      Pass 1: spaCy statistical NER (PERSON, ORG, GPE, MONEY, DATE)
      Pass 2: Regex for structured financial IDs (IFSC, PAN, SWIFT, IBAN, refs)
              v8.0 [P4v8-01]: Uses _SEARCH_COMPILED patterns (word boundaries)
      Pass 3: Merge and deduplicate results

    spaCy model loaded lazily on first use (Rule 12).
    """

    def __init__(self) -> None:
        """Initialize synthesizer. spaCy model loaded on first use."""
        self._nlp = None
        self._nlp_loaded = False

    def _get_nlp(self):
        """
        Lazy-load spaCy model on first use.

        v6.1 [ALN-06]: Uses SPACY_MODEL_NAME from config.py.
        """
        if not self._nlp_loaded:
            self._nlp_loaded = True
            try:
                import spacy
                self._nlp = spacy.load(
                    SPACY_MODEL_NAME,
                    disable=["tagger", "parser", "lemmatizer"],
                )
                logger.info("spaCy %s loaded successfully.", SPACY_MODEL_NAME)
            except (OSError, ImportError) as e:
                self._nlp = None
                logger.warning(
                    "spaCy %s not available (%s). "
                    "Falling back to regex-only NER. "
                    "WARNING: This violates Rule 12 (spaCy + regex required).",
                    SPACY_MODEL_NAME, e,
                )
        return self._nlp

    def extract_entities_from_text(self, text: str) -> list[dict]:
        """
        Extract entities using spaCy NER + regex.

        v8.0 [P4v8-01]: Pass 2 uses _SEARCH_COMPILED patterns (word boundaries)
        instead of _COMPILED patterns (^$ anchors).

        Args:
            text: Unstructured text to extract entities from.

        Returns:
            Deduplicated list of entity dicts with text, label, source fields.
        """
        entities: list[dict] = []
        seen: set[tuple[str, str]] = set()

        # Pass 1: spaCy NER
        nlp = self._get_nlp()
        if nlp is not None:
            doc = nlp(text)
            for ent in doc.ents:
                if ent.label_ in ("PERSON", "ORG", "GPE", "MONEY", "DATE"):
                    key = (ent.text, ent.label_)
                    if key not in seen:
                        seen.add(key)
                        entities.append({
                            "text": ent.text,
                            "label": ent.label_,
                            "start": ent.start_char,
                            "end": ent.end_char,
                            "source": "spacy_ner",
                        })

        # Pass 2: Regex (always runs regardless of spaCy availability)
        for match in re.finditer(
            r'(?:User|Account|Subject|Entity)\s+(\w+)', text, re.IGNORECASE,
        ):
            key = (match.group(0), "REFERENCE")
            if key not in seen:
                seen.add(key)
                entities.append({
                    "text": match.group(0),
                    "id": match.group(1),
                    "label": "REFERENCE",
                    "source": "regex_reference",
                })

        for match in IFSC_SEARCH_COMPILED.finditer(text):
            key = (match.group(), "IFSC")
            if key not in seen:
                seen.add(key)
                entities.append({
                    "text": match.group(),
                    "label": "IFSC",
                    "source": "regex_ifsc",
                })

        for match in PAN_SEARCH_COMPILED.finditer(text):
            key = (match.group(), "PAN")
            if key not in seen:
                seen.add(key)
                entities.append({
                    "text": match.group(),
                    "label": "PAN",
                    "source": "regex_pan",
                })

        for match in SWIFT_SEARCH_COMPILED.finditer(text):
            key = (match.group(), "SWIFT")
            if key not in seen:
                seen.add(key)
                entities.append({
                    "text": match.group(),
                    "label": "SWIFT",
                    "source": "regex_swift",
                })

        for match in IBAN_SEARCH_COMPILED.finditer(text):
            key = (match.group(), "IBAN")
            if key not in seen:
                seen.add(key)
                entities.append({
                    "text": match.group(),
                    "label": "IBAN",
                    "source": "regex_iban",
                })

        return entities

    @staticmethod
    def _observation_currency(groups: dict) -> str | None:
        """Resolve only explicit, mutually compatible currency markers."""
        codes = {
            value.upper() for key in ("currency_before", "currency_after")
            if (value := groups.get(key))
        }
        symbol = (groups.get("symbol") or "").lower().rstrip(".")
        symbol_codes = {
            "$": {"USD", "CAD", "AUD", "NZD", "SGD", "HKD"},
            "₹": {"INR"},
            "€": {"EUR"},
            "£": {"GBP", "EGP", "LBP", "SYP", "FKP", "GIP", "SHP"},
            "rs": {"INR", "PKR", "LKR", "NPR", "MUR", "SCR"},
        }.get(symbol)
        if len(codes) > 1:
            return None
        if codes:
            code = next(iter(codes))
            return code if symbol_codes is None or code in symbol_codes else None
        if symbol_codes and len(symbol_codes) == 1:
            return next(iter(symbol_codes))
        # Dollars, pounds, Rs., lakh and crore do not identify a unique currency.
        return None

    def extract_monetary_observations(
        self,
        text: str,
        *,
        document_id: str | None = None,
        document_index: int = 0,
    ) -> list[dict]:
        """Extract occurrences in source order, without invoking spaCy.

        start/end are half-open character offsets into the original document.
        Longer representations win over overlapping alternatives; equal amounts
        at separate spans remain separate. Conflicting currency markers produce
        an unknown currency, never a shorter, apparently compatible observation.
        """
        candidates: list[dict] = []
        invalid_spans = [
            match.span(1) for match in re.finditer(AMOUNT_BROKEN_NUMBER_PATTERN, text)
        ]
        for pattern in AMOUNT_PATTERNS.values():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                groups = match.groupdict()
                if groups.get("sign_before") and groups.get("sign_after"):
                    invalid_spans.append(match.span())
                    continue
                amount = Decimal(groups["number"].replace(",", ""))
                if (groups.get("sign_before") or groups.get("sign_after")) == "-":
                    amount = amount.copy_negate()
                scale = (groups.get("scale") or "").lower().rstrip("s")
                exponent_shift = {"k": 3, "lakh": 5, "crore": 7}.get(scale, 0)
                # Tuple construction avoids Decimal context rounding for long
                # coefficients, unlike multiplication by the magnitude.
                sign, digits, exponent = amount.as_tuple()
                amount = Decimal((sign, digits, exponent + exponent_shift))
                candidates.append({
                    "document_id": document_id,
                    "document_index": document_index,
                    "start": match.start(),
                    "end": match.end(),
                    "text": match.group(),
                    "amount": amount,
                    "currency": self._observation_currency(groups),
                })

        observations: list[dict] = []
        occupied = list(invalid_spans)
        for candidate in sorted(
            candidates, key=lambda item: (item["start"] - item["end"], item["start"]),
        ):
            start, end = candidate["start"], candidate["end"]
            if any(start < other_end and other_start < end for other_start, other_end in occupied):
                continue
            observations.append(candidate)
            occupied.append((start, end))
        return sorted(observations, key=lambda item: item["start"])

    def extract_amounts_from_text(self, text: str) -> list[Decimal]:
        """Return exact values in occurrence order, preserving repeated amounts."""
        return [item["amount"] for item in self.extract_monetary_observations(text)]

    @staticmethod
    def _comparison_scope(scope: object) -> dict | None:
        """Require explicit, nonempty scope strings; never infer missing fields."""
        fields = ("entity_id", "period_start", "period_end", "currency", "basis", "aggregation")
        if not isinstance(scope, dict):
            return None
        if not all(isinstance(scope.get(key), str) and scope[key].strip() for key in fields):
            return None
        if scope["aggregation"] not in ("total", "components"):
            return None
        return {key: scope[key] for key in fields}

    @staticmethod
    def _ledger_amount(ledger_data: dict) -> Decimal | None:
        raw = ledger_data.get("total_inflow")
        # Avoid implicit binary-float or boolean monetary conversions.
        if isinstance(raw, bool) or not isinstance(raw, (Decimal, str, int)):
            return None
        try:
            amount = Decimal(raw)
            return amount if amount.is_finite() else None
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _exact_sum(amounts: list[Decimal]) -> Decimal:
        """Preserve coefficient precision for both aggregation and subtraction."""
        lowest_exponent = min(amount.as_tuple().exponent for amount in amounts)
        highest_digit = max(amount.adjusted() for amount in amounts)
        with localcontext() as context:
            context.prec = max(context.prec, highest_digit - lowest_exponent + len(str(len(amounts))) + 2)
            return sum(amounts, Decimal("0"))

    def synthesize(
        self,
        ledger_data: dict | None,
        text_evidence: list[dict | str],
        currency: str = "USD",
    ) -> EvidenceResult:
        """Compare each eligible document independently against total_inflow.

        Both ledger and document must carry a nested ``scope`` with nonempty
        string fields entity_id, period_start, period_end, currency, basis and
        aggregation. All six must be equal. ``total`` requires one observation;
        ``components`` sums only that document's occurrences. Every observation
        must have a known currency equal to the scope currency. The legacy
        currency argument is retained for call compatibility, not inference.

        Verdict precedence: missing/invalid ledger -> INSUFFICIENT_DATA; no
        monetary occurrences -> NO_OBSERVATION; none eligible -> NOT_COMPARABLE;
        any checked disagreement -> DISAGREEMENT; otherwise -> MATCH for the
        checked subset. Unknown/ineligible documents remain visible in details.
        USD/INR use configured tolerances; other currencies require exact equality.
        """
        ledger_data = ledger_data or {}
        ledger_amount = self._ledger_amount(ledger_data)
        ledger_scope = self._comparison_scope(ledger_data.get("scope"))
        result = EvidenceResult(verdict="NOT_COMPARABLE", reasoning="")

        for document_index, evidence in enumerate(text_evidence):
            document = evidence if isinstance(evidence, dict) else {"content": evidence}
            text = document.get("content") or ""
            document_id = document.get("id", document.get("document_id"))
            result.extracted_entities.extend(self.extract_entities_from_text(text))
            observations = self.extract_monetary_observations(
                text, document_id=document_id, document_index=document_index,
            )
            first_index = len(result.observations)
            result.observations.extend(observations)
            result.extracted_amounts.extend(item["amount"] for item in observations)
            scope = self._comparison_scope(document.get("scope"))
            detail = {
                "document_id": document_id,
                "document_index": document_index,
                "observation_indices": list(range(first_index, len(result.observations))),
                "scope": document.get("scope"),
                "ledger_scope": ledger_data.get("scope"),
                "status": "NOT_COMPARABLE",
                "reason": "",
            }
            result.comparisons.append(detail)
            if ledger_amount is None:
                detail.update(status="INSUFFICIENT_DATA", reason="Missing or invalid ledger total_inflow.")
            elif not observations:
                detail.update(status="NO_OBSERVATION", reason="No monetary observations in this document.")
            elif scope is None or ledger_scope is None:
                detail["reason"] = "Both sources require complete explicit comparison scopes."
            elif scope != ledger_scope:
                detail["reason"] = "Document and ledger scopes differ."
            elif scope["aggregation"] == "total" and len(observations) != 1:
                detail["reason"] = "Total aggregation requires exactly one monetary observation."
            elif any(item["currency"] != scope["currency"] for item in observations):
                detail["reason"] = "Observation currency is unknown or differs from the scope."
            else:
                result.eligible_count += 1
                observed_amount = self._exact_sum([item["amount"] for item in observations])
                difference = self._exact_sum([observed_amount, ledger_amount.copy_negate()]).copy_abs()
                threshold = {
                    "USD": EVIDENCE_DISCREPANCY_THRESHOLD_USD,
                    "INR": EVIDENCE_DISCREPANCY_THRESHOLD_INR,
                }.get(scope["currency"], Decimal("0"))
                status = "DISAGREEMENT" if difference > threshold else "MATCH"
                detail.update(
                    status=status,
                    reason="Compared within equal explicit scopes using the currency tolerance.",
                    observed_amount=str(observed_amount),
                    ledger_amount=str(ledger_amount),
                    difference=str(difference),
                    threshold=str(threshold),
                )
                result.checked_count += 1
                if status == "DISAGREEMENT":
                    result.discrepancies.append({
                        **detail,
                        "type": "AMOUNT_MISMATCH",
                        "text_claims": str(observed_amount),
                        "ledger_shows": str(ledger_amount),
                        "entity": scope["entity_id"],
                    })

        if ledger_amount is None:
            result.verdict = "INSUFFICIENT_DATA"
            summary = "Missing or invalid ledger total_inflow; observations retained without comparison."
        elif not result.observations:
            result.verdict = "NO_OBSERVATION"
            summary = "No monetary observations were extracted."
        elif not result.checked_count:
            summary = "No document met the scope, currency and aggregation requirements for comparison."
        elif result.discrepancies:
            result.verdict = "DISAGREEMENT"
            summary = f"{len(result.discrepancies)} checked document(s) differ from the scoped ledger amount."
        else:
            result.verdict = "MATCH"
            summary = "Checked documents match the scoped ledger amount within the currency tolerance."
        result.reasoning = (
            f"{summary} Checked {result.checked_count} of {result.eligible_count} eligible documents "
            f"({len(text_evidence)} supplied). Unchecked documents imply no agreement or disagreement."
        )
        return result
