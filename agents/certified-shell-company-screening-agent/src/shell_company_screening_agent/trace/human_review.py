def open_blocking_reviews(rows):
    return [r for r in rows if r.get("signoff_blocking") == "Yes" and r.get("status") != "completed"]
