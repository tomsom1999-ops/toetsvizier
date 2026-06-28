from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .paths import BACKUP_DIR


SCHEMA_VERSION = 6
AUTO_BACKUP_KEEP_COUNT = 30
AUTO_BACKUP_KEEP_DAYS = 14

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS school_years (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    start_date TEXT,
    end_date TEXT,
    is_active INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_year_id INTEGER NOT NULL REFERENCES school_years(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    level TEXT,
    grade_year TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(school_year_id, name)
);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_number TEXT,
    first_name TEXT,
    last_name TEXT,
    display_name TEXT NOT NULL,
    email TEXT,
    level TEXT,
    grade_year TEXT,
    student_number_key TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS student_attributes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    field_type TEXT NOT NULL,
    options_json TEXT
);

CREATE TABLE IF NOT EXISTS student_attribute_values (
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    attribute_id INTEGER NOT NULL REFERENCES student_attributes(id) ON DELETE CASCADE,
    value TEXT,
    PRIMARY KEY (student_id, attribute_id)
);

CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    school_year_id INTEGER NOT NULL REFERENCES school_years(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, class_id)
);

CREATE TABLE IF NOT EXISTS comparable_test_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_year_id INTEGER NOT NULL REFERENCES school_years(id),
    name TEXT NOT NULL,
    period TEXT NOT NULL,
    test_type TEXT NOT NULL,
    grade_year TEXT,
    level TEXT,
    test_date TEXT,
    available_time_minutes INTEGER,
    weight REAL NOT NULL DEFAULT 1 CHECK (weight >= 0),
    is_resit INTEGER NOT NULL DEFAULT 0 CHECK (is_resit IN (0, 1)),
    original_test_id INTEGER REFERENCES tests(id),
    comparable_test_group_id INTEGER REFERENCES comparable_test_groups(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS test_classes (
    test_id INTEGER NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    PRIMARY KEY (test_id, class_id)
);

CREATE TABLE IF NOT EXISTS test_students (
    test_id INTEGER NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (test_id, student_id)
);

CREATE TABLE IF NOT EXISTS taxonomy_definitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    is_standard INTEGER NOT NULL DEFAULT 0 CHECK (is_standard IN (0, 1))
);

CREATE TABLE IF NOT EXISTS taxonomy_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    taxonomy_id INTEGER NOT NULL REFERENCES taxonomy_definitions(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE(taxonomy_id, name)
);

CREATE TABLE IF NOT EXISTS question_bank_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    short_description TEXT,
    status TEXT NOT NULL DEFAULT 'Actief',
    maximum_score REAL NOT NULL,
    expected_time_minutes REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS question_bank_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES question_bank_items(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL DEFAULT 1,
    title TEXT NOT NULL,
    question_text TEXT,
    short_description TEXT,
    maximum_score REAL NOT NULL,
    expected_time_minutes REAL,
    is_multiple_choice INTEGER NOT NULL DEFAULT 0 CHECK (is_multiple_choice IN (0, 1)),
    multiple_choice_answer TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(item_id, version_number)
);

CREATE TABLE IF NOT EXISTS question_bank_subquestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id INTEGER NOT NULL REFERENCES question_bank_versions(id) ON DELETE CASCADE,
    subquestion TEXT NOT NULL,
    question_text TEXT,
    short_description TEXT,
    maximum_score REAL NOT NULL,
    expected_time_minutes REAL,
    is_multiple_choice INTEGER NOT NULL DEFAULT 0 CHECK (is_multiple_choice IN (0, 1)),
    multiple_choice_answer TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE(version_id, subquestion)
);

CREATE TABLE IF NOT EXISTS question_bank_version_taxonomy_values (
    version_id INTEGER NOT NULL REFERENCES question_bank_versions(id) ON DELETE CASCADE,
    taxonomy_id INTEGER NOT NULL REFERENCES taxonomy_definitions(id) ON DELETE CASCADE,
    taxonomy_value_id INTEGER NOT NULL REFERENCES taxonomy_values(id) ON DELETE CASCADE,
    PRIMARY KEY (version_id, taxonomy_id)
);

CREATE TABLE IF NOT EXISTS question_bank_version_property_values (
    version_id INTEGER NOT NULL REFERENCES question_bank_versions(id) ON DELETE CASCADE,
    property_id INTEGER NOT NULL REFERENCES property_definitions(id) ON DELETE CASCADE,
    value TEXT,
    PRIMARY KEY (version_id, property_id)
);

CREATE TABLE IF NOT EXISTS question_bank_subquestion_taxonomy_values (
    subquestion_id INTEGER NOT NULL REFERENCES question_bank_subquestions(id) ON DELETE CASCADE,
    taxonomy_id INTEGER NOT NULL REFERENCES taxonomy_definitions(id) ON DELETE CASCADE,
    taxonomy_value_id INTEGER NOT NULL REFERENCES taxonomy_values(id) ON DELETE CASCADE,
    PRIMARY KEY (subquestion_id, taxonomy_id)
);

CREATE TABLE IF NOT EXISTS question_bank_subquestion_property_values (
    subquestion_id INTEGER NOT NULL REFERENCES question_bank_subquestions(id) ON DELETE CASCADE,
    property_id INTEGER NOT NULL REFERENCES property_definitions(id) ON DELETE CASCADE,
    value TEXT,
    PRIMARY KEY (subquestion_id, property_id)
);

CREATE TABLE IF NOT EXISTS matrix_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id INTEGER NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    question_number TEXT NOT NULL,
    subquestion TEXT,
    maximum_score REAL NOT NULL CHECK (maximum_score >= 0),
    short_description TEXT,
    expected_time_minutes REAL CHECK (expected_time_minutes IS NULL OR expected_time_minutes >= 0),
    is_multiple_choice INTEGER NOT NULL DEFAULT 0 CHECK (is_multiple_choice IN (0, 1)),
    multiple_choice_answer TEXT,
    multiple_choice_correction_enabled INTEGER NOT NULL DEFAULT 0 CHECK (multiple_choice_correction_enabled IN (0, 1)),
    multiple_choice_correction_mode TEXT NOT NULL DEFAULT 'none',
    multiple_choice_extra_answers TEXT,
    question_bank_id INTEGER REFERENCES question_bank_items(id),
    question_bank_version_id INTEGER REFERENCES question_bank_versions(id),
    question_bank_subquestion_id INTEGER REFERENCES question_bank_subquestions(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(test_id, question_number, subquestion)
);

CREATE TABLE IF NOT EXISTS property_definitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    field_type TEXT NOT NULL,
    choices_json TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS question_property_values (
    question_id INTEGER NOT NULL REFERENCES matrix_questions(id) ON DELETE CASCADE,
    property_id INTEGER NOT NULL REFERENCES property_definitions(id) ON DELETE CASCADE,
    value TEXT,
    PRIMARY KEY (question_id, property_id)
);

CREATE TABLE IF NOT EXISTS question_taxonomy_values (
    question_id INTEGER NOT NULL REFERENCES matrix_questions(id) ON DELETE CASCADE,
    taxonomy_id INTEGER NOT NULL REFERENCES taxonomy_definitions(id) ON DELETE CASCADE,
    taxonomy_value_id INTEGER NOT NULL REFERENCES taxonomy_values(id) ON DELETE CASCADE,
    PRIMARY KEY (question_id, taxonomy_id)
);

CREATE TABLE IF NOT EXISTS test_taxonomy_selections (
    test_id INTEGER NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    taxonomy_id INTEGER NOT NULL REFERENCES taxonomy_definitions(id) ON DELETE CASCADE,
    PRIMARY KEY (test_id, taxonomy_id)
);

CREATE TABLE IF NOT EXISTS test_property_selections (
    test_id INTEGER NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    property_id INTEGER NOT NULL REFERENCES property_definitions(id) ON DELETE CASCADE,
    PRIMARY KEY (test_id, property_id)
);

CREATE TABLE IF NOT EXISTS test_property_option_selections (
    test_id INTEGER NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    property_id INTEGER NOT NULL REFERENCES property_definitions(id) ON DELETE CASCADE,
    value TEXT NOT NULL,
    PRIMARY KEY (test_id, property_id, value)
);

CREATE TABLE IF NOT EXISTS test_analysis_parts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id INTEGER NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(test_id, sort_order)
);

CREATE TABLE IF NOT EXISTS question_analysis_parts (
    question_id INTEGER PRIMARY KEY REFERENCES matrix_questions(id) ON DELETE CASCADE,
    part_id INTEGER REFERENCES test_analysis_parts(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS normalizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id INTEGER NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    method TEXT NOT NULL,
    configuration_json TEXT NOT NULL DEFAULT '{}',
    decimal_places INTEGER NOT NULL DEFAULT 1,
    rounding_method TEXT NOT NULL DEFAULT 'standaard',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS test_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id INTEGER NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'niet gemaakt',
    grade REAL,
    total_score REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(test_id, student_id)
);

CREATE TABLE IF NOT EXISTS scores (
    attempt_id INTEGER NOT NULL REFERENCES test_attempts(id) ON DELETE CASCADE,
    question_id INTEGER NOT NULL REFERENCES matrix_questions(id) ON DELETE CASCADE,
    score REAL CHECK (score IS NULL OR score >= 0),
    response_text TEXT,
    PRIMARY KEY (attempt_id, question_id)
);

CREATE TABLE IF NOT EXISTS report_exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type TEXT NOT NULL,
    test_id INTEGER REFERENCES tests(id),
    file_path TEXT NOT NULL,
    exported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_classes_year ON classes(school_year_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_student ON enrollments(student_id);
CREATE INDEX IF NOT EXISTS idx_tests_year ON tests(school_year_id);
CREATE INDEX IF NOT EXISTS idx_test_students_student ON test_students(student_id);
CREATE INDEX IF NOT EXISTS idx_matrix_questions_test ON matrix_questions(test_id);
CREATE INDEX IF NOT EXISTS idx_question_bank_versions_item ON question_bank_versions(item_id);
CREATE INDEX IF NOT EXISTS idx_question_bank_subquestions_version ON question_bank_subquestions(version_id);
CREATE INDEX IF NOT EXISTS idx_question_taxonomies_question ON question_taxonomy_values(question_id);
CREATE INDEX IF NOT EXISTS idx_test_taxonomies_test ON test_taxonomy_selections(test_id);
CREATE INDEX IF NOT EXISTS idx_test_properties_test ON test_property_selections(test_id);
CREATE INDEX IF NOT EXISTS idx_test_property_options_test ON test_property_option_selections(test_id);
CREATE INDEX IF NOT EXISTS idx_test_analysis_parts_test ON test_analysis_parts(test_id);
CREATE INDEX IF NOT EXISTS idx_question_analysis_parts_part ON question_analysis_parts(part_id);
CREATE INDEX IF NOT EXISTS idx_attempts_test ON test_attempts(test_id);
CREATE INDEX IF NOT EXISTS idx_attempts_student ON test_attempts(student_id);
CREATE INDEX IF NOT EXISTS idx_attempts_test_student ON test_attempts(test_id, student_id);
CREATE INDEX IF NOT EXISTS idx_scores_attempt ON scores(attempt_id);
CREATE INDEX IF NOT EXISTS idx_scores_question ON scores(question_id);
"""

STANDARD_TAXONOMIES = {
    "RTTI": ["R", "T1", "T2", "I"],
    "OBIT": ["Onthouden", "Begrijpen", "Integreren", "Toepassen"],
    "Bloom": [
        "Onthouden",
        "Begrijpen",
        "Toepassen",
        "Analyseren",
        "Evalueren",
        "Creeren",
    ],
}

DEFAULT_PROPERTIES = [
    ("Domein", "keuzelijst"),
    ("Leerdoel", "tekst"),
    ("Vraagtype", "keuzelijst"),
]


class SubjectDatabase:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    @classmethod
    def create(cls, path: Path | str, subject_name: str, school_year: str) -> "SubjectDatabase":
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        database = cls(path)
        database.connection.executescript(SCHEMA)
        database._migrate_schema()
        database.set_meta("schema_version", str(SCHEMA_VERSION))
        database.set_meta("subject_name", subject_name.strip())
        database.set_meta("created_at", datetime.now().isoformat(timespec="seconds"))
        database.add_school_year(school_year, active=True)
        database._seed_defaults()
        database.connection.commit()
        return database

    @classmethod
    def open(cls, path: Path | str) -> "SubjectDatabase":
        database = cls(path)
        database.backup_before_schema_migration()
        database.connection.executescript(SCHEMA)
        database._migrate_schema()
        database.set_meta("schema_version", str(SCHEMA_VERSION))
        database._seed_defaults()
        database.connection.commit()
        return database

    def close(self) -> None:
        self.connection.close()

    def backup(self, *, automatic: bool = False) -> Path:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        kind = "auto" if automatic else "handmatig"
        target = BACKUP_DIR / f"{self.path.stem}-{kind}-{stamp}.db"
        self.connection.commit()
        shutil.copy2(self.path, target)
        if automatic:
            self.cleanup_automatic_backups()
        return target

    def cleanup_automatic_backups(
        self,
        *,
        keep_count: int = AUTO_BACKUP_KEEP_COUNT,
        keep_days: int = AUTO_BACKUP_KEEP_DAYS,
    ) -> None:
        if keep_count < 1:
            keep_count = 1
        cutoff_timestamp = datetime.now().timestamp() - keep_days * 24 * 60 * 60
        auto_backups = sorted(
            BACKUP_DIR.glob(f"{self.path.stem}-auto-*.db"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for index, backup_path in enumerate(auto_backups):
            if index < keep_count:
                continue
            try:
                if backup_path.stat().st_mtime < cutoff_timestamp:
                    backup_path.unlink()
            except FileNotFoundError:
                continue

    def backup_before_schema_migration(self) -> Path | None:
        current_version = self.current_schema_version()
        if current_version is not None and current_version >= SCHEMA_VERSION:
            return None
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        from_version = "onbekend" if current_version is None else str(current_version)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        target = BACKUP_DIR / (
            f"{self.path.stem}-voor-update-v{from_version}-naar-v{SCHEMA_VERSION}-{stamp}.db"
        )
        self.connection.commit()
        shutil.copy2(self.path, target)
        return target

    def current_schema_version(self) -> int | None:
        try:
            has_meta_table = self.connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='app_meta'"
            ).fetchone()
            if not has_meta_table:
                return None
            row = self.connection.execute("SELECT value FROM app_meta WHERE key='schema_version'").fetchone()
        except sqlite3.Error:
            return None
        if not row:
            return None
        try:
            return int(str(row["value"]))
        except (TypeError, ValueError):
            return None

    def set_meta(self, key: str, value: str) -> None:
        self.connection.execute(
            "INSERT INTO app_meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def meta(self, key: str, default: str = "") -> str:
        result = self.connection.execute("SELECT value FROM app_meta WHERE key = ?", (key,)).fetchone()
        return result["value"] if result else default

    def _migrate_schema(self) -> None:
        def columns(table: str) -> set[str]:
            return {
                row["name"] for row in self.connection.execute(f"PRAGMA table_info({table})").fetchall()
            }

        def add_column(table: str, name: str, definition: str) -> None:
            if name not in columns(table):
                self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")

        test_columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(tests)").fetchall()
        }
        if "weight" not in test_columns:
            self.connection.execute(
                "ALTER TABLE tests ADD COLUMN weight REAL NOT NULL DEFAULT 1 CHECK (weight >= 0)"
            )
        question_columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(matrix_questions)").fetchall()
        }
        if "is_multiple_choice" not in question_columns:
            self.connection.execute(
                "ALTER TABLE matrix_questions ADD COLUMN is_multiple_choice INTEGER NOT NULL DEFAULT 0 CHECK (is_multiple_choice IN (0, 1))"
            )
        if "multiple_choice_answer" not in question_columns:
            self.connection.execute("ALTER TABLE matrix_questions ADD COLUMN multiple_choice_answer TEXT")
        if "multiple_choice_correction_enabled" not in question_columns:
            self.connection.execute(
                "ALTER TABLE matrix_questions ADD COLUMN multiple_choice_correction_enabled INTEGER NOT NULL DEFAULT 0 CHECK (multiple_choice_correction_enabled IN (0, 1))"
            )
        if "multiple_choice_correction_mode" not in question_columns:
            self.connection.execute(
                "ALTER TABLE matrix_questions ADD COLUMN multiple_choice_correction_mode TEXT NOT NULL DEFAULT 'none'"
            )
        if "multiple_choice_extra_answers" not in question_columns:
            self.connection.execute("ALTER TABLE matrix_questions ADD COLUMN multiple_choice_extra_answers TEXT")
        if "question_bank_id" not in question_columns:
            self.connection.execute("ALTER TABLE matrix_questions ADD COLUMN question_bank_id INTEGER")
        if "question_bank_version_id" not in question_columns:
            self.connection.execute("ALTER TABLE matrix_questions ADD COLUMN question_bank_version_id INTEGER")
        if "question_bank_subquestion_id" not in question_columns:
            self.connection.execute("ALTER TABLE matrix_questions ADD COLUMN question_bank_subquestion_id INTEGER")
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_matrix_questions_bank ON matrix_questions(question_bank_id)"
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_matrix_questions_bank_version ON matrix_questions(question_bank_version_id)"
        )
        item_columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(question_bank_items)").fetchall()
        }
        if "status" not in item_columns:
            self.connection.execute("ALTER TABLE question_bank_items ADD COLUMN status TEXT NOT NULL DEFAULT 'Actief'")
        score_columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(scores)").fetchall()
        }
        if "response_text" not in score_columns:
            self.connection.execute("ALTER TABLE scores ADD COLUMN response_text TEXT")
        add_column("property_definitions", "is_active", "is_active INTEGER NOT NULL DEFAULT 1")
        add_column("student_attributes", "options_json", "options_json TEXT")
        add_column("students", "student_number_key", "student_number_key TEXT")
        self.connection.execute(
            "UPDATE students SET student_number_key=LOWER(TRIM(student_number)) "
            "WHERE student_number IS NOT NULL AND TRIM(student_number)<>'' "
            "AND (student_number_key IS NULL OR student_number_key='')"
        )
        duplicate_keys = [
            row["student_number_key"]
            for row in self.connection.execute(
                "SELECT student_number_key FROM students "
                "WHERE student_number_key IS NOT NULL AND student_number_key<>'' "
                "GROUP BY student_number_key HAVING COUNT(*) > 1"
            ).fetchall()
        ]
        for duplicate_key in duplicate_keys:
            self.connection.execute(
                "UPDATE students SET student_number_key=NULL "
                "WHERE student_number_key=? "
                "AND id NOT IN (SELECT MIN(id) FROM students WHERE student_number_key=?)",
                (duplicate_key, duplicate_key),
            )
        self.connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_students_student_number_key "
            "ON students(student_number_key) WHERE student_number_key IS NOT NULL AND student_number_key<>''"
        )
        self.connection.execute(
            "CREATE TRIGGER IF NOT EXISTS trg_students_student_number_key_insert "
            "AFTER INSERT ON students "
            "BEGIN "
            "UPDATE students SET student_number_key="
            "CASE WHEN NEW.student_number IS NULL OR TRIM(NEW.student_number)='' THEN NULL ELSE LOWER(TRIM(NEW.student_number)) END "
            "WHERE id=NEW.id; "
            "END"
        )
        self.connection.execute(
            "CREATE TRIGGER IF NOT EXISTS trg_students_student_number_key_update "
            "AFTER UPDATE OF student_number ON students "
            "BEGIN "
            "UPDATE students SET student_number_key="
            "CASE WHEN NEW.student_number IS NULL OR TRIM(NEW.student_number)='' THEN NULL ELSE LOWER(TRIM(NEW.student_number)) END "
            "WHERE id=NEW.id; "
            "END"
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_scores_attempt ON scores(attempt_id)"
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_attempts_test_student ON test_attempts(test_id, student_id)"
        )
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS test_students (
                test_id INTEGER NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (test_id, student_id)
            );
            CREATE INDEX IF NOT EXISTS idx_test_students_student ON test_students(student_id);
            """
        )
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS test_analysis_parts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(test_id, sort_order)
            );
            CREATE TABLE IF NOT EXISTS question_analysis_parts (
                question_id INTEGER PRIMARY KEY REFERENCES matrix_questions(id) ON DELETE CASCADE,
                part_id INTEGER REFERENCES test_analysis_parts(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS idx_test_analysis_parts_test ON test_analysis_parts(test_id);
            CREATE INDEX IF NOT EXISTS idx_question_analysis_parts_part ON question_analysis_parts(part_id);
            """
        )
        self._migrate_question_bank_schema()

    def _migrate_question_bank_schema(self) -> None:
        expected_columns = {
            "question_bank_items": [
                ("status", "status TEXT NOT NULL DEFAULT 'Actief'"),
                ("expected_time_minutes", "expected_time_minutes REAL"),
                ("created_at", "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
                ("updated_at", "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
            ],
            "question_bank_versions": [
                ("question_text", "question_text TEXT"),
                ("short_description", "short_description TEXT"),
                ("expected_time_minutes", "expected_time_minutes REAL"),
                ("is_multiple_choice", "is_multiple_choice INTEGER NOT NULL DEFAULT 0 CHECK (is_multiple_choice IN (0, 1))"),
                ("multiple_choice_answer", "multiple_choice_answer TEXT"),
                ("created_at", "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
                ("updated_at", "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
            ],
            "question_bank_subquestions": [
                ("question_text", "question_text TEXT"),
                ("short_description", "short_description TEXT"),
                ("expected_time_minutes", "expected_time_minutes REAL"),
                ("is_multiple_choice", "is_multiple_choice INTEGER NOT NULL DEFAULT 0 CHECK (is_multiple_choice IN (0, 1))"),
                ("multiple_choice_answer", "multiple_choice_answer TEXT"),
                ("sort_order", "sort_order INTEGER NOT NULL DEFAULT 0"),
            ],
        }
        for table, columns in expected_columns.items():
            existing = {
                row["name"] for row in self.connection.execute(f"PRAGMA table_info({table})").fetchall()
            }
            if not existing:
                continue
            for name, definition in columns:
                if name not in existing:
                    self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")
                    existing.add(name)

    def _seed_defaults(self) -> None:
        for name, values in STANDARD_TAXONOMIES.items():
            self.connection.execute(
                "INSERT OR IGNORE INTO taxonomy_definitions(name, is_standard) VALUES(?, 1)", (name,)
            )
            taxonomy_id = self.connection.execute(
                "SELECT id FROM taxonomy_definitions WHERE name = ?", (name,)
            ).fetchone()["id"]
            for order, value in enumerate(values):
                self.connection.execute(
                    "INSERT OR IGNORE INTO taxonomy_values(taxonomy_id, name, sort_order) VALUES(?, ?, ?)",
                    (taxonomy_id, value, order),
                )
        for name, field_type in DEFAULT_PROPERTIES:
            self.connection.execute(
                "INSERT OR IGNORE INTO property_definitions(name, field_type) VALUES(?, ?)",
                (name, field_type),
            )
        self._migrate_legacy_taxonomy_values()
        self._migrate_used_property_selections()

    def _migrate_legacy_taxonomy_values(self) -> None:
        legacy_property = self.connection.execute(
            "SELECT id FROM property_definitions WHERE name = 'Taxonomie'"
        ).fetchone()
        if not legacy_property:
            return
        rows = self.connection.execute(
            "SELECT question_id, value FROM question_property_values WHERE property_id = ? AND value LIKE '%: %'",
            (legacy_property["id"],),
        ).fetchall()
        for row in rows:
            taxonomy_name, value_name = row["value"].split(": ", 1)
            value = self.connection.execute(
                "SELECT d.id AS taxonomy_id, v.id AS value_id "
                "FROM taxonomy_definitions d JOIN taxonomy_values v ON v.taxonomy_id = d.id "
                "WHERE d.name = ? AND v.name = ?",
                (taxonomy_name, value_name),
            ).fetchone()
            if value:
                self.connection.execute(
                    "INSERT OR IGNORE INTO question_taxonomy_values(question_id, taxonomy_id, taxonomy_value_id) "
                    "VALUES(?, ?, ?)",
                    (row["question_id"], value["taxonomy_id"], value["value_id"]),
                )
                self.connection.execute(
                    "INSERT OR IGNORE INTO test_taxonomy_selections(test_id, taxonomy_id) "
                    "SELECT test_id, ? FROM matrix_questions WHERE id=?",
                    (value["taxonomy_id"], row["question_id"]),
                )
        self.connection.execute(
            "UPDATE property_definitions SET is_active=0 WHERE name='Taxonomie'"
        )

    def _migrate_used_property_selections(self) -> None:
        self.connection.execute(
            "INSERT OR IGNORE INTO test_property_selections(test_id, property_id) "
            "SELECT DISTINCT q.test_id, v.property_id FROM question_property_values v "
            "JOIN matrix_questions q ON q.id=v.question_id "
            "JOIN property_definitions p ON p.id=v.property_id WHERE p.is_active=1"
        )

    def execute(self, query: str, parameters: Iterable[Any] = ()) -> None:
        self.connection.execute(query, tuple(parameters))
        self.connection.commit()

    def rows(self, query: str, parameters: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return list(self.connection.execute(query, tuple(parameters)).fetchall())

    def scalar(self, query: str, parameters: Iterable[Any] = ()) -> Any:
        row = self.connection.execute(query, tuple(parameters)).fetchone()
        return row[0] if row else None

    def add_school_year(self, name: str, active: bool = False) -> None:
        if active:
            self.connection.execute("UPDATE school_years SET is_active = 0")
        self.execute(
            "INSERT OR IGNORE INTO school_years(name, is_active) VALUES(?, ?)",
            (name.strip(), int(active)),
        )
