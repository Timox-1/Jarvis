from datetime import date, timedelta, datetime, timezone
from db.client import get_db

KEMEROVO_TZ = timezone(timedelta(hours=7))


def add_income(user_id: str, amount: float, source: str = "прочее",
               description: str = None, income_date: str = None) -> str:
    db = get_db()
    data = {
        "user_id": user_id,
        "amount": amount,
        "currency": "RUB",
        "source": source,
        "date": income_date or datetime.now(KEMEROVO_TZ).date().isoformat(),
    }
    if description:
        data["description"] = description
    db.table("income").insert(data).execute()
    return f"Доход записан: {amount:.0f}₽ [{source}]" + (f" — {description}" if description else "")


def list_income(user_id: str, period: str = "month", source: str = None) -> list[dict]:
    db = get_db()
    today = date.today()

    if period == "today":
        start = today.isoformat()
    elif period == "week":
        start = (today - timedelta(days=7)).isoformat()
    elif period == "month":
        start = today.replace(day=1).isoformat()
    else:
        start = period

    query = (db.table("income")
             .select("*")
             .eq("user_id", user_id)
             .gte("date", start)
             .order("date", desc=True))

    if source:
        query = query.eq("source", source)

    return query.execute().data


def get_financial_summary(user_id: str, period: str = "month") -> dict:
    from tools.expenses import get_expense_summary

    income_records = list_income(user_id, period)
    total_income = sum(float(r["amount"]) for r in income_records)

    by_source: dict[str, float] = {}
    for r in income_records:
        src = r.get("source") or "прочее"
        by_source[src] = by_source.get(src, 0) + float(r["amount"])

    expenses = get_expense_summary(user_id, period)

    return {
        "period": period,
        "currency": "RUB",
        "income": {
            "total": round(total_income, 2),
            "count": len(income_records),
            "by_source": {k: round(v, 2) for k, v in sorted(by_source.items(), key=lambda x: -x[1])},
        },
        "expenses": {
            "total": expenses["total"],
            "count": expenses["count"],
            "by_category": expenses["by_category"],
        },
        "profit": round(total_income - expenses["total"], 2),
    }
