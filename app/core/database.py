"""
Database connection dan fungsi CRUD untuk FileValidator.
Auto-limit 150 riwayat per file_type. Saat insert dan sudah >= 150,
hapus yang paling lama otomatis.
"""
import json
import mysql.connector
from datetime import datetime
from typing import Optional
from app.core.config import settings

MAX_LOGS_PER_TYPE = 150


def get_connection():
    return mysql.connector.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASS,
        database=settings.DB_NAME,
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
        autocommit=True,
        connection_timeout=5,
        connect_timeout=5,
    )


def _safe_query(fn):
    try:
        conn = get_connection()
        try:
            return fn(conn)
        finally:
            conn.close()
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return None


def check_filename_exists(filename: str, file_type: str) -> bool:
    """Cek apakah nama file sudah pernah divalidasi di kategori yang sama."""
    def _fn(conn):
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM file_validations WHERE filename = %s AND file_type = %s",
            (filename, file_type)
        )
        count = cursor.fetchone()[0]
        cursor.close()
        return count > 0
    result = _safe_query(_fn)
    return result if result is not None else False


def _enforce_limit(conn, file_type: str):
    """
    Pastikan jumlah riwayat per file_type tidak melebihi MAX_LOGS_PER_TYPE.
    Jika sudah >= 150, hapus yang paling lama sejumlah kelebihan + 1 slot baru.
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM file_validations WHERE file_type = %s",
        (file_type,)
    )
    count = cursor.fetchone()[0]
    if count >= MAX_LOGS_PER_TYPE:
        to_delete = count - MAX_LOGS_PER_TYPE + 1
        cursor.execute(
            """
            DELETE FROM file_validations
            WHERE file_type = %s
            ORDER BY validated_at ASC
            LIMIT %s
            """,
            (file_type, to_delete)
        )
        print(f"[DB] Auto-deleted {to_delete} old log(s) for {file_type}")
    cursor.close()


def save_validation_result(
    filename: str,
    file_type: str,
    source: str,
    validated_by: str,
    status: str,
    total_rows: int,
    total_errors: int,
    error_details: list,
    notes: str = None,
    raw_lines: list = None,
) -> int:
    def _fn(conn):
        _enforce_limit(conn, file_type)
        cursor = conn.cursor()
        raw_lines_json = json.dumps(raw_lines, ensure_ascii=False) if raw_lines else None
        cursor.execute(
            """
            INSERT INTO file_validations
                (filename, file_type, source, validated_by, validated_at,
                 status, total_rows, total_errors, error_details, notes, raw_lines)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (filename, file_type, source, validated_by, datetime.now(),
             status, total_rows, total_errors,
             json.dumps(error_details, ensure_ascii=False),
             notes, raw_lines_json)
        )
        new_id = cursor.lastrowid
        cursor.close()
        return new_id
    return _safe_query(_fn)


def get_validation_logs(
    file_type: str = None,
    source: str = None,
    status: str = None,
    limit: int = 150,
    offset: int = 0,
) -> list:
    def _fn(conn):
        cursor = conn.cursor(dictionary=True)
        conditions, params = [], []
        if file_type:
            conditions.append("file_type = %s"); params.append(file_type)
        if source:
            conditions.append("source = %s"); params.append(source)
        if status:
            conditions.append("status = %s"); params.append(status)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        safe_limit = min(limit, MAX_LOGS_PER_TYPE)
        cursor.execute(
            f"SELECT * FROM file_validations {where} ORDER BY validated_at DESC LIMIT %s OFFSET %s",
            params + [safe_limit, offset]
        )
        rows = cursor.fetchall()
        cursor.close()
        for row in rows:
            if row.get("error_details"):
                try:
                    row["error_details"] = json.loads(row["error_details"])
                except Exception:
                    row["error_details"] = []
            if row.get("raw_lines"):
                try:
                    row["raw_lines"] = json.loads(row["raw_lines"])
                except Exception:
                    row["raw_lines"] = None
            for key in ("validated_at", "created_at"):
                if isinstance(row.get(key), datetime):
                    row[key] = row[key].isoformat()
        return rows
    result = _safe_query(_fn)
    return result if result is not None else []




def get_validation_summary() -> dict:
    def _fn(conn):
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT COUNT(*) AS total,
                   SUM(status = 'valid') AS total_valid,
                   SUM(status = 'invalid') AS total_invalid,
                   SUM(total_errors) AS total_errors
            FROM file_validations
        """)
        overall = cursor.fetchone()
        cursor.execute("""
            SELECT file_type, COUNT(*) AS total,
                   SUM(status = 'valid') AS valid,
                   SUM(status = 'invalid') AS invalid
            FROM file_validations GROUP BY file_type
        """)
        by_type = cursor.fetchall()
        cursor.execute("""
            SELECT id, filename, file_type, source, status,
                   total_rows, total_errors, validated_by, validated_at
            FROM file_validations ORDER BY validated_at DESC LIMIT 5
        """)
        recent = cursor.fetchall()
        cursor.close()
        for row in recent:
            if isinstance(row.get("validated_at"), datetime):
                row["validated_at"] = row["validated_at"].isoformat()
        return {"overall": overall, "by_type": by_type, "recent": recent}
    result = _safe_query(_fn)
    return result if result is not None else {"overall": {}, "by_type": [], "recent": []}
