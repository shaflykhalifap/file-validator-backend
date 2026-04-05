"""
Database connection pool menggunakan mysql-connector-python.
Koneksi ke MySQL server mdbgo.com.
"""
import json
import mysql.connector
from mysql.connector import pooling
from datetime import datetime
from app.core.config import settings

# Connection pool — dibuat sekali saat startup
_pool: pooling.MySQLConnectionPool | None = None


def get_pool() -> pooling.MySQLConnectionPool:
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="filevalidator_pool",
            pool_size=5,
            host=settings.DB_HOST,
            user=settings.DB_USER,
            password=settings.DB_PASS,
            database=settings.DB_NAME,
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
            autocommit=True,
            connection_timeout=10,
        )
    return _pool


def get_connection():
    """Ambil koneksi dari pool. Selalu close setelah dipakai."""
    return get_pool().get_connection()


# ── CRUD helpers ──────────────────────────────────────────────

def save_validation_result(
    filename: str,
    file_type: str,       # 'price' | 'inventory' | 'master'
    source: str,          # 'inbox' | 'error' | 'upload'
    validated_by: str,
    status: str,          # 'valid' | 'invalid'
    total_rows: int,
    total_errors: int,
    error_details: list,
    notes: str = None,
) -> int:
    """
    Simpan hasil validasi ke tabel file_validations.
    Return: id baris yang baru dibuat.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        sql = """
            INSERT INTO file_validations
                (filename, file_type, source, validated_by, validated_at,
                 status, total_rows, total_errors, error_details, notes)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (
            filename,
            file_type,
            source,
            validated_by,
            datetime.now(),
            status,
            total_rows,
            total_errors,
            json.dumps(error_details, ensure_ascii=False),
            notes,
        ))
        new_id = cursor.lastrowid
        cursor.close()
        return new_id
    finally:
        conn.close()


def get_validation_logs(
    file_type: str = None,
    source: str = None,
    status: str = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """
    Ambil log validasi dari DB dengan filter opsional.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        conditions = []
        params = []
        if file_type:
            conditions.append("file_type = %s")
            params.append(file_type)
        if source:
            conditions.append("source = %s")
            params.append(source)
        if status:
            conditions.append("status = %s")
            params.append(status)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"""
            SELECT id, filename, file_type, source, validated_by,
                   validated_at, status, total_rows, total_errors,
                   error_details, notes, created_at
            FROM file_validations
            {where}
            ORDER BY validated_at DESC
            LIMIT %s OFFSET %s
        """
        params += [limit, offset]
        cursor.execute(sql, params)
        rows = cursor.fetchall()

        # Parse JSON error_details
        for row in rows:
            if row["error_details"]:
                try:
                    row["error_details"] = json.loads(row["error_details"])
                except Exception:
                    row["error_details"] = []
            else:
                row["error_details"] = []
            # Serialize datetime
            for key in ("validated_at", "created_at"):
                if isinstance(row.get(key), datetime):
                    row[key] = row[key].isoformat()

        cursor.close()
        return rows
    finally:
        conn.close()


def get_validation_summary() -> dict:
    """
    Ambil ringkasan statistik untuk dashboard.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        # Total per status
        cursor.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(status = 'valid') AS total_valid,
                SUM(status = 'invalid') AS total_invalid,
                SUM(total_errors) AS total_errors
            FROM file_validations
        """)
        overall = cursor.fetchone()

        # Per file_type
        cursor.execute("""
            SELECT file_type,
                   COUNT(*) AS total,
                   SUM(status = 'valid') AS valid,
                   SUM(status = 'invalid') AS invalid
            FROM file_validations
            GROUP BY file_type
        """)
        by_type = cursor.fetchall()

        # 5 validasi terakhir
        cursor.execute("""
            SELECT id, filename, file_type, source, status,
                   total_rows, total_errors, validated_by, validated_at
            FROM file_validations
            ORDER BY validated_at DESC
            LIMIT 5
        """)
        recent = cursor.fetchall()
        for row in recent:
            if isinstance(row.get("validated_at"), datetime):
                row["validated_at"] = row["validated_at"].isoformat()

        cursor.close()
        return {
            "overall": overall,
            "by_type": by_type,
            "recent": recent,
        }
    finally:
        conn.close()
