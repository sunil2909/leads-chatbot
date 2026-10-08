import csv
from pathlib import Path


FIELD_MAP = {
    "Lead Number": "lead_number",
    "Lead Origin": "lead_origin",
    "Lead Source": "lead_source",
    "Do Not Email": "do_not_email",
    "Do Not Call": "do_not_call",
    "Converted": "converted",
    "TotalVisits": "total_visits",
    "Total Time Spent on Website": "total_time_spent_on_website",
    "Page Views Per Visit": "page_views_per_visit",
    "Last Activity": "last_activity",
    "Country": "country",
    "Specialization": "specialization",
    "What is your current occupation": "current_occupation",
    "Lead Quality": "lead_quality",
    "Lead Profile": "lead_profile",
    "City": "city",
    "Last Notable Activity": "last_notable_activity",
}
INTEGER_FIELDS = {"lead_number", "total_visits", "total_time_spent_on_website"}
FLOAT_FIELDS = {"page_views_per_visit"}
YES_NO_FIELDS = {"do_not_email", "do_not_call"}


def read_leads_csv(path: Path) -> list[dict[str, object | None]]:
    with path.open(newline="", encoding="utf-8-sig") as csv_file:
        rows = csv.DictReader(csv_file)
        leads = []

        for row in rows:
            lead: dict[str, object | None] = {}
            for source_name, field_name in FIELD_MAP.items():
                value = (row[source_name] or "").strip()
                if not value:
                    lead[field_name] = None
                elif field_name in INTEGER_FIELDS:
                    lead[field_name] = int(value)
                elif field_name in FLOAT_FIELDS:
                    lead[field_name] = float(value)
                elif field_name in YES_NO_FIELDS:
                    lead[field_name] = {"Yes": True, "No": False}[value]
                elif field_name == "converted":
                    lead[field_name] = {"0": False, "1": True}[value]
                else:
                    lead[field_name] = value
            leads.append(lead)

    return leads