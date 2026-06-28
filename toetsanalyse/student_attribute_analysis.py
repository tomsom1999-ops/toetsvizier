from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any

from .database import SubjectDatabase


ANALYSABLE_STUDENT_ATTRIBUTE_TYPES = {"keuzelijst", "ja/nee", "getal"}
MIN_STUDENTS_PER_ATTRIBUTE_GROUP = 3
GROUP_ATTRIBUTE_KEY = "__group__"
GRADE_BINS = [
    ("< 4,0", 1.0, 4.0),
    ("4,0 - 5,4", 4.0, 5.5),
    ("5,5 - 6,9", 5.5, 7.0),
    ("7,0 - 8,4", 7.0, 8.5),
    ("8,5 - 10", 8.5, 10.01),
]


def student_attribute_analysis_enabled(database: SubjectDatabase) -> bool:
    return database.meta("student_attribute_analysis_enabled", "0") == "1"


def analyzable_student_attributes(database: SubjectDatabase) -> list[Any]:
    return database.rows(
        "SELECT id, name, field_type, options_json FROM student_attributes "
        "WHERE field_type IN ('keuzelijst', 'ja/nee', 'getal') ORDER BY name"
    )


def is_group_attribute(attribute_id: int | str) -> bool:
    return str(attribute_id) == GROUP_ATTRIBUTE_KEY


def available_attribute_values(
    database: SubjectDatabase,
    attribute_id: int | str,
    year_id: int | None = None,
) -> list[str]:
    if is_group_attribute(attribute_id):
        conditions: list[str] = []
        parameters: list[object] = []
        if year_id is not None:
            conditions.append("school_year_id=?")
            parameters.append(year_id)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        rows = database.rows(
            "SELECT DISTINCT name FROM classes" + where + " ORDER BY name",
            parameters,
        )
        return [row["name"] for row in rows]
    conditions = ["v.attribute_id=?", "TRIM(COALESCE(v.value, ''))<>''"]
    parameters: list[object] = [attribute_id]
    joins = ""
    if year_id is not None:
        joins = "JOIN enrollments e ON e.student_id=v.student_id "
        conditions.append("e.school_year_id=?")
        parameters.append(year_id)
    rows = database.rows(
        "SELECT DISTINCT v.value FROM student_attribute_values v "
        + joins
        + "WHERE "
        + " AND ".join(conditions)
        + " ORDER BY v.value",
        parameters,
    )
    return [row["value"] for row in rows]


def available_attribute_dimensions(database: SubjectDatabase) -> list[dict[str, object]]:
    dimensions: list[dict[str, object]] = []
    for taxonomy in database.rows("SELECT id, name FROM taxonomy_definitions ORDER BY name"):
        dimensions.append(
            {
                "kind": "taxonomy",
                "id": int(taxonomy["id"]),
                "label": f"Taxonomie: {taxonomy['name']}",
            }
        )
    for definition in database.rows(
        "SELECT id, name FROM property_definitions WHERE is_active=1 ORDER BY name"
    ):
        dimensions.append(
            {
                "kind": "property",
                "id": int(definition["id"]),
                "label": str(definition["name"]),
            }
        )
    return dimensions


def _filter_sql(
    year_id: int | None,
    test_id: int | None,
    level: str | None,
    grade_year: str | None,
    class_id: int | None,
) -> tuple[str, list[object]]:
    conditions = ["a.status='gemaakt'", "a.total_score IS NOT NULL"]
    parameters: list[object] = []
    if year_id is not None:
        conditions.append("t.school_year_id=?")
        parameters.append(year_id)
    if test_id is not None:
        conditions.append("t.id=?")
        parameters.append(test_id)
    if level:
        conditions.append("t.level=?")
        parameters.append(level)
    if grade_year:
        conditions.append("t.grade_year=?")
        parameters.append(grade_year)
    if class_id is not None:
        conditions.append("e.class_id=?")
        parameters.append(class_id)
    return " AND ".join(conditions), parameters


def _mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def _attribute_grouping_sql(
    attribute_id: int | str,
    attribute_value: str | None = None,
) -> tuple[str, str, list[str], list[object]]:
    if is_group_attribute(attribute_id):
        joins = "JOIN classes ac ON ac.id=e.class_id"
        label_expression = "ac.name"
        conditions = ["TRIM(COALESCE(ac.name, ''))<>''"]
        parameters: list[object] = []
        if attribute_value:
            conditions.append("ac.name=?")
            parameters.append(attribute_value)
        return joins, label_expression, conditions, parameters
    joins = "JOIN student_attribute_values sav ON sav.student_id=s.id"
    label_expression = "sav.value"
    conditions = ["sav.attribute_id=?", "TRIM(COALESCE(sav.value, ''))<>''"]
    parameters = [attribute_id]
    if attribute_value:
        conditions.append("sav.value=?")
        parameters.append(attribute_value)
    return joins, label_expression, conditions, parameters


def student_attribute_summary(
    database: SubjectDatabase,
    *,
    attribute_id: int | str,
    year_id: int | None = None,
    test_id: int | None = None,
    level: str | None = None,
    grade_year: str | None = None,
    class_id: int | None = None,
    attribute_value: str | None = None,
    minimum_students: int = MIN_STUDENTS_PER_ATTRIBUTE_GROUP,
) -> dict[str, object]:
    filter_sql, filter_parameters = _filter_sql(year_id, test_id, level, grade_year, class_id)
    attribute_join, attribute_label, attribute_conditions, attribute_parameters = _attribute_grouping_sql(
        attribute_id, attribute_value
    )
    conditions = [
        filter_sql,
        *attribute_conditions,
        "mx.maximum_score > 0",
    ]
    parameters = [*filter_parameters, *attribute_parameters]
    rows = database.rows(
        f"""
        SELECT {attribute_label} AS attribute_value, a.student_id, a.total_score, a.grade,
               mx.maximum_score
        FROM test_attempts a
        JOIN tests t ON t.id=a.test_id
        JOIN students s ON s.id=a.student_id
        LEFT JOIN enrollments e ON e.student_id=s.id AND e.school_year_id=t.school_year_id
        {attribute_join}
        JOIN (
            SELECT test_id, SUM(maximum_score) AS maximum_score
            FROM matrix_questions GROUP BY test_id
        ) mx ON mx.test_id=t.id
        WHERE """
        + " AND ".join(conditions),
        parameters,
    )
    total_percentages = [
        float(row["total_score"]) / float(row["maximum_score"]) * 100
        for row in rows
        if row["maximum_score"]
    ]
    total_mean = _mean(total_percentages)
    groups: dict[str, dict[str, object]] = {}
    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        grouped[str(row["attribute_value"])].append(row)
    hidden_groups = 0
    for value, value_rows in grouped.items():
        student_ids = {int(row["student_id"]) for row in value_rows}
        if len(student_ids) < minimum_students:
            hidden_groups += 1
            continue
        percentages = [
            float(row["total_score"]) / float(row["maximum_score"]) * 100
            for row in value_rows
            if row["maximum_score"]
        ]
        grades = [float(row["grade"]) for row in value_rows if row["grade"] is not None]
        sufficient_grades = [grade for grade in grades if grade >= 5.5]
        mean_percentage = _mean(percentages)
        groups[value] = {
            "value": value,
            "students": len(student_ids),
            "attempts": len(value_rows),
            "mean_percentage": mean_percentage,
            "difference_from_total": (
                mean_percentage - total_mean
                if mean_percentage is not None and total_mean is not None
                else None
            ),
            "mean_grade": _mean(grades),
            "sufficient_percentage": (
                len(sufficient_grades) / len(grades) * 100 if grades else None
            ),
        }
    return {
        "rows": sorted(groups.values(), key=lambda row: str(row["value"]).lower()),
        "total_attempts": len(rows),
        "total_students": len({int(row["student_id"]) for row in rows}),
        "total_mean_percentage": total_mean,
        "hidden_groups": hidden_groups,
        "minimum_students": minimum_students,
    }


def _matching_class_id(database: SubjectDatabase, source_class_id: int | None, target_year_id: int | None) -> int | None:
    if source_class_id is None or target_year_id is None:
        return source_class_id
    class_name = database.scalar("SELECT name FROM classes WHERE id=?", (source_class_id,))
    if not class_name:
        return source_class_id
    target_id = database.scalar(
        "SELECT id FROM classes WHERE school_year_id=? AND name=? ORDER BY id LIMIT 1",
        (target_year_id, class_name),
    )
    return int(target_id) if target_id is not None else -1


def student_attribute_year_comparison(
    database: SubjectDatabase,
    *,
    attribute_id: int | str,
    base_year_id: int,
    comparison_year_id: int,
    level: str | None = None,
    grade_year: str | None = None,
    class_id: int | None = None,
    attribute_value: str | None = None,
    minimum_students: int = MIN_STUDENTS_PER_ATTRIBUTE_GROUP,
) -> dict[str, object]:
    base = student_attribute_summary(
        database,
        attribute_id=attribute_id,
        year_id=base_year_id,
        level=level,
        grade_year=grade_year,
        class_id=class_id,
        attribute_value=attribute_value,
        minimum_students=minimum_students,
    )
    comparison_class_id = _matching_class_id(database, class_id, comparison_year_id)
    comparison = student_attribute_summary(
        database,
        attribute_id=attribute_id,
        year_id=comparison_year_id,
        level=level,
        grade_year=grade_year,
        class_id=comparison_class_id,
        attribute_value=attribute_value,
        minimum_students=minimum_students,
    )
    base_rows = {str(row["value"]): row for row in base["rows"]}
    comparison_rows = {str(row["value"]): row for row in comparison["rows"]}
    values = sorted(set(base_rows) | set(comparison_rows), key=str.lower)
    rows: list[dict[str, object]] = []
    for value in values:
        base_row = base_rows.get(value)
        comparison_row = comparison_rows.get(value)
        base_percentage = base_row.get("mean_percentage") if base_row else None
        comparison_percentage = comparison_row.get("mean_percentage") if comparison_row else None
        rows.append(
            {
                "value": value,
                "base_students": base_row.get("students") if base_row else None,
                "base_attempts": base_row.get("attempts") if base_row else None,
                "base_mean_percentage": base_percentage,
                "comparison_students": comparison_row.get("students") if comparison_row else None,
                "comparison_attempts": comparison_row.get("attempts") if comparison_row else None,
                "comparison_mean_percentage": comparison_percentage,
                "difference": (
                    float(comparison_percentage) - float(base_percentage)
                    if comparison_percentage is not None and base_percentage is not None
                    else None
                ),
            }
        )
    return {
        "rows": rows,
        "base": base,
        "comparison": comparison,
        "hidden_groups": int(base["hidden_groups"]) + int(comparison["hidden_groups"]),
        "minimum_students": minimum_students,
        "comparison_class_matched": comparison_class_id != -1,
    }


def student_attribute_grade_distribution(
    database: SubjectDatabase,
    *,
    attribute_id: int | str,
    year_id: int | None = None,
    test_id: int | None = None,
    level: str | None = None,
    grade_year: str | None = None,
    class_id: int | None = None,
    attribute_value: str | None = None,
    minimum_students: int = MIN_STUDENTS_PER_ATTRIBUTE_GROUP,
) -> dict[str, object]:
    filter_sql, filter_parameters = _filter_sql(year_id, test_id, level, grade_year, class_id)
    attribute_join, attribute_label, attribute_conditions, attribute_parameters = _attribute_grouping_sql(
        attribute_id, attribute_value
    )
    conditions = [
        filter_sql,
        "a.grade IS NOT NULL",
        *attribute_conditions,
    ]
    parameters = [*filter_parameters, *attribute_parameters]
    rows = database.rows(
        f"""
        SELECT {attribute_label} AS attribute_value, a.student_id, a.grade
        FROM test_attempts a
        JOIN tests t ON t.id=a.test_id
        JOIN students s ON s.id=a.student_id
        LEFT JOIN enrollments e ON e.student_id=s.id AND e.school_year_id=t.school_year_id
        {attribute_join}
        WHERE """
        + " AND ".join(conditions),
        parameters,
    )
    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        grouped[str(row["attribute_value"])].append(row)
    visible_rows: list[dict[str, object]] = []
    hidden_groups = 0
    for value, value_rows in grouped.items():
        student_ids = {int(row["student_id"]) for row in value_rows}
        if len(student_ids) < minimum_students:
            hidden_groups += 1
            continue
        grades = [float(row["grade"]) for row in value_rows if row["grade"] is not None]
        bin_counts: list[int] = []
        for _, low, high in GRADE_BINS:
            bin_counts.append(sum(1 for grade in grades if low <= grade < high))
        visible_rows.append(
            {
                "value": value,
                "students": len(student_ids),
                "grades": len(grades),
                "bins": bin_counts,
                "mean_grade": _mean(grades),
            }
        )
    return {
        "bins": [label for label, _, _ in GRADE_BINS],
        "rows": sorted(visible_rows, key=lambda row: str(row["value"]).lower()),
        "hidden_groups": hidden_groups,
        "minimum_students": minimum_students,
    }


def student_attribute_dimension_summary(
    database: SubjectDatabase,
    *,
    attribute_id: int | str,
    dimension_kind: str,
    dimension_id: int,
    year_id: int | None = None,
    test_id: int | None = None,
    level: str | None = None,
    grade_year: str | None = None,
    class_id: int | None = None,
    attribute_value: str | None = None,
    minimum_students: int = MIN_STUDENTS_PER_ATTRIBUTE_GROUP,
) -> dict[str, object]:
    filter_sql, filter_parameters = _filter_sql(year_id, test_id, level, grade_year, class_id)
    join_parameters: list[object] = []
    attribute_join, attribute_label, attribute_conditions, attribute_parameters = _attribute_grouping_sql(
        attribute_id, attribute_value
    )
    joins = """
        JOIN scores sc ON sc.attempt_id=a.id AND sc.score IS NOT NULL
        JOIN matrix_questions q ON q.id=sc.question_id
    """
    label_expression = ""
    if dimension_kind == "taxonomy":
        joins += """
            JOIN question_taxonomy_values qtv
              ON qtv.question_id=q.id AND qtv.taxonomy_id=?
            JOIN taxonomy_values dv ON dv.id=qtv.taxonomy_value_id
        """
        label_expression = "dv.name"
        join_parameters.append(dimension_id)
    elif dimension_kind == "property":
        joins += """
            JOIN question_property_values qpv
              ON qpv.question_id=q.id AND qpv.property_id=?
        """
        label_expression = "qpv.value"
        join_parameters.append(dimension_id)
    else:
        raise ValueError("Onbekende analysesoort.")
    conditions = [
        filter_sql,
        *attribute_conditions,
        f"TRIM(COALESCE({label_expression}, ''))<>''",
    ]
    parameters = [*join_parameters, *filter_parameters, *attribute_parameters]
    rows = database.rows(
        f"""
        SELECT {attribute_label} AS attribute_value, {label_expression} AS dimension_value,
               a.student_id, sc.score, q.maximum_score
        FROM test_attempts a
        JOIN tests t ON t.id=a.test_id
        JOIN students s ON s.id=a.student_id
        LEFT JOIN enrollments e ON e.student_id=s.id AND e.school_year_id=t.school_year_id
        {attribute_join}
        {joins}
        WHERE """
        + " AND ".join(conditions),
        parameters,
    )
    grouped: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["attribute_value"]), str(row["dimension_value"]))].append(row)
    visible_rows: list[dict[str, object]] = []
    hidden_groups = 0
    for (value, dimension_value), value_rows in grouped.items():
        student_ids = {int(row["student_id"]) for row in value_rows}
        if len(student_ids) < minimum_students:
            hidden_groups += 1
            continue
        maximum = sum(float(row["maximum_score"] or 0) for row in value_rows)
        scored = sum(float(row["score"] or 0) for row in value_rows)
        visible_rows.append(
            {
                "value": value,
                "dimension": dimension_value,
                "students": len(student_ids),
                "score_count": len(value_rows),
                "mean_percentage": scored / maximum * 100 if maximum else None,
            }
        )
    return {
        "rows": sorted(
            visible_rows,
            key=lambda row: (str(row["value"]).lower(), str(row["dimension"]).lower()),
        ),
        "hidden_groups": hidden_groups,
        "minimum_students": minimum_students,
    }
