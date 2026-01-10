import sqlite3

conn = sqlite3.connect('results/research.db')
cur = conn.cursor()
cur.execute(
    """
    SELECT h.hypothesis_id,
           sh.status,
           sh.policy_id,
           sh.batch_id,
           sh.decision_timestamp
    FROM hypotheses h
    JOIN hypothesis_status_history sh
      ON sh.hypothesis_id = h.hypothesis_id
    WHERE sh.history_id = (
      SELECT MAX(history_id)
      FROM hypothesis_status_history h2
      WHERE h2.hypothesis_id = h.hypothesis_id
    )
    ORDER BY h.hypothesis_id;
    """
)
rows = cur.fetchall()
for row in rows:
    print(row)
conn.close()
