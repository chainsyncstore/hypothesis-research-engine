from config.settings import get_settings
from storage.repositories import EvaluationRepository

settings = get_settings()
repo = EvaluationRepository(settings.database_path)
rows = repo.get_hypotheses_by_status("PROMOTED", policy_id="WF_V1")
print(f"PROMOTED hypotheses found: {len(rows)}")
for h in rows:
    print(h)
