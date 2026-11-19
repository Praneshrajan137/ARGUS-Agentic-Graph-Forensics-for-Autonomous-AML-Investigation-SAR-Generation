"""
Tests for Evidence Synthesizer -- Purple Agent v8.0
PRD Reference: Task B4
TDD: Tests written FIRST, implementation SECOND.

Tests cover:
  - Amount discrepancy detection (text vs ledger cross-reference)
  - Entity extraction via spaCy NER (PERSON, ORG, MONEY)
  - Regex extraction (IFSC, PAN, SWIFT, IBAN, references)
  - Merge and deduplication of spaCy + regex results
  - Source-span monetary occurrences, precision, currency, and malformed tokens
  - Missing/zero ledger and explicit scope comparison contracts
  - Single-document component aggregation (never cross-document sums)
  - v8.0 [P4v8-01]: SEARCH_COMPILED patterns find embedded codes
  - v8.0 [P4v8-01]: COMPILED (anchored) patterns reject embedded codes
"""
from decimal import Decimal
from unittest.mock import MagicMock

import pytest


from tracer_agent.src.core.evidence_synthesizer import EvidenceSynthesizer
from tracer_agent.src.config import (
    IFSC_COMPILED,
    PAN_COMPILED,
    SWIFT_COMPILED,
    IBAN_COMPILED,
    IFSC_SEARCH_COMPILED,
    PAN_SEARCH_COMPILED,
    SWIFT_SEARCH_COMPILED,
    IBAN_SEARCH_COMPILED,
)


# ===================================================================
# Helper: Mock spaCy NLP for deterministic testing
# ===================================================================

def _make_mock_nlp(entities: list[tuple[str, str, int, int]]):
    """
    Create a mock spaCy Language that returns controlled entities.

    Args:
        entities: List of (text, label, start_char, end_char) tuples.

    Returns:
        Mock nlp callable producing a mock Doc with the given entities.
    """
    def _mock_call(text: str):
        doc = MagicMock()
        mock_ents = []
        for ent_text, label, start, end in entities:
            ent = MagicMock()
            ent.text = ent_text
            ent.label_ = label
            ent.start_char = start
            ent.end_char = end
            mock_ents.append(ent)
        doc.ents = mock_ents
        return doc
    return _mock_call


def _synth_with_mock_nlp(
    entities: list[tuple[str, str, int, int]] | None = None,
) -> EvidenceSynthesizer:
    """Create an EvidenceSynthesizer with optionally mocked spaCy."""
    synth = EvidenceSynthesizer()
    if entities is not None:
        synth._nlp = _make_mock_nlp(entities)
        synth._nlp_loaded = True
    else:
        synth._nlp = None
        synth._nlp_loaded = True
    return synth


def _scope(**overrides) -> dict:
    return {
        "entity_id": "src_01",
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "currency": "USD",
        "basis": "inflow",
        "aggregation": "total",
        **overrides,
    }


def _ledger(amount="10000", **scope_overrides) -> dict:
    return {"total_inflow": Decimal(amount), "scope": _scope(**scope_overrides)}


def _document(content="$10,000 USD", document_id="doc-1", **scope_overrides) -> dict:
    return {"id": document_id, "content": content, "scope": _scope(**scope_overrides)}


class TestAmountDiscrepancy:

    def test_detects_amount_discrepancy(self) -> None:
        result = _synth_with_mock_nlp().synthesize(_ledger("9500"), [_document()])
        assert result.verdict == "DISAGREEMENT"
        assert len(result.discrepancies) == 1
        assert result.discrepancies[0]["type"] == "AMOUNT_MISMATCH"
        assert result.checked_count == result.eligible_count == 1
        detail = result.comparisons[0]
        assert detail["status"] == "DISAGREEMENT"
        assert detail["document_id"] == "doc-1"
        assert detail["document_index"] == 0
        assert detail["observation_indices"] == [0]
        assert Decimal(detail["observed_amount"]) == Decimal("10000")
        assert Decimal(detail["ledger_amount"]) == Decimal("9500")
        assert Decimal(detail["difference"]) == Decimal("500")
        assert Decimal(detail["threshold"]) == Decimal("100")
        assert detail["scope"] == detail["ledger_scope"] == _scope()
        assert "checked" in result.reasoning.lower()
        assert "eligible" in result.reasoning.lower()
        for phrase in ("crime", "fraud", "structuring", "misrepresentation"):
            assert phrase not in result.reasoning.lower()

    def test_consistent_data_no_discrepancy(self) -> None:
        result = _synth_with_mock_nlp().synthesize(_ledger(), [_document()])
        assert result.verdict == "MATCH"
        assert result.discrepancies == []
        assert result.checked_count == result.eligible_count == 1
        assert result.comparisons[0]["status"] == "MATCH"
        assert "checked" in result.reasoning.lower()
        assert "eligible" in result.reasoning.lower()

    @pytest.mark.parametrize("documents", [[], ["No monetary claim."], [{"content": ""}]])
    def test_no_amounts_are_not_a_match(self, documents) -> None:
        result = _synth_with_mock_nlp().synthesize(_ledger(), documents)
        assert result.verdict == "NO_OBSERVATION"
        assert result.extracted_amounts == result.observations == []
        assert result.checked_count == result.eligible_count == 0

    @pytest.mark.parametrize("ledger", [None, {}, {"total_inflow": None}])
    def test_missing_ledger_preserves_observations(self, ledger) -> None:
        result = _synth_with_mock_nlp().synthesize(ledger, [_document()])
        assert result.verdict == "INSUFFICIENT_DATA"
        assert result.extracted_amounts == [Decimal("10000")]
        assert result.observations[0]["document_id"] == "doc-1"
        assert result.checked_count == result.eligible_count == 0

    @pytest.mark.parametrize("amount", ["NaN", "Infinity", "invalid", True, 1.1])
    def test_invalid_ledger_is_not_comparable(self, amount) -> None:
        ledger = _ledger()
        ledger["total_inflow"] = amount
        result = _synth_with_mock_nlp().synthesize(ledger, [_document()])
        assert result.verdict == "INSUFFICIENT_DATA"
        assert result.checked_count == 0

    def test_zero_ledger_still_checks_text(self) -> None:
        result = _synth_with_mock_nlp().synthesize(_ledger("0"), [_document("$50,000 USD")])
        assert result.verdict == "DISAGREEMENT"
        assert len(result.discrepancies) == 1

    def test_partial_amounts_sum_only_within_scoped_components_document(self) -> None:
        result = _synth_with_mock_nlp().synthesize(
            _ledger("8000", aggregation="components"),
            [_document("First $5,000 USD; second $3,000 USD.", aggregation="components")],
        )
        assert result.verdict == "MATCH"
        assert result.checked_count == result.eligible_count == 1
        assert result.comparisons[0]["observation_indices"] == [0, 1]
        assert result.discrepancies == []

    @pytest.mark.parametrize("aggregation", ["total", "components"])
    def test_unrelated_documents_never_sum_to_clear_disagreements(self, aggregation) -> None:
        result = _synth_with_mock_nlp().synthesize(
            _ledger("8000", aggregation=aggregation),
            [
                _document("$5,000 USD", "first", aggregation=aggregation),
                _document("$3,000 USD", "second", aggregation=aggregation),
            ],
        )
        assert result.verdict == "DISAGREEMENT"
        assert len(result.discrepancies) == 2
        assert result.checked_count == result.eligible_count == 2
        assert [item["document_id"] for item in result.comparisons] == ["first", "second"]


class TestComparisonScope:

    @pytest.mark.parametrize("side", ["ledger", "document", "both"])
    def test_equal_unscoped_amounts_are_not_comparable(self, side) -> None:
        ledger, document = _ledger(), _document()
        if side in ("ledger", "both"):
            ledger.pop("scope")
        if side in ("document", "both"):
            document.pop("scope")
        result = _synth_with_mock_nlp().synthesize(ledger, [document])
        assert result.verdict == "NOT_COMPARABLE"
        assert result.checked_count == result.eligible_count == 0
        assert result.comparisons[0]["status"] == "NOT_COMPARABLE"
        assert result.comparisons[0]["reason"]

    def test_unscoped_documents_cannot_match_via_a_global_sum(self) -> None:
        result = _synth_with_mock_nlp().synthesize(_ledger("8000"), ["$5,000 USD", "$3,000 USD"])
        assert result.verdict == "NOT_COMPARABLE"
        assert result.checked_count == result.eligible_count == 0
        assert result.extracted_amounts == [Decimal("5000"), Decimal("3000")]

    def test_match_is_explicitly_limited_to_checked_documents(self) -> None:
        result = _synth_with_mock_nlp().synthesize(_ledger(), [_document(), "$10,000 USD"])
        assert result.verdict == "MATCH"
        assert result.checked_count == result.eligible_count == 1
        assert [item["status"] for item in result.comparisons] == ["MATCH", "NOT_COMPARABLE"]
        assert "2 supplied" in result.reasoning
        assert "Unchecked documents imply no agreement" in result.reasoning

    @pytest.mark.parametrize("field", list(_scope()))
    @pytest.mark.parametrize("side", ["ledger", "document"])
    def test_incomplete_scopes_are_not_comparable(self, field, side) -> None:
        ledger, document = _ledger(), _document()
        target = ledger if side == "ledger" else document
        target["scope"].pop(field)
        result = _synth_with_mock_nlp().synthesize(ledger, [document])
        assert result.verdict == "NOT_COMPARABLE"
        assert result.checked_count == 0

    @pytest.mark.parametrize("change", [
        {"entity_id": "other"}, {"period_start": "2025-01-01"},
        {"period_end": "2026-02-28"}, {"currency": "INR"},
        {"basis": "outflow"}, {"aggregation": "components"},
    ])
    def test_different_scopes_are_not_comparable(self, change) -> None:
        result = _synth_with_mock_nlp().synthesize(_ledger(), [_document(**change)])
        assert result.verdict == "NOT_COMPARABLE"
        assert result.checked_count == result.eligible_count == 0
        assert result.discrepancies == []

    @pytest.mark.parametrize("aggregation", ["", "all", None])
    def test_aggregation_must_be_explicit_and_supported(self, aggregation) -> None:
        result = _synth_with_mock_nlp().synthesize(
            _ledger(aggregation=aggregation), [_document(aggregation=aggregation)],
        )
        assert result.verdict == "NOT_COMPARABLE"

    @pytest.mark.parametrize("text", ["$10,000", "10,000 EUR", "₹10,000", "$10,000 INR"])
    def test_unknown_or_conflicting_observation_currency_is_not_comparable(self, text) -> None:
        result = _synth_with_mock_nlp().synthesize(_ledger(), [_document(text)])
        assert result.verdict == "NOT_COMPARABLE"
        assert result.checked_count == 0

    def test_total_requires_exactly_one_observation(self) -> None:
        result = _synth_with_mock_nlp().synthesize(
            _ledger(), [_document("$5,000 USD and $5,000 USD")],
        )
        assert result.verdict == "NOT_COMPARABLE"
        assert len(result.observations) == 2
        assert result.checked_count == 0

    def test_repeated_components_are_distinct_occurrences(self) -> None:
        result = _synth_with_mock_nlp().synthesize(
            _ledger(aggregation="components"),
            [_document("$5,000 USD and $5,000 USD", aggregation="components")],
        )
        assert result.verdict == "MATCH"
        assert result.extracted_amounts == [Decimal("5000"), Decimal("5000")]
        assert result.comparisons[0]["observation_indices"] == [0, 1]

    def test_mixed_currency_components_cannot_be_summed(self) -> None:
        result = _synth_with_mock_nlp().synthesize(
            _ledger("8000", aggregation="components"),
            [_document("$5,000 USD and 3,000 EUR", aggregation="components")],
        )
        assert result.verdict == "NOT_COMPARABLE"

    def test_ineligible_documents_cannot_clear_eligible_disagreement(self) -> None:
        result = _synth_with_mock_nlp().synthesize(
            _ledger("8000"),
            [_document("$5,000 USD"), _document("$3,000 USD", entity_id="other"), "No amount"],
        )
        assert result.verdict == "DISAGREEMENT"
        assert result.checked_count == result.eligible_count == 1
        assert [item["status"] for item in result.comparisons] == [
            "DISAGREEMENT", "NOT_COMPARABLE", "NO_OBSERVATION",
        ]

    def test_match_does_not_hide_a_disagreement(self) -> None:
        result = _synth_with_mock_nlp().synthesize(
            _ledger(), [_document(), _document("$5,000 USD", "other")],
        )
        assert result.verdict == "DISAGREEMENT"
        assert result.checked_count == result.eligible_count == 2
        assert len(result.discrepancies) == 1

    @pytest.mark.parametrize("code,amount,expected", [
        ("USD", "10100", "MATCH"), ("USD", "10100.0001", "DISAGREEMENT"),
        ("INR", "20000", "MATCH"), ("INR", "20000.0001", "DISAGREEMENT"),
        ("EUR", "10000.0001", "DISAGREEMENT"),
    ])
    def test_threshold_uses_scope_currency_not_legacy_argument(self, code, amount, expected) -> None:
        result = _synth_with_mock_nlp().synthesize(
            _ledger(currency=code), [_document(f"{amount} {code}", currency=code)],
            currency="INR" if code == "USD" else "USD",
        )
        assert result.verdict == expected


class TestMonetaryOccurrences:

    @pytest.mark.parametrize("text,expected", [
        ("$5k", ["5000"]), ("$5K", ["5000"]), ("$1.25k USD", ["1250"]),
        ("$123.4567", ["123.4567"]), ("123.4567 USD", ["123.4567"]),
        ("$10,000 USD", ["10000"]), ("$5,000 and $5,000", ["5000", "5000"]),
        ("₹1,23,456.789", ["123456.789"]), ("Rs. 2.5 lakh", ["250000"]),
        ("₹1.25 crore", ["12500000"]), ("USD 12.345", ["12.345"]),
        ("2 lakh INR", ["200000"]), ("EUR 8,000; $5k; ₹3", ["8000", "5000", "3"]),
        ("$5,000. Done; $2,000, pending.", ["5000", "2000"]),
        ("-$5 USD and USD -2.50", ["-5", "-2.50"]),
        ("$123456789012345678901234567890.123456789k", ["123456789012345678901234567890123.456789"]),
    ])
    def test_exact_occurrence_extraction(self, text, expected) -> None:
        assert _synth_with_mock_nlp().extract_amounts_from_text(text) == list(map(Decimal, expected))

    @pytest.mark.parametrize("token", [
        "$1,23", "$12,34,56 USD", "$123.45.67", "$123..45", "$1e3",
        "$5kk", "$12abc", "$NaN", "$Infinity", "NaN USD", "Infinity USD",
        "$1,000.2.3 USD", "12,34 USD", "$1_000", "acct123USD", "$--5 USD",
        "$1 000 USD", "USD 1 000", "$1, 000 USD", "$1 2 3 USD",
        "$1/2 USD", "USD 1:2", "1\u00a0000 USD",
    ])
    def test_malformed_tokens_do_not_produce_short_valid_amounts(self, token) -> None:
        assert _synth_with_mock_nlp().extract_amounts_from_text(token) == []

    @pytest.mark.parametrize("text,code", [
        ("$5k", None), ("Rs. 5", None), ("2 lakh", None), ("£5", None),
        ("£5 GBP", "GBP"), ("$5 USD", "USD"), ("$5 CAD", "CAD"), ("₹5", "INR"),
        ("5 EUR", "EUR"), ("5 GBP", "GBP"), ("$5 EUR", None),
        ("USD 5 INR", None), ("₹5 USD", None),
    ])
    def test_currency_is_explicit_or_unknown(self, text, code) -> None:
        observations = _synth_with_mock_nlp().extract_monetary_observations(text)
        assert len(observations) == 1
        assert observations[0]["currency"] == code
        assert observations[0]["text"] == text

    def test_observations_preserve_source_span_and_document_identity(self) -> None:
        text = "First $10,000 USD; again $10,000 USD."
        result = _synth_with_mock_nlp().synthesize(
            _ledger(), [{"id": "email-7", "content": text}, "$5k"],
        )
        assert len(result.observations) == 3
        assert result.extracted_amounts == [Decimal("10000"), Decimal("10000"), Decimal("5000")]
        for observation in result.observations:
            source = text if observation["document_index"] == 0 else "$5k"
            assert source[observation["start"]:observation["end"]] == observation["text"]
        first, second, third = result.observations
        assert first["document_id"] == second["document_id"] == "email-7"
        assert first["end"] <= second["start"]
        assert third["document_id"] is None
        assert third["document_index"] == 1

    def test_high_precision_components_and_difference_are_exact(self) -> None:
        result = _synth_with_mock_nlp().synthesize(
            _ledger("100000000000000000000000000001", aggregation="components", currency="EUR"),
            [_document("100000000000000000000000000000 EUR; 1.0000000001 EUR",
                       aggregation="components", currency="EUR")],
        )
        assert result.verdict == "DISAGREEMENT"
        assert Decimal(result.comparisons[0]["difference"]) == Decimal("0.0000000001")

    def test_amount_extraction_does_not_load_spacy(self) -> None:
        synth = EvidenceSynthesizer()
        synth._get_nlp = MagicMock(side_effect=AssertionError("Unexpected spaCy load"))
        assert synth.extract_amounts_from_text("$5k") == [Decimal("5000")]
        assert synth._nlp_loaded is False
        synth._get_nlp.assert_not_called()


# ===================================================================
# TestSpacyNER
# ===================================================================

class TestSpacyNER:

    def test_spacy_extracts_person_entities(self) -> None:
        """PERSON: 'John Smith' extracted via spaCy NER."""
        synth = _synth_with_mock_nlp(
            entities=[("John Smith", "PERSON", 0, 10)]
        )
        entities = synth.extract_entities_from_text("John Smith sent funds.")
        person_ents = [e for e in entities if e["label"] == "PERSON"]
        assert len(person_ents) >= 1
        assert person_ents[0]["text"] == "John Smith"
        assert person_ents[0]["source"] == "spacy_ner"

    def test_spacy_extracts_org_entities(self) -> None:
        """ORG: 'Shell Corp LLC' extracted via spaCy NER."""
        synth = _synth_with_mock_nlp(
            entities=[("Shell Corp LLC", "ORG", 12, 26)]
        )
        entities = synth.extract_entities_from_text(
            "Transfer to Shell Corp LLC completed."
        )
        org_ents = [e for e in entities if e["label"] == "ORG"]
        assert len(org_ents) >= 1
        assert org_ents[0]["text"] == "Shell Corp LLC"
        assert org_ents[0]["source"] == "spacy_ner"

    def test_spacy_extracts_money_entities(self) -> None:
        """MONEY: '$10,000' extracted via spaCy NER."""
        synth = _synth_with_mock_nlp(
            entities=[("$10,000", "MONEY", 15, 22)]
        )
        entities = synth.extract_entities_from_text(
            "Transfer amount $10,000 received."
        )
        money_ents = [e for e in entities if e["label"] == "MONEY"]
        assert len(money_ents) >= 1
        assert money_ents[0]["text"] == "$10,000"


# ===================================================================
# TestRegexExtraction
# ===================================================================

class TestRegexExtraction:

    def test_extracts_entity_references_from_text(self) -> None:
        """Regex extracts 'User 8492' and 'Account ACCT' references."""
        synth = _synth_with_mock_nlp(entities=[])
        text = "User 8492 sent funds to Account ACCT-src_01."
        entities = synth.extract_entities_from_text(text)
        ref_ents = [e for e in entities if e["label"] == "REFERENCE"]
        ref_ids = [e["id"] for e in ref_ents]
        assert "8492" in ref_ids
        assert "ACCT" in ref_ids

    def test_regex_extracts_ifsc(self) -> None:
        """IFSC: SBIN0001234 extracted from embedded text."""
        synth = _synth_with_mock_nlp(entities=[])
        entities = synth.extract_entities_from_text(
            "Branch IFSC: SBIN0001234 verified."
        )
        ifsc_ents = [e for e in entities if e["label"] == "IFSC"]
        assert len(ifsc_ents) >= 1
        assert ifsc_ents[0]["text"] == "SBIN0001234"

    def test_regex_extracts_pan(self) -> None:
        """PAN: ABCDE1234F extracted from embedded text."""
        synth = _synth_with_mock_nlp(entities=[])
        entities = synth.extract_entities_from_text(
            "Customer PAN: ABCDE1234F on file."
        )
        pan_ents = [e for e in entities if e["label"] == "PAN"]
        assert len(pan_ents) >= 1
        assert pan_ents[0]["text"] == "ABCDE1234F"

    def test_regex_extracts_swift(self) -> None:
        """SWIFT: SBININBB extracted from embedded text."""
        synth = _synth_with_mock_nlp(entities=[])
        entities = synth.extract_entities_from_text(
            "Routed via SWIFT: SBININBB for transfer."
        )
        swift_ents = [e for e in entities if e["label"] == "SWIFT"]
        assert len(swift_ents) >= 1
        assert swift_ents[0]["text"] == "SBININBB"

    def test_regex_extracts_iban(self) -> None:
        """IBAN: DE89370400440532013000 extracted from embedded text."""
        synth = _synth_with_mock_nlp(entities=[])
        entities = synth.extract_entities_from_text(
            "Beneficiary IBAN: DE89370400440532013000 confirmed."
        )
        iban_ents = [e for e in entities if e["label"] == "IBAN"]
        assert len(iban_ents) >= 1
        assert iban_ents[0]["text"] == "DE89370400440532013000"


# ===================================================================
# TestMergeAndDedup
# ===================================================================

class TestMergeAndDedup:

    def test_merge_spacy_and_regex_results(self) -> None:
        """
        spaCy + regex results merged without true duplicates.
        Same text with different labels (ORG from spaCy, IFSC from regex)
        produces distinct entries. spaCy PERSON entity also preserved.
        """
        synth = _synth_with_mock_nlp(
            entities=[
                ("John Smith", "PERSON", 0, 10),
                ("SBIN0001234", "ORG", 31, 42),
            ]
        )
        text = "John Smith transferred via IFSC SBIN0001234 to account."
        entities = synth.extract_entities_from_text(text)

        labels_for_sbin = {
            e["label"] for e in entities if e["text"] == "SBIN0001234"
        }
        assert "ORG" in labels_for_sbin
        assert "IFSC" in labels_for_sbin

        assert any(
            e["text"] == "John Smith" and e["label"] == "PERSON"
            for e in entities
        )

    def test_amount_deduplication(self) -> None:
        """
        '$10,000 USD' is one occurrence containing compatible currency markers.
        Overlapping representations must not produce extra Decimal values.
        """
        synth = _synth_with_mock_nlp(entities=[])
        amounts = synth.extract_amounts_from_text(
            "Transfer of $10,000 USD completed."
        )
        assert Decimal("10000") in amounts
        assert amounts.count(Decimal("10000")) == 1


# ===================================================================
# TestV8SearchPatterns
# ===================================================================

class TestV8SearchPatterns:

    def test_search_patterns_find_embedded_codes(self) -> None:
        """v8.0 [P4v8-01]: _SEARCH_COMPILED finds identifiers within text."""
        ifsc_text = "Sent via SBIN0001234 to account"
        assert len(IFSC_SEARCH_COMPILED.findall(ifsc_text)) >= 1

        pan_text = "Customer PAN ABCPP1234F registered"
        assert len(PAN_SEARCH_COMPILED.findall(pan_text)) >= 1

        swift_text = "SWIFT code SBININBB used for the transfer"
        assert len(SWIFT_SEARCH_COMPILED.findall(swift_text)) >= 1

        iban_text = "IBAN DE89370400440532013000 confirmed"
        assert len(IBAN_SEARCH_COMPILED.findall(iban_text)) >= 1

    def test_validation_patterns_do_not_match_embedded(self) -> None:
        """v8.0 [P4v8-01]: _COMPILED (anchored ^$) patterns reject embedded text."""
        assert len(list(IFSC_COMPILED.finditer(
            "Sent via SBIN0001234 to account"
        ))) == 0

        assert len(list(PAN_COMPILED.finditer(
            "PAN code ABCPP1234F on file"
        ))) == 0

        assert len(list(SWIFT_COMPILED.finditer(
            "SWIFT code SBININBB used"
        ))) == 0

        assert len(list(IBAN_COMPILED.finditer(
            "IBAN DE89370400440532013000 confirmed"
        ))) == 0
