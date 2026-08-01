from __future__ import annotations

from decimal import Decimal, DivisionByZero, InvalidOperation
from typing import Any


class NumericVerificationError(ValueError):
    pass


def verify_numeric_claims(graph: dict[str, Any], evidence_repository: dict[str, Any]) -> list[dict[str, Any]]:
    records_by_id = {record["evidence_record_id"]: record for record in evidence_repository["evidence_records"]}
    results = []
    for claim in graph["claim_nodes"]:
        formula = _formula_from_claim(claim)
        if formula is None:
            continue
        input_records = [records_by_id[record_id] for record_id in claim["supporting_evidence_record_ids"] if record_id in records_by_id]
        inputs = _numeric_inputs(input_records)
        result = _verify_formula(formula, inputs)
        results.append(
            {
                "numeric_check_id": f"NV-{len(results) + 1:03d}",
                "related_claim_id": claim["claim_id"],
                "inputs": inputs,
                "formula": formula["expression"],
                "computed_result": result["computed_result"],
                "verification_status": result["verification_status"],
                "caveat": result["caveat"],
                "downstream_use_warning": "Numeric verification confirms arithmetic only. It is not a valuation conclusion, recommendation, or direct-source value certification.",
            }
        )
    return results


def _formula_from_claim(claim: dict[str, Any]) -> dict[str, Any] | None:
    formula = claim.get("numeric_formula") or claim.get("calculation_formula") or claim.get("formula")
    if isinstance(formula, str) and formula.strip():
        return {"expression": formula.strip()}
    if isinstance(formula, dict) and isinstance(formula.get("expression"), str) and formula["expression"].strip():
        return formula
    return None


def _numeric_inputs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    inputs = []
    for record in records:
        attributes = record.get("structured_attributes") or {}
        for index, amount in enumerate(attributes.get("amounts", []), start=1):
            parsed = _parse_amount(amount)
            if parsed is None:
                continue
            inputs.append(
                {
                    "label": _input_label(record, index),
                    "amount": parsed,
                    "currency": attributes.get("currency", "unknown"),
                    "evidence_record_id": record["evidence_record_id"],
                    "source_ids": record["source_ids"],
                    "source_tiers": record["source_tiers"],
                }
            )
    return inputs


def _verify_formula(formula: dict[str, Any], inputs: list[dict[str, Any]]) -> dict[str, Any]:
    variables = {input_item["label"]: Decimal(str(input_item["amount"])) for input_item in inputs}
    try:
        computed = _ExpressionParser(formula["expression"], variables).parse()
    except NumericVerificationError as exc:
        return {
            "computed_result": None,
            "verification_status": "insufficient_numeric_support",
            "caveat": f"Numeric formula could not be replayed: {exc}",
        }
    expected = formula.get("expected_result")
    if expected is None:
        return {
            "computed_result": _format_number(computed),
            "verification_status": "passed_with_caveat",
            "caveat": "Explicit formula replayed, but no expected result was provided; arithmetic result is informational and requires downstream review before use.",
        }
    expected_decimal = _to_decimal(expected)
    if expected_decimal is None:
        return {
            "computed_result": _format_number(computed),
            "verification_status": "insufficient_numeric_support",
            "caveat": "Formula supplied an expected result that could not be parsed as a number.",
        }
    status = "passed_with_caveat" if computed == expected_decimal else "failed"
    return {
        "computed_result": _format_number(computed),
        "verification_status": status,
        "caveat": "Explicit formula replayed from provided numeric inputs; preserve source scope and formula caveats before downstream use.",
    }


def _parse_amount(value: Any) -> int | float | None:
    if isinstance(value, (int, float)):
        return value
    if not isinstance(value, str):
        return None
    tokens = value.replace(",", "").replace("$", "").strip().split()
    if not tokens:
        return None
    number = _to_decimal(tokens[0])
    if number is None:
        return None
    multiplier = Decimal(1)
    if len(tokens) > 1:
        unit = tokens[1].lower()
        if unit in {"thousand", "thousands"}:
            multiplier = Decimal(1_000)
        elif unit in {"million", "millions"}:
            multiplier = Decimal(1_000_000)
        elif unit in {"billion", "billions"}:
            multiplier = Decimal(1_000_000_000)
    return _format_number(number * multiplier)


def _to_decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def _input_label(record: dict[str, Any], index: int) -> str:
    attributes = record.get("structured_attributes") or {}
    labels = attributes.get("amount_labels") or attributes.get("input_labels") or []
    if isinstance(labels, list) and index <= len(labels) and isinstance(labels[index - 1], str) and labels[index - 1].strip():
        return _safe_identifier(labels[index - 1])
    return f"input_{len(record.get('evidence_record_id', ''))}_{index}"


def _safe_identifier(value: str) -> str:
    identifier = []
    previous_was_separator = False
    for character in value.lower():
        if character.isalnum() or character == "_":
            identifier.append(character)
            previous_was_separator = False
        elif not previous_was_separator:
            identifier.append("_")
            previous_was_separator = True
    return "".join(identifier).strip("_") or "input"


def _format_number(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


class _ExpressionParser:
    def __init__(self, expression: str, variables: dict[str, Decimal]) -> None:
        self.expression = expression
        self.variables = variables
        self.tokens = self._tokenize(expression)
        self.position = 0

    def parse(self) -> Decimal:
        if not self.tokens:
            raise NumericVerificationError("empty formula")
        value = self._parse_expression()
        if self.position != len(self.tokens):
            raise NumericVerificationError(f"unexpected token {self.tokens[self.position]!r}")
        return value

    def _parse_expression(self) -> Decimal:
        value = self._parse_term()
        while self._peek() in {"+", "-"}:
            operator = self._advance()
            right = self._parse_term()
            value = value + right if operator == "+" else value - right
        return value

    def _parse_term(self) -> Decimal:
        value = self._parse_factor()
        while self._peek() in {"*", "/"}:
            operator = self._advance()
            right = self._parse_factor()
            try:
                value = value * right if operator == "*" else value / right
            except DivisionByZero as exc:
                raise NumericVerificationError("division by zero") from exc
        return value

    def _parse_factor(self) -> Decimal:
        token = self._peek()
        if token is None:
            raise NumericVerificationError("unexpected end of formula")
        if token == "(":
            self._advance()
            value = self._parse_expression()
            if self._peek() != ")":
                raise NumericVerificationError("missing closing parenthesis")
            self._advance()
            return value
        if token == "-":
            self._advance()
            return -self._parse_factor()
        self._advance()
        numeric = _to_decimal(token)
        if numeric is not None:
            return numeric
        if token not in self.variables:
            raise NumericVerificationError(f"missing numeric input {token}")
        return self.variables[token]

    def _peek(self) -> str | None:
        if self.position >= len(self.tokens):
            return None
        return self.tokens[self.position]

    def _advance(self) -> str:
        token = self.tokens[self.position]
        self.position += 1
        return token

    @staticmethod
    def _tokenize(expression: str) -> list[str]:
        tokens = []
        current = ""
        for character in expression:
            if character.isspace():
                if current:
                    tokens.append(current)
                    current = ""
                continue
            if character in "+-*/()":
                if current:
                    tokens.append(current)
                    current = ""
                tokens.append(character)
                continue
            if character.isalnum() or character in {"_", "."}:
                current += character
                continue
            raise NumericVerificationError(f"unsupported character {character!r}")
        if current:
            tokens.append(current)
        return tokens
