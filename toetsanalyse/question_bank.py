from __future__ import annotations

import sqlite3

from .database import SubjectDatabase


QUESTION_BANK_STATUSES = ["Concept", "Actief", "Gearchiveerd", "Niet meer gebruiken"]


def question_database_enabled(database: SubjectDatabase) -> bool:
    return database.meta("question_database_enabled", "0") == "1"


def load_all_taxonomies(database: SubjectDatabase) -> list[dict]:
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "values": database.rows(
                "SELECT id, name FROM taxonomy_values WHERE taxonomy_id=? ORDER BY sort_order, id",
                (row["id"],),
            ),
        }
        for row in database.rows("SELECT id, name FROM taxonomy_definitions ORDER BY id")
    ]


def load_active_question_properties(database: SubjectDatabase) -> list[dict]:
    return [
        dict(row)
        for row in database.rows(
            "SELECT id, name, field_type, choices_json FROM property_definitions "
            "WHERE is_active=1 ORDER BY id"
        )
    ]


def question_database_latest_rows(database: SubjectDatabase) -> list[sqlite3.Row]:
    return database.rows(
        """
        SELECT i.id AS item_id, v.id AS version_id, v.version_number, v.title, v.question_text,
               v.short_description, COALESCE(i.status, 'Actief') AS status,
               v.maximum_score, v.is_multiple_choice,
               COALESCE(s.subquestion_count, 0) AS subquestion_count,
               COALESCE(u.usage_count, 0) AS usage_count,
               COALESCE(u.usage_description_summary, '') AS usage_description_summary,
               COALESCE(ts.taxonomy_summary, '') AS taxonomy_summary,
               COALESCE(ps.property_summary, '') AS property_summary,
               COALESCE(tf.taxonomy_filters, '') AS taxonomy_filters,
               COALESCE(pf.property_filters, '') AS property_filters
        FROM question_bank_items i
        JOIN question_bank_versions v ON v.item_id=i.id
        LEFT JOIN (
            SELECT version_id, COUNT(*) AS subquestion_count
            FROM question_bank_subquestions GROUP BY version_id
        ) s ON s.version_id=v.id
        LEFT JOIN (
            SELECT question_bank_id AS item_id, COUNT(DISTINCT test_id) AS usage_count,
                   GROUP_CONCAT(DISTINCT NULLIF(TRIM(short_description), '')) AS usage_description_summary
            FROM matrix_questions
            WHERE question_bank_id IS NOT NULL
            GROUP BY question_bank_id
        ) u ON u.item_id=i.id
        LEFT JOIN (
            SELECT qbtv.version_id, GROUP_CONCAT(td.name || ': ' || tv.name, ', ') AS taxonomy_summary
            FROM question_bank_version_taxonomy_values qbtv
            JOIN taxonomy_definitions td ON td.id=qbtv.taxonomy_id
            JOIN taxonomy_values tv ON tv.id=qbtv.taxonomy_value_id
            GROUP BY qbtv.version_id
        ) ts ON ts.version_id=v.id
        LEFT JOIN (
            SELECT qbpv.version_id, GROUP_CONCAT(pd.name || ': ' || qbpv.value, ', ') AS property_summary
            FROM question_bank_version_property_values qbpv
            JOIN property_definitions pd ON pd.id=qbpv.property_id
            WHERE TRIM(COALESCE(qbpv.value, '')) <> ''
            GROUP BY qbpv.version_id
        ) ps ON ps.version_id=v.id
        LEFT JOIN (
            SELECT version_id, GROUP_CONCAT(taxonomy_id || '=' || taxonomy_value_id, '|') AS taxonomy_filters
            FROM question_bank_version_taxonomy_values GROUP BY version_id
        ) tf ON tf.version_id=v.id
        LEFT JOIN (
            SELECT version_id, GROUP_CONCAT(property_id || '=' || LOWER(TRIM(value)), '|') AS property_filters
            FROM question_bank_version_property_values
            WHERE TRIM(COALESCE(value, '')) <> ''
            GROUP BY version_id
        ) pf ON pf.version_id=v.id
        WHERE v.version_number=(
            SELECT MAX(v2.version_number) FROM question_bank_versions v2 WHERE v2.item_id=i.id
        )
        ORDER BY LOWER(v.title), i.id
        """
    )


def question_database_distinct_property_values(database: SubjectDatabase, property_id: int) -> list[str]:
    return [
        str(row["value"])
        for row in database.rows(
            "SELECT DISTINCT value FROM question_bank_version_property_values "
            "WHERE property_id=? AND TRIM(COALESCE(value, '')) <> '' ORDER BY LOWER(value)",
            (property_id,),
        )
    ]
