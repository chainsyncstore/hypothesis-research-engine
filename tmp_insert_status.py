import sqlite3

conn = sqlite3.connect('results/research.db')
cur = conn.cursor()
cur.execute(
    """
    INSERT INTO hypothesis_status_history (
        hypothesis_id,
        status,
        policy_id,
        batch_id,
        decision_timestamp,
        rationale_json
    ) VALUES (?, ?, ?, ?, datetime('now'), ?)
    """,
    (
        'always_long',
        'PROMOTED',
        'WF_V1',
        'COMPETITION_BOOTSTRAP',
        '["manual force-promotion for competition dry run"]'
    )
)
conn.commit()
conn.close()
print('Inserted PROMOTED status for always_long / WF_V1')
