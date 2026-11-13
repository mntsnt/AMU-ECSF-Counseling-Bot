import sqlite3
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from config import DATABASE_PATH

def get_connection() -> sqlite3.Connection:
    """Returns a SQLite connection with row factory enabled."""
    conn = sqlite3.connect(DATABASE_PATH, timeout=15.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """Initializes the database schema and sequences."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Create cases table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                case_id INTEGER PRIMARY KEY AUTOINCREMENT,
                seeker_id INTEGER NOT NULL,
                counselor_id INTEGER DEFAULT NULL,
                status TEXT NOT NULL CHECK(status IN ('PENDING', 'ACTIVE', 'CLOSED')),
                initial_question TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                claimed_at TIMESTAMP DEFAULT NULL,
                closed_at TIMESTAMP DEFAULT NULL,
                closed_by TEXT DEFAULT NULL
            )
        """)

        # Create case messages log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS case_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                sender_role TEXT NOT NULL CHECK(sender_role IN ('SEEKER', 'COUNSELOR', 'SYSTEM')),
                message_type TEXT NOT NULL,
                content_snippet TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (case_id) REFERENCES cases (case_id) ON DELETE CASCADE
            )
        """)

        # Indexes for fast lookup
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cases_seeker ON cases(seeker_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cases_counselor ON cases(counselor_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status)")

        # Ensure starting case_id is 1001 for clean numbering
        cursor.execute("SELECT count(*) FROM cases")
        count = cursor.fetchone()[0]
        if count == 0:
            cursor.execute("""
                INSERT OR IGNORE INTO sqlite_sequence (name, seq) 
                VALUES ('cases', 1000)
            """)

        conn.commit()

def create_case(seeker_id: int, initial_question: str) -> int:
    """
    Creates a new counseling case in PENDING status.
    Returns the newly generated case_id.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO cases (seeker_id, status, initial_question, created_at)
            VALUES (?, 'PENDING', ?, CURRENT_TIMESTAMP)
        """, (seeker_id, initial_question))
        case_id = cursor.lastrowid
        conn.commit()
        return case_id

def get_case(case_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve details for a specific case."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_open_case_for_seeker(seeker_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieves the seeker's current pending or active case if one exists.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM cases 
            WHERE seeker_id = ? AND status IN ('PENDING', 'ACTIVE')
            ORDER BY case_id DESC LIMIT 1
        """, (seeker_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_active_case_for_counselor(counselor_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieves the case currently being handled by the specified counselor.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM cases 
            WHERE counselor_id = ? AND status = 'ACTIVE'
            ORDER BY case_id DESC LIMIT 1
        """, (counselor_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def claim_case(case_id: int, counselor_id: int) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Atomically claims a pending case for a counselor.
    Ensures counselor does not already have an active case and case is still pending.
    Returns (success, message, case_dict).
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Check if counselor already has an active case
        cursor.execute("""
            SELECT case_id FROM cases 
            WHERE counselor_id = ? AND status = 'ACTIVE'
        """, (counselor_id,))
        active_row = cursor.fetchone()
        if active_row:
            return False, f"You already have an active session (Case #{active_row['case_id']}). Please close or release it first.", None

        # 2. Attempt atomic claim
        cursor.execute("""
            UPDATE cases 
            SET counselor_id = ?, status = 'ACTIVE', claimed_at = CURRENT_TIMESTAMP
            WHERE case_id = ? AND status = 'PENDING'
        """, (counselor_id, case_id))

        if cursor.rowcount == 0:
            # Check why it failed
            cursor.execute("SELECT status, counselor_id FROM cases WHERE case_id = ?", (case_id,))
            row = cursor.fetchone()
            if not row:
                return False, "This case does not exist.", None
            if row["status"] != "PENDING":
                return False, "This case has already been accepted by another counselor or is closed.", None
            return False, "Could not claim this case.", None

        conn.commit()

        # Fetch updated record
        cursor.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,))
        case_data = dict(cursor.fetchone())
        return True, "Case accepted successfully.", case_data

def close_case(case_id: int, closed_by: str) -> bool:
    """
    Concludes and closes an open (PENDING or ACTIVE) case.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE cases 
            SET status = 'CLOSED', closed_at = CURRENT_TIMESTAMP, closed_by = ?
            WHERE case_id = ? AND status IN ('PENDING', 'ACTIVE')
        """, (closed_by, case_id))
        conn.commit()
        return cursor.rowcount > 0

def release_case(case_id: int, counselor_id: int) -> bool:
    """
    Releases an active case back to PENDING so another counselor can take it.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE cases 
            SET counselor_id = NULL, status = 'PENDING', claimed_at = NULL
            WHERE case_id = ? AND counselor_id = ? AND status = 'ACTIVE'
        """, (case_id, counselor_id))
        conn.commit()
        return cursor.rowcount > 0

def get_pending_cases(limit: int = 15) -> List[Dict[str, Any]]:
    """Returns a list of all currently pending cases awaiting a counselor."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM cases 
            WHERE status = 'PENDING'
            ORDER BY case_id ASC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

def get_statistics() -> Dict[str, int]:
    """Returns total, pending, active, and closed case counts."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END) as active,
                SUM(CASE WHEN status = 'CLOSED' THEN 1 ELSE 0 END) as closed
            FROM cases
        """)
        row = cursor.fetchone()
        return {
            "total": row["total"] or 0,
            "pending": row["pending"] or 0,
            "active": row["active"] or 0,
            "closed": row["closed"] or 0,
        }

def log_message(case_id: int, sender_role: str, message_type: str, content_snippet: str = "") -> None:
    """Logs message metadata for session tracking."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO case_messages (case_id, sender_role, message_type, content_snippet)
                VALUES (?, ?, ?, ?)
            """, (case_id, sender_role, message_type, content_snippet[:200] if content_snippet else ""))
            conn.commit()
    except Exception as e:
        print(f"[Database] Error logging message for Case #{case_id}: {e}")
