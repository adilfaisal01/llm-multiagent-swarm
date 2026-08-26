"""Date calculator tool — date arithmetic, weekdays, and age computations."""
from __future__ import annotations
from datetime import date, datetime
from .base import BaseTool

_DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


class DateCalculator(BaseTool):
    """Compute date arithmetic: days between dates, weekday, age, offsets.

    A pure transform — nothing is logged to the scratchpad. Accepts dates in
    ``YYYY-MM-DD`` or ``YYYY-MM-DD HH:MM`` form and answers common date
    subquestions without the model doing arithmetic in its head.
    """

    name = "date_calculator"
    description = (
        "Compute with dates: days between two dates, weekday of a date, age "
        "from a birthdate, or adding/subtracting days. Pass dates as "
        "YYYY-MM-DD. Use for any date-math the question requires."
    )
    parameters = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "description": "One of: 'days_between', 'weekday', 'age', 'add_days'",
            },
            "date1": {
                "type": "string",
                "description": "First date (YYYY-MM-DD)",
            },
            "date2": {
                "type": "string",
                "description": "Second date (YYYY-MM-DD); required for days_between",
            },
            "days": {
                "type": "number",
                "description": "Days to add (positive) or subtract (negative); required for add_days",
            },
        },
        "required": ["operation", "date1"],
    }

    def run(self, args: dict, worker_name: str = "") -> str:
        """Execute a date calculation.

        Args:
            args: Tool arguments. ``operation`` and ``date1`` are required;
                ``date2`` (for ``days_between``) and ``days`` (for
                ``add_days``) depend on the operation.
            worker_name: Unused by this tool; accepted for interface parity.

        Returns:
            The computed result, or an error string starting with ``Error:``.
        """
        op = args.get("operation", "")
        date1_raw = args.get("date1", "")
        if not op:
            return "Error: no operation provided"
        if not date1_raw:
            return "Error: no date1 provided"

        d1 = _parse_date(date1_raw)
        if d1 is None:
            return f"Error: invalid date1 '{date1_raw}' (use YYYY-MM-DD)"

        if op == "days_between":
            date2_raw = args.get("date2", "")
            if not date2_raw:
                return "Error: no date2 provided for days_between"
            d2 = _parse_date(date2_raw)
            if d2 is None:
                return f"Error: invalid date2 '{date2_raw}' (use YYYY-MM-DD)"
            delta = abs((d2 - d1).days)
            return f"{delta} days between {date1_raw} and {date2_raw}"

        if op == "weekday":
            return f"{date1_raw} is a {_DAY_NAMES[d1.weekday()]}"

        if op == "age":
            today = date.today()
            years = today.year - d1.year - ((today.month, today.day) < (d1.month, d1.day))
            if years < 0:
                return f"{date1_raw} is in the future"
            return f"Age from {date1_raw}: {years} years"

        if op == "add_days":
            days_raw = args.get("days")
            if days_raw is None:
                return "Error: days must be provided for add_days"
            try:
                n = int(days_raw)
            except (TypeError, ValueError):
                return "Error: days must be an integer"
            result = date.fromordinal(d1.toordinal() + n)
            return f"{date1_raw} plus {n} days = {result.isoformat()} ({_DAY_NAMES[result.weekday()]})"

        return f"Error: unknown operation '{op}' (choose from days_between, weekday, age, add_days)"


def _parse_date(raw: str) -> date | None:
    """Parse YYYY-MM-DD (or ISO with time) into a date."""
    text = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


TOOLS = [DateCalculator()]
BUNDLES = ["code", "research", "all"]
