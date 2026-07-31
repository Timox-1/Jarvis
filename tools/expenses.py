from datetime import date, timedelta, datetime, timezone
from db.client import get_db

KEMEROVO_TZ = timezone(timedelta(hours=7))


def add_expense(user_id: str, amount: float, category: str = "прочее",
                description: str = None, expense_date: str = None,
                project_id: str = None) -> str:
    db = get_db()
    data = {
        "user_id": user_id,
        "amount": amount,
        "currency": "RUB",
        "category": category,
        "date": expense_date or datetime.now(KEMEROVO_TZ).date().isoformat(),
    }
    if description:
        data["description"] = description
    if project_id:
        data["project_id"] = project_id
    db.table("expenses").insert(data).execute()
    suffix = f" — {description}" if description else ""
    if project_id:
        suffix += " [проект]"
    return f"Расход записан: {amount:.0f}₽ [{category}]" + suffix


def list_expenses(user_id: str, period: str = "week", category: str = None,
                  project_id: str = None) -> list[dict]:
    db = get_db()
    today = date.today()

    if period == "today":
        start = today.isoformat()
    elif period == "week":
        start = (today - timedelta(days=7)).isoformat()
    elif period == "month":
        start = today.replace(day=1).isoformat()
    else:
        start = period  # specific date YYYY-MM-DD

    query = (db.table("expenses")
             .select("*")
             .eq("user_id", user_id)
             .gte("date", start)
             .order("date", desc=True))

    if category:
        query = query.eq("category", category)
    if project_id:
        query = query.eq("project_id", project_id)

    return query.execute().data


def get_expense_summary(user_id: str, period: str = "month", project_id: str = None) -> dict:
    expenses = list_expenses(user_id, period, project_id=project_id)
    total = sum(float(e["amount"]) for e in expenses)

    by_category: dict[str, float] = {}
    for e in expenses:
        cat = e.get("category") or "прочее"
        by_category[cat] = by_category.get(cat, 0) + float(e["amount"])

    return {
        "period": period,
        "total": round(total, 2),
        "currency": "RUB",
        "count": len(expenses),
        "by_category": {k: round(v, 2) for k, v in sorted(by_category.items(), key=lambda x: -x[1])},
    }
