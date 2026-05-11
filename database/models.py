from database.db import db
import json
import os

USE_SQLITE = os.getenv('USE_SQLITE', 'true').lower() == 'true'

class Email:
    @staticmethod
    def create(sender, subject, content):
        sql = "INSERT INTO emails (sender, subject, content) VALUES (%s, %s, %s)"
        cursor = db.execute(sql, (sender, subject, content))
        return cursor.lastrowid
    
    @staticmethod
    def get_by_id(email_id):
        sql = "SELECT * FROM emails WHERE id = %s"
        return db.fetch_one(sql, (email_id,))
    
    @staticmethod
    def get_list(page=1, limit=10, search=None, category=None):
        offset = (page - 1) * limit
        base_sql = """
            SELECT e.*, fr.category as final_category, fr.method as final_method 
            FROM emails e 
            LEFT JOIN final_results fr ON e.id = fr.email_id 
            WHERE 1=1
        """
        count_sql = "SELECT COUNT(*) as total FROM emails e LEFT JOIN final_results fr ON e.id = fr.email_id WHERE 1=1"
        params = []
        
        if search:
            base_sql += " AND (e.sender LIKE %s OR e.subject LIKE %s OR e.content LIKE %s)"
            count_sql += " AND (e.sender LIKE %s OR e.subject LIKE %s OR e.content LIKE %s)"
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        if category:
            base_sql += " AND fr.category = %s"
            count_sql += " AND fr.category = %s"
            params.append(category)
        
        total = db.fetch_one(count_sql, params)['total']
        
        base_sql += " ORDER BY e.created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        data = db.fetch_all(base_sql, params)
        
        return {"total": total, "data": data, "page": page, "limit": limit}
    
    @staticmethod
    def delete(email_id):
        sql = "DELETE FROM emails WHERE id = %s"
        db.execute(sql, (email_id,))
        return True
    
    @staticmethod
    def update(email_id, sender, subject, content):
        sql = "UPDATE emails SET sender=%s, subject=%s, content=%s WHERE id=%s"
        db.execute(sql, (sender, subject, content, email_id))
        return True

class Classification:
    @staticmethod
    def create(email_id, agent_name, method, category, confidence):
        sql = "INSERT INTO classifications (email_id, agent_name, method, category, confidence) VALUES (%s, %s, %s, %s, %s)"
        cursor = db.execute(sql, (email_id, agent_name, method, category, confidence))
        return cursor.lastrowid
    
    @staticmethod
    def get_by_email(email_id):
        sql = "SELECT * FROM classifications WHERE email_id = %s ORDER BY created_at DESC"
        return db.fetch_all(sql, (email_id,))
    
    @staticmethod
    def get_agent_stats():
        sql = """
            SELECT agent_name, method, COUNT(*) as total, 
                   AVG(confidence) as avg_confidence,
                   SUM(CASE WHEN category = fr.category THEN 1 ELSE 0 END) as correct
            FROM classifications c
            LEFT JOIN final_results fr ON c.email_id = fr.email_id
            GROUP BY agent_name, method
        """
        return db.fetch_all(sql)

class PaxosLog:
    @staticmethod
    def create(email_id, proposal_id, phase, proposer, value, result, acceptor_votes=None):
        votes_json = json.dumps(acceptor_votes) if acceptor_votes else None
        sql = "INSERT INTO paxos_logs (email_id, proposal_id, phase, proposer, value, result, acceptor_votes) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        cursor = db.execute(sql, (email_id, proposal_id, phase, proposer, value, result, votes_json))
        return cursor.lastrowid
    
    @staticmethod
    def get_by_email(email_id):
        sql = "SELECT * FROM paxos_logs WHERE email_id = %s ORDER BY created_at ASC"
        return db.fetch_all(sql, (email_id,))
    
    @staticmethod
    def get_list(page=1, limit=10, email_id=None):
        offset = (page - 1) * limit
        base_sql = "SELECT * FROM paxos_logs WHERE 1=1"
        count_sql = "SELECT COUNT(*) as total FROM paxos_logs WHERE 1=1"
        params = []
        
        if email_id:
            base_sql += " AND email_id = %s"
            count_sql += " AND email_id = %s"
            params.append(email_id)
        
        total = db.fetch_one(count_sql, params)['total']
        base_sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        data = db.fetch_all(base_sql, params)
        
        return {"total": total, "data": data, "page": page, "limit": limit}

class FinalResult:
    @staticmethod
    def create(email_id, category, method):
        if USE_SQLITE:
            existing = db.fetch_one("SELECT id FROM final_results WHERE email_id = ?", (email_id,))
            if existing:
                db.execute("UPDATE final_results SET category=?, method=? WHERE email_id=?", (category, method, email_id))
            else:
                db.execute("INSERT INTO final_results (email_id, category, method) VALUES (?, ?, ?)", (email_id, category, method))
        else:
            sql = "INSERT INTO final_results (email_id, category, method) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE category=%s, method=%s"
            db.execute(sql, (email_id, category, method, category, method))
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
                    (SELECT COUNT(*) FROM emails) as total_emails,
                    (SELECT COUNT(*) FROM emails WHERE date(created_at) = date('now')) as today_classified,
                    (SELECT COUNT(*) FROM paxos_logs WHERE phase = 'learn') as consensus_count,
                    (SELECT COUNT(*) FROM final_results) as total_results
            """
            trend_sql = """
                SELECT date(created_at) as date, COUNT(*) as count 
                FROM final_results 
                WHERE created_at >= date('now', '-7 days')
                GROUP BY date(created_at) 
                ORDER BY date ASC
            """
        else:
            overview_sql = """
                SELECT 
                    (SELECT COUNT(*) FROM emails) as total_emails,
                    (SELECT COUNT(*) FROM emails WHERE DATE(created_at) = CURDATE()) as today_classified,
                    (SELECT COUNT(*) FROM paxos_logs WHERE phase = 'learn') as consensus_count,
                    (SELECT COUNT(*) FROM final_results) as total_results
            """
            trend_sql = """
                SELECT DATE(created_at) as date, COUNT(*) as count 
                FROM final_results 
                WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
                GROUP BY DATE(created_at) 
                ORDER BY date ASC
            """
        overview = db.fetch_one(overview_sql)
        
        category_sql = "SELECT category, COUNT(*) as count FROM final_results GROUP BY category"
        categories = db.fetch_all(category_sql)
        
        trends = db.fetch_all(trend_sql)
        
        return {"overview": overview, "categories": categories, "trends": trends}

class SystemConfig:
    @staticmethod
    def get(key):
        sql = "SELECT config_value FROM system_config WHERE config_key = %s"
        result = db.fetch_one(sql, (key,))
        if result:
            try:
                return json.loads(result['config_value'])
            except:
                return result['config_value']
        return None
    
    @staticmethod
    def set(key, value):
        if isinstance(value, (list, dict)):
            value = json.dumps(value, ensure_ascii=False)
        if USE_SQLITE:
            existing = db.fetch_one("SELECT id FROM system_config WHERE config_key = ?", (key,))
            if existing:
                db.execute("UPDATE system_config SET config_value = ? WHERE config_key = ?", (value, key))
            else:
                db.execute("INSERT INTO system_config (config_key, config_value) VALUES (?, ?)", (key, value))
        else:
            sql = "INSERT INTO system_config (config_key, config_value) VALUES (%s, %s) ON DUPLICATE KEY UPDATE config_value = %s"
            db.execute(sql, (key, value, value))
        return True
    
    @staticmethod
    def get_all():
        sql = "SELECT * FROM system_config"
        results = db.fetch_all(sql)
        config = {}
        for r in results:
            try:
                config[r['config_key']] = json.loads(r['config_value'])
            except:
                config[r['config_key']] = r['config_value']
        return config
