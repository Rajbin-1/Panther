"""
Panther Agent - SQLite Persistence Layer
Manages database initialization, migrations, and safe parameterized queries.
"""

import sqlite3
import os
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("panther.database")

class DatabaseManager:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # Place in user local data or working directory
            base_dir = os.environ.get("PANTHER_DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
            os.makedirs(base_dir, exist_ok=True)
            self.db_path = os.path.join(base_dir, "panther_agent.db")
        else:
            self.db_path = db_path
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
            
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_db(self):
        """Initializes tables using safe parameterized DDL statements."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Application Configuration
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS application_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            # 2. Device Profile
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS device_profile (
                    id TEXT PRIMARY KEY,
                    hostname TEXT NOT NULL,
                    os_version TEXT NOT NULL,
                    arch TEXT NOT NULL,
                    cpu_cores INTEGER NOT NULL,
                    total_ram_mb INTEGER NOT NULL,
                    primary_display TEXT NOT NULL,
                    dpi_scale REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            # 3. Task History
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_history (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    state TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    total_turns INTEGER DEFAULT 0,
                    success INTEGER DEFAULT 0,
                    termination_reason TEXT
                );
            """)

            # 4. Task Turns & Events
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_events (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    turn_index INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    proposal_summary TEXT,
                    action_type TEXT,
                    action_params TEXT,
                    action_result TEXT,
                    verification_rule TEXT,
                    verification_passed INTEGER DEFAULT 0,
                    verification_details TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES task_history(id) ON DELETE CASCADE
                );
            """)

            # 5. Errors
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS errors (
                    id TEXT PRIMARY KEY,
                    task_id TEXT,
                    component TEXT NOT NULL,
                    error_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    traceback TEXT,
                    recoverable INTEGER DEFAULT 1,
                    timestamp TEXT NOT NULL
                );
            """)

            # 6. Model Installations
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS model_installations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    size_bytes INTEGER DEFAULT 0,
                    ram_estimate_mb INTEGER DEFAULT 0,
                    suitable_for_6gb INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 0,
                    verified_at TEXT NOT NULL
                );
            """)

            # 7. Setup State
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS setup_state (
                    step TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    details TEXT,
                    verified_at TEXT NOT NULL
                );
            """)

            # 7b. Persistent Setup Session (Stage 3 state machine & checkpointing)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS setup_session (
                    id TEXT PRIMARY KEY,
                    current_state TEXT NOT NULL,
                    setup_version TEXT NOT NULL,
                    checkpoint TEXT NOT NULL,
                    selected_model TEXT,
                    download_progress TEXT,
                    verification_status TEXT,
                    runtime_test_status TEXT,
                    failure_info TEXT,
                    completed INTEGER DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
            """)

            # Lightweight migrations for existing tables
            try:
                cursor.execute("ALTER TABLE device_profile ADD COLUMN profile_json TEXT;")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE device_profile ADD COLUMN tier INTEGER DEFAULT 1;")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE device_profile ADD COLUMN tier_name TEXT DEFAULT 'Tier 1: Minimal';")
            except Exception:
                pass

            # 8. Diagnostics Logs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS diagnostics_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    component TEXT NOT NULL,
                    message TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT NOT NULL
                );
            """)

            # Create performance indices
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_events_task ON task_events(task_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnostics_level ON diagnostics_logs(level);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnostics_time ON diagnostics_logs(created_at);")
            
            conn.commit()
            logger.info("SQLite persistence initialized successfully at %s", self.db_path)

    # Configuration access
    def get_config(self, key: str, default: Any = None) -> Any:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM application_config WHERE key = ?;", (key,))
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row["value"])
                except Exception:
                    return row["value"]
            return default

    def set_config(self, key: str, value: Any) -> None:
        val_str = json.dumps(value) if not isinstance(value, str) else value
        now = datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO application_config (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at;",
                (key, val_str, now)
            )
            conn.commit()

    def get_all_config(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM application_config;")
            rows = cursor.fetchall()
            result = {}
            for r in rows:
                try:
                    result[r["key"]] = json.loads(r["value"])
                except Exception:
                    result[r["key"]] = r["value"]
            return result

    # Diagnostics logging
    def log_diagnostic(self, level: str, component: str, message: str, metadata: Optional[Dict[str, Any]] = None):
        now = datetime.utcnow().isoformat()
        meta_str = json.dumps(metadata) if metadata else None
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO diagnostics_logs (level, component, message, metadata, created_at) VALUES (?, ?, ?, ?, ?);",
                (level.upper(), component, message, meta_str, now)
            )
            conn.commit()

    def get_diagnostics(self, limit: int = 100, min_level: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if min_level:
                cursor.execute(
                    "SELECT * FROM diagnostics_logs WHERE level = ? ORDER BY id DESC LIMIT ?;",
                    (min_level.upper(), limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM diagnostics_logs ORDER BY id DESC LIMIT ?;",
                    (limit,)
                )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    # Task persistence
    def record_task_start(self, task_id: str, title: str, goal: str, state: str) -> None:
        now = datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO task_history (id, title, goal, state, started_at) VALUES (?, ?, ?, ?, ?);",
                (task_id, title, goal, state, now)
            )
            conn.commit()

    def update_task_state(self, task_id: str, state: str, success: Optional[bool] = None, termination_reason: Optional[str] = None, turns: Optional[int] = None) -> None:
        now = datetime.utcnow().isoformat() if state in ("COMPLETE", "FAILED", "CANCELLED") else None
        with self.get_connection() as conn:
            updates = ["state = ?"]
            params: List[Any] = [state]
            if now:
                updates.append("ended_at = ?")
                params.append(now)
            if success is not None:
                updates.append("success = ?")
                params.append(1 if success else 0)
            if termination_reason is not None:
                updates.append("termination_reason = ?")
                params.append(termination_reason)
            if turns is not None:
                updates.append("total_turns = ?")
                params.append(turns)
            params.append(task_id)
            query = f"UPDATE task_history SET {', '.join(updates)} WHERE id = ?;"
            conn.execute(query, tuple(params))
            conn.commit()

    def record_task_event(self, event_id: str, task_id: str, turn_index: int, state: str, 
                          proposal_summary: str, action_type: Optional[str], action_params: Optional[Dict[str, Any]], 
                          action_result: Optional[Dict[str, Any]], verification_rule: Optional[Dict[str, Any]], 
                          verification_passed: bool, verification_details: Optional[str]) -> None:
        now = datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO task_events (
                    id, task_id, turn_index, state, proposal_summary, action_type, 
                    action_params, action_result, verification_rule, verification_passed, 
                    verification_details, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    event_id, task_id, turn_index, state, proposal_summary, action_type,
                    json.dumps(action_params) if action_params else None,
                    json.dumps(action_result) if action_result else None,
                    json.dumps(verification_rule) if verification_rule else None,
                    1 if verification_passed else 0,
                    verification_details,
                    now
                )
            )
            conn.commit()

    def get_task_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM task_history ORDER BY started_at DESC LIMIT ?;", (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def get_task_details(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM task_history WHERE id = ?;", (task_id,))
            task_row = cursor.fetchone()
            if not task_row:
                return None
            cursor.execute("SELECT * FROM task_events WHERE task_id = ? ORDER BY turn_index ASC;", (task_id,))
            events = [dict(r) for r in cursor.fetchall()]
            # parse json fields
            for ev in events:
                for f in ["action_params", "action_result", "verification_rule"]:
                    if ev.get(f):
                        try:
                            ev[f] = json.loads(ev[f])
                        except Exception:
                            pass
            task_data = dict(task_row)
            task_data["events"] = events
            return task_data

    # Error recording
    def record_error(self, err_id: str, task_id: Optional[str], component: str, error_type: str, 
                     message: str, traceback_str: Optional[str], recoverable: bool = True) -> None:
        now = datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO errors (id, task_id, component, error_type, message, traceback, recoverable, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
                (err_id, task_id, component, error_type, message, traceback_str, 1 if recoverable else 0, now)
            )
            conn.commit()

    # Models & Setup
    def save_device_profile(self, profile: Dict[str, Any]) -> None:
        now = datetime.utcnow().isoformat()
        profile_json = json.dumps(profile)
        tier = profile.get("tier", 1)
        tier_name = profile.get("tier_name", "Tier 1: Minimal")
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO device_profile (
                    id, hostname, os_version, arch, cpu_cores, total_ram_mb, primary_display, dpi_scale, profile_json, tier, tier_name, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    hostname = excluded.hostname,
                    os_version = excluded.os_version,
                    arch = excluded.arch,
                    cpu_cores = excluded.cpu_cores,
                    total_ram_mb = excluded.total_ram_mb,
                    primary_display = excluded.primary_display,
                    dpi_scale = excluded.dpi_scale,
                    profile_json = excluded.profile_json,
                    tier = excluded.tier,
                    tier_name = excluded.tier_name,
                    updated_at = excluded.updated_at;
                """,
                (
                    profile.get("id", "dev_primary"),
                    profile.get("hostname", "localhost"),
                    profile.get("os_version", "Windows"),
                    profile.get("arch", "x64"),
                    profile.get("cpu_cores", 2),
                    profile.get("total_ram_mb", 6144),
                    profile.get("primary_display", "1920x1080"),
                    float(profile.get("dpi_scale", 1.0)),
                    profile_json,
                    tier,
                    tier_name,
                    now,
                    now
                )
            )
            conn.commit()

    def get_device_profile(self) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM device_profile ORDER BY updated_at DESC LIMIT 1;")
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            if res.get("profile_json"):
                try:
                    nested = json.loads(res["profile_json"])
                    for k, v in nested.items():
                        if k not in res or res[k] is None:
                            res[k] = v
                    res["profile"] = nested
                except Exception:
                    pass
            return res

    def save_setup_session(self, session: Dict[str, Any]) -> None:
        now = datetime.utcnow().isoformat()
        session_id = session.get("id", "default")
        current_state = session.get("current_state", "NOT_STARTED")
        setup_version = session.get("setup_version", "1.0.0")
        checkpoint = session.get("checkpoint", current_state)
        selected_model = session.get("selected_model", "")
        download_progress = json.dumps(session.get("download_progress", {}))
        verification_status = json.dumps(session.get("verification_status", {}))
        runtime_test_status = json.dumps(session.get("runtime_test_status", {}))
        failure_info = json.dumps(session.get("failure_info")) if session.get("failure_info") else None
        completed = 1 if session.get("completed", False) else 0

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO setup_session (
                    id, current_state, setup_version, checkpoint, selected_model,
                    download_progress, verification_status, runtime_test_status,
                    failure_info, completed, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    current_state = excluded.current_state,
                    setup_version = excluded.setup_version,
                    checkpoint = excluded.checkpoint,
                    selected_model = excluded.selected_model,
                    download_progress = excluded.download_progress,
                    verification_status = excluded.verification_status,
                    runtime_test_status = excluded.runtime_test_status,
                    failure_info = excluded.failure_info,
                    completed = excluded.completed,
                    updated_at = excluded.updated_at;
                """,
                (
                    session_id, current_state, setup_version, checkpoint, selected_model,
                    download_progress, verification_status, runtime_test_status,
                    failure_info, completed, now
                )
            )
            conn.commit()

    def get_setup_session(self, session_id: str = "default") -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM setup_session WHERE id = ?;", (session_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            for json_field in ["download_progress", "verification_status", "runtime_test_status", "failure_info"]:
                if res.get(json_field):
                    try:
                        res[json_field] = json.loads(res[json_field])
                    except Exception:
                        pass
            res["completed"] = bool(res.get("completed", 0))
            return res

    def save_model(self, model: Dict[str, Any]) -> None:
        now = datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO model_installations (id, name, provider, size_bytes, ram_estimate_mb, suitable_for_6gb, is_active, verified_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    provider = excluded.provider,
                    size_bytes = excluded.size_bytes,
                    ram_estimate_mb = excluded.ram_estimate_mb,
                    suitable_for_6gb = excluded.suitable_for_6gb,
                    is_active = excluded.is_active,
                    verified_at = excluded.verified_at;
                """,
                (
                    model["id"], model["name"], model.get("provider", "ollama"),
                    model.get("size_bytes", 0), model.get("ram_estimate_mb", 0),
                    1 if model.get("suitable_for_6gb", True) else 0,
                    1 if model.get("is_active", False) else 0,
                    now
                )
            )
            conn.commit()

    def get_models(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM model_installations ORDER BY name ASC;")
            return [dict(r) for r in cursor.fetchall()]

    def set_setup_step(self, step: str, status: str, details: Optional[str] = None) -> None:
        now = datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO setup_state (step, status, details, verified_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(step) DO UPDATE SET
                    status = excluded.status,
                    details = excluded.details,
                    verified_at = excluded.verified_at;
                """,
                (step, status, details, now)
            )
            conn.commit()

    def get_setup_state(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM setup_state;")
            return {r["step"]: dict(r) for r in cursor.fetchall()}
