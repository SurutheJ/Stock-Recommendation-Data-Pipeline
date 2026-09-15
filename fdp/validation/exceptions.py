class SchemaValidationError(Exception):
    """A single row failed type/range validation and was rejected."""


class BusinessRuleViolation(Exception):
    """A cross-row business rule was violated (used for hard failures only;
    most business-rule findings are soft warnings, see `business_rules.py`)."""
