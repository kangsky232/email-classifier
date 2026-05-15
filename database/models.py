import json
import os
import hashlib

from database.db import db


USE_SQLITE = os.getenv("USE_SQLITE", "true").lower() == "true"


class User:
    @staticmethod
    def _hash_password(password):
        return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def create(username, password):
        sql = "INSERT INTO users (username, password) VALUES (%s, %s)"
        cursor = db.execute(sql, (username, User._hash_password(password)))
        last_id = cursor.lastrowid
        cursor.close()
        return last_id

    @staticmethod
    def authenticate(username, password):
        sql = "SELECT * FROM users WHERE username = %s AND password = %s"
        return db.fetch_one(sql, (username, User._hash_password(password)))

    @staticmethod
    def get_by_id(user_id):
        sql = "SELECT id, username, created_at FROM users WHERE id = %s"
        return db.fetch_one(sql, (user_id,))


class Email:
    @staticmethod
    def create(sender, subject, content, user_id=None):
        sql = "INSERT INTO emails (sender, subject, content, user_id) VALUES (%s, %s, %s, %s)"
        cursor = db.execute(sql, (sender, subject, content, user_id))
        last_id = cursor.lastrowid
        cursor.close()
        return last_id

    @staticmethod
    def get_by_id(email_id):
        sql = "SELECT * FROM emails WHERE id = %s"
        return db.fetch_one(sql, (email_id,))

    @staticmethod
    def get_list(page=1, limit=10, search=None, category=None, user_id=None):
        page = max(int(page or 1), 1)
        limit = max(int(limit or 10), 1)
        offset = (page - 1) * limit

        base_sql = """
            SELECT e.*, fr.category AS final_category, fr.method AS final_method
            FROM emails e
            LEFT JOIN final_results fr ON e.id = fr.email_id
            WHERE 1=1
        """
        count_sql = """
            SELECT COUNT(*) AS total
            FROM emails e
            LEFT JOIN final_results fr ON e.id = fr.email_id
            WHERE 1=1
        """
        params = []

        if user_id:
            base_sql += " AND e.user_id = %s"
            count_sql += " AND e.user_id = %s"
            params.append(user_id)

        if search:
            base_sql += " AND (e.sender LIKE %s OR e.subject LIKE %s OR e.content LIKE %s)"
            count_sql += " AND (e.sender LIKE %s OR e.subject LIKE %s OR e.content LIKE %s)"
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])

        if category:
            base_sql += " AND fr.category = %s"
            count_sql += " AND fr.category = %s"
            params.append(category)

        count_params = tuple(params)
        total_row = db.fetch_one(count_sql, count_params) or {"total": 0}

        base_sql += " ORDER BY e.created_at DESC LIMIT %s OFFSET %s"
        data = db.fetch_all(base_sql, tuple(params + [limit, offset]))

        return {"total": total_row["total"], "data": data, "page": page, "limit": limit}

    @staticmethod
    def update(email_id, sender, subject, content):
        sql = "UPDATE emails SET sender=%s, subject=%s, content=%s WHERE id=%s"
        db.execute(sql, (sender, subject, content, email_id)).close()
        return True

    @staticmethod
    def delete(email_id):
        sql = "DELETE FROM emails WHERE id = %s"
        db.execute(sql, (email_id,)).close()
        return True


class Classification:
    @staticmethod
    def create(email_id, agent_name, method, category, confidence):
        sql = """
            INSERT INTO classifications (email_id, agent_name, method, category, confidence)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor = db.execute(sql, (email_id, agent_name, method, category, confidence))
        last_id = cursor.lastrowid
        cursor.close()
        return last_id

    @staticmethod
    def get_by_email(email_id):
        sql = "SELECT * FROM classifications WHERE email_id = %s ORDER BY created_at DESC"
        return db.fetch_all(sql, (email_id,))

    @staticmethod
    def get_agent_stats():
        sql = """
            SELECT
                c.agent_name,
                c.method,
                COUNT(*) AS total,
                AVG(c.confidence) AS avg_confidence,
                SUM(CASE WHEN c.category = fr.category THEN 1 ELSE 0 END) AS correct
            FROM classifications c
            LEFT JOIN final_results fr ON c.email_id = fr.email_id
            GROUP BY c.agent_name, c.method
        """
        return db.fetch_all(sql)


class PaxosLog:
    @staticmethod
    def create(email_id, proposal_id, phase, proposer, value, result, acceptor_votes=None):
        votes_json = json.dumps(acceptor_votes, ensure_ascii=False) if acceptor_votes is not None else None
        sql = """
            INSERT INTO paxos_logs
                (email_id, proposal_id, phase, proposer, value, result, acceptor_votes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor = db.execute(sql, (email_id, proposal_id, phase, proposer, value, result, votes_json))
        last_id = cursor.lastrowid
        cursor.close()
        return last_id

    @staticmethod
    def get_by_email(email_id):
        sql = "SELECT * FROM paxos_logs WHERE email_id = %s ORDER BY created_at ASC"
        return db.fetch_all(sql, (email_id,))

    @staticmethod
    def get_list(page=1, limit=10, email_id=None):
        page = max(int(page or 1), 1)
        limit = max(int(limit or 10), 1)
        offset = (page - 1) * limit

        base_sql = "SELECT * FROM paxos_logs WHERE 1=1"
        count_sql = "SELECT COUNT(*) AS total FROM paxos_logs WHERE 1=1"
        params = []

        if email_id:
            base_sql += " AND email_id = %s"
            count_sql += " AND email_id = %s"
            params.append(email_id)

        total_row = db.fetch_one(count_sql, tuple(params)) or {"total": 0}
        base_sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        data = db.fetch_all(base_sql, tuple(params + [limit, offset]))

        return {"total": total_row["total"], "data": data, "page": page, "limit": limit}


class FinalResult:
    @staticmethod
    def create(email_id, category, method):
        if USE_SQLITE:
            sql = """
                INSERT INTO final_results (email_id, category, method)
                VALUES (%s, %s, %s)
                ON CONFLICT(email_id) DO UPDATE SET
                    category = excluded.category,
                    method = excluded.method
            """
            params = (email_id, category, method)
        else:
            sql = """
                INSERT INTO final_results (email_id, category, method)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE category = VALUES(category), method = VALUES(method)
            """
            params = (email_id, category, method)

        db.execute(sql, params).close()
        return True

    @staticmethod
    def get_by_email(email_id):
        sql = "SELECT * FROM final_results WHERE email_id = %s"
        return db.fetch_one(sql, (email_id,))

    @staticmethod
    def get_stats():
        if USE_SQLITE:
            overview_sql = """
                SELECT
                    (SELECT COUNT(*) FROM emails) AS total_emails,
                    (SELECT COUNT(*) FROM final_results WHERE date(created_at) = date('now')) AS today_classified,
                    (SELECT COUNT(*) FROM paxos_logs WHERE phase = 'learn') AS consensus_count,
                    (SELECT COUNT(*) FROM final_results) AS total_results
            """
            trend_sql = """
                SELECT date(created_at) AS date, COUNT(*) AS count
                FROM final_results
                WHERE created_at >= date('now', '-7 days')
                GROUP BY date(created_at)
                ORDER BY date ASC
            """
        else:
            overview_sql = """
                SELECT
                    (SELECT COUNT(*) FROM emails) AS total_emails,
                    (SELECT COUNT(*) FROM final_results WHERE DATE(created_at) = CURDATE()) AS today_classified,
                    (SELECT COUNT(*) FROM paxos_logs WHERE phase = 'learn') AS consensus_count,
                    (SELECT COUNT(*) FROM final_results) AS total_results
            """
            trend_sql = """
                SELECT DATE(created_at) AS date, COUNT(*) AS count
                FROM final_results
                WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
                GROUP BY DATE(created_at)
                ORDER BY date ASC
            """

        overview = db.fetch_one(overview_sql) or {}
        categories = db.fetch_all(
            "SELECT category, COUNT(*) AS count FROM final_results GROUP BY category ORDER BY count DESC"
        )
        trends = db.fetch_all(trend_sql)

        return {"overview": overview, "categories": categories, "trends": trends}


class SystemConfig:
    @staticmethod
    def get(key):
        sql = "SELECT config_value FROM system_config WHERE config_key = %s"
        result = db.fetch_one(sql, (key,))
        if not result:
            return None
        return SystemConfig._decode_value(result["config_value"])

    @staticmethod
    def set(key, value):
        if isinstance(value, (list, dict)):
            value = json.dumps(value, ensure_ascii=False)

        if USE_SQLITE:
            sql = """
                INSERT INTO system_config (config_key, config_value)
                VALUES (%s, %s)
                ON CONFLICT(config_key) DO UPDATE SET config_value = excluded.config_value
            """
            params = (key, value)
        else:
            sql = """
                INSERT INTO system_config (config_key, config_value)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)
            """
            params = (key, value)

        db.execute(sql, params).close()
        return True

    @staticmethod
    def get_all():
        results = db.fetch_all("SELECT config_key, config_value FROM system_config")
        return {row["config_key"]: SystemConfig._decode_value(row["config_value"]) for row in results}

    @staticmethod
    def _decode_value(value):
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return value
