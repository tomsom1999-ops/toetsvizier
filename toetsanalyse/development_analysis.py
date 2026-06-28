from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Any

from .database import SubjectDatabase
from .name_sorting import student_sort_key
from .norming import calculate_grade, has_active_normalization, load_normalization, maximum_score


def development_analysis_enabled(database: SubjectDatabase) -> bool:
    return database.meta("development_analysis_enabled", "0") == "1"


def _average(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def _standard_deviation(values: list[float]) -> float | None:
    return statistics.pstdev(values) if len(values) > 1 else None


def _test_weight(test: dict[str, Any]) -> float:
    value = test.get("weight")
    return 1.0 if value is None else float(value)


def _safe_key(prefix: str, value: str) -> str:
    cleaned = "".join(character if character.isalnum() else "_" for character in value.casefold()).strip("_")
    return f"{prefix}_{cleaned or 'veld'}"


def _question_order(row: dict[str, Any]) -> tuple[int, str, str, int]:
    number = str(row.get("question_number") or "")
    try:
        numeric = int(number)
    except ValueError:
        numeric = 10_000
    return (numeric, number, str(row.get("subquestion") or ""), int(row.get("id") or 0))


def development_filter_options(database: SubjectDatabase) -> dict[str, list[dict[str, object]]]:
    return {
        "school_years": [
            {"id": row["id"], "name": row["name"]}
            for row in database.rows("SELECT id, name FROM school_years ORDER BY name DESC")
        ],
        "levels": [
            {"value": row["value"], "label": row["value"]}
            for row in database.rows(
                "SELECT DISTINCT COALESCE(level, '') AS value FROM tests WHERE COALESCE(level, '')<>'' ORDER BY value"
            )
        ],
        "grades": [
            {"value": row["value"], "label": row["value"]}
            for row in database.rows(
                "SELECT DISTINCT COALESCE(grade_year, '') AS value FROM tests "
                "WHERE COALESCE(grade_year, '')<>'' ORDER BY value"
            )
        ],
        "groups": [
            {"value": row["name"], "label": row["name"]}
            for row in database.rows("SELECT DISTINCT name FROM classes ORDER BY name")
        ],
    }


def development_test_options(
    database: SubjectDatabase,
    *,
    school_year_id: int | None = None,
    level: str | None = None,
    grade_year: str | None = None,
    group: str | None = None,
) -> list[dict[str, object]]:
    conditions = ["1=1"]
    parameters: list[object] = []
    if school_year_id is not None:
        conditions.append("t.school_year_id=?")
        parameters.append(school_year_id)
    if level:
        conditions.append("t.level=?")
        parameters.append(level)
    if grade_year:
        conditions.append("t.grade_year=?")
        parameters.append(grade_year)
    if group:
        conditions.append(
            "EXISTS (SELECT 1 FROM test_classes tc JOIN classes c ON c.id=tc.class_id "
            "WHERE tc.test_id=t.id AND c.name=?)"
        )
        parameters.append(group)
    return [
        {
            "id": int(row["id"]),
            "name": row["name"],
            "school_year": row["school_year"],
            "period": row["period"],
            "level": row["level"] or "",
            "grade_year": row["grade_year"] or "",
            "is_resit": bool(row["is_resit"]),
            "original_test_id": row["original_test_id"],
        }
        for row in database.rows(
            "SELECT t.id, t.name, sy.name AS school_year, t.period, t.level, t.grade_year, "
            "t.is_resit, t.original_test_id, t.test_date, t.created_at "
            "FROM tests t JOIN school_years sy ON sy.id=t.school_year_id "
            f"WHERE {' AND '.join(conditions)} ORDER BY sy.name DESC, COALESCE(t.test_date, t.created_at), t.id",
            tuple(parameters),
        )
    ]


def _questions_for_test(database: SubjectDatabase, test_id: int) -> list[dict[str, Any]]:
    questions = [
        dict(row)
        for row in database.rows(
            "SELECT id, question_number, subquestion, question_number || COALESCE(subquestion, '') AS label, "
            "maximum_score, short_description FROM matrix_questions WHERE test_id=?",
            (test_id,),
        )
    ]
    for question in questions:
        question["id"] = int(question["id"])
        question["maximum_score"] = float(question["maximum_score"])
    questions.sort(key=_question_order)
    return questions


def _dimensions_for_test(database: SubjectDatabase, test_id: int) -> dict[str, dict[str, object]]:
    dimensions: dict[str, dict[str, object]] = {}
    taxonomy_rows = database.rows(
        "SELECT d.name AS definition_name, qtv.question_id, tv.name AS value_name, tv.sort_order "
        "FROM question_taxonomy_values qtv "
        "JOIN taxonomy_definitions d ON d.id=qtv.taxonomy_id "
        "JOIN taxonomy_values tv ON tv.id=qtv.taxonomy_value_id "
        "JOIN matrix_questions q ON q.id=qtv.question_id WHERE q.test_id=? "
        "ORDER BY d.name, tv.sort_order, tv.name",
        (test_id,),
    )
    for row in taxonomy_rows:
        title = str(row["definition_name"])
        key = _safe_key("taxonomy", title)
        dimension = dimensions.setdefault(
            key,
            {
                "key": key,
                "title": f"Taxonomie {title}",
                "raw_title": title,
                "kind": "taxonomy",
                "mapping": {},
                "category_order": [],
            },
        )
        category = str(row["value_name"])
        dimension["mapping"][int(row["question_id"])] = category
        if category not in dimension["category_order"]:
            dimension["category_order"].append(category)

    property_rows = database.rows(
        "SELECT p.name AS definition_name, qpv.question_id, qpv.value "
        "FROM question_property_values qpv "
        "JOIN property_definitions p ON p.id=qpv.property_id "
        "JOIN matrix_questions q ON q.id=qpv.question_id "
        "WHERE q.test_id=? AND COALESCE(qpv.value, '')<>'' "
        "ORDER BY p.name, qpv.value",
        (test_id,),
    )
    has_taxonomy_dimensions = any(str(dimension.get("kind")) == "taxonomy" for dimension in dimensions.values())
    for row in property_rows:
        title = str(row["definition_name"])
        if has_taxonomy_dimensions and title.casefold() == "taxonomie":
            continue
        key = _safe_key("property", title)
        dimension = dimensions.setdefault(
            key,
            {
                "key": key,
                "title": title,
                "raw_title": title,
                "kind": "property",
                "mapping": {},
                "category_order": [],
            },
        )
        category = str(row["value"])
        dimension["mapping"][int(row["question_id"])] = category
        if category not in dimension["category_order"]:
            dimension["category_order"].append(category)
    return dimensions


def _student_groups(database: SubjectDatabase, student_id: int, school_year_id: int) -> list[str]:
    return [
        str(row["name"])
        for row in database.rows(
            "SELECT c.name FROM enrollments e JOIN classes c ON c.id=e.class_id "
            "WHERE e.student_id=? AND e.school_year_id=? ORDER BY c.name",
            (student_id, school_year_id),
        )
    ]


def _complete_attempts(database: SubjectDatabase, test_id: int, question_count: int) -> list[dict[str, Any]]:
    if question_count <= 0:
        return []
    attempts = [
        dict(row)
        for row in database.rows(
            "SELECT a.id, a.student_id, s.display_name, COALESCE(s.last_name, '') AS last_name, "
            "COALESCE(s.first_name, '') AS first_name, a.total_score "
            "FROM test_attempts a JOIN students s ON s.id=a.student_id "
            "WHERE a.test_id=? AND a.status='gemaakt' AND a.total_score IS NOT NULL "
            "AND (SELECT COUNT(*) FROM scores sc WHERE sc.attempt_id=a.id AND sc.score IS NOT NULL)=? "
            "ORDER BY s.display_name",
            (test_id, question_count),
        )
    ]
    attempts.sort(key=lambda attempt: student_sort_key(attempt["display_name"], attempt["first_name"], attempt["last_name"]))
    return attempts


def _scores_for_attempts(database: SubjectDatabase, attempt_ids: set[int]) -> dict[int, dict[int, float]]:
    if not attempt_ids:
        return {}
    placeholders = ",".join("?" for _ in attempt_ids)
    result: dict[int, dict[int, float]] = {attempt_id: {} for attempt_id in attempt_ids}
    for row in database.rows(
        f"SELECT attempt_id, question_id, score FROM scores WHERE attempt_id IN ({placeholders}) AND score IS NOT NULL",
        tuple(attempt_ids),
    ):
        result[int(row["attempt_id"])][int(row["question_id"])] = float(row["score"])
    return result


def _rank_context(value: float, values: list[float]) -> dict[str, int | None]:
    if not values:
        return {"rank": None, "rank_count": None, "rank_end": None, "tied_count": None, "percentile": None, "top_percentage": None}
    rank = 1 + sum(candidate > value and not math.isclose(candidate, value, rel_tol=0.0, abs_tol=1e-9) for candidate in values)
    tied_count = sum(math.isclose(candidate, value, rel_tol=0.0, abs_tol=1e-9) for candidate in values)
    percentile = round(sum(candidate < value and not math.isclose(candidate, value, rel_tol=0.0, abs_tol=1e-9) for candidate in values) / len(values) * 100)
    return {
        "rank": rank,
        "rank_count": len(values),
        "rank_end": rank + tied_count - 1,
        "tied_count": tied_count,
        "percentile": percentile,
        "top_percentage": max(1, math.ceil(rank / len(values) * 100)),
    }


def _format_delta(value: float | None) -> str:
    if value is None:
        return "-"
    sign = "+" if value >= 0 else ""
    return f"{sign}{round(value)}%"


def _trend_tone(value: float | None, threshold: float = 5.0) -> str:
    if value is None or abs(value) < threshold:
        return "amber"
    return "green" if value > 0 else "red"


def _trend_label(value: float | None, threshold: float = 5.0) -> str:
    if value is None:
        return "onvoldoende data"
    if abs(value) < threshold:
        return "stabiel"
    return "stijgend" if value > 0 else "dalend"


def _student_trend(tests: list[dict[str, Any]]) -> dict[str, float | None]:
    values = [float(test.get("score_percentage") or 0.0) for test in tests]
    percentiles = [
        float(test["percentile"])
        for test in tests
        if test.get("percentile") is not None
    ]
    if len(tests) < 2:
        return {
            "first": values[0] if values else None,
            "last": values[-1] if values else None,
            "delta": None,
            "recent_delta": None,
            "stability": _standard_deviation(values),
            "percentile_first": percentiles[0] if percentiles else None,
            "percentile_last": percentiles[-1] if percentiles else None,
            "percentile_delta": None,
        }
    first = values[0]
    last = values[-1]
    percentile_delta = (percentiles[-1] - percentiles[0]) if len(percentiles) >= 2 else None
    return {
        "first": first,
        "last": last,
        "delta": last - first,
        "recent_delta": values[-1] - values[-2],
        "stability": _standard_deviation(values),
        "percentile_first": percentiles[0] if percentiles else None,
        "percentile_last": percentiles[-1] if percentiles else None,
        "percentile_delta": percentile_delta,
    }


def _attendance_issues(
    database: SubjectDatabase,
    test_rows: list[dict[str, Any]],
    *,
    group: str | None = None,
) -> list[dict[str, object]]:
    if not test_rows:
        return []
    test_lookup = {int(test["id"]): test for test in test_rows}
    placeholders = ",".join("?" for _ in test_lookup)
    group_cache: dict[tuple[int, int], list[str]] = {}
    rows = database.rows(
        "SELECT a.test_id, a.student_id, a.status, s.display_name "
        "FROM test_attempts a JOIN students s ON s.id=a.student_id "
        f"WHERE a.test_id IN ({placeholders}) AND a.status NOT IN ('gemaakt', 'niet analyseren') "
        "ORDER BY s.display_name",
        tuple(test_lookup),
    )
    by_student: dict[int, dict[str, object]] = {}
    for row in rows:
        test = test_lookup.get(int(row["test_id"]))
        if not test:
            continue
        student_id = int(row["student_id"])
        if group:
            cache_key = (student_id, int(test["school_year_id"]))
            if cache_key not in group_cache:
                group_cache[cache_key] = _student_groups(database, student_id, int(test["school_year_id"]))
            if group not in group_cache[cache_key]:
                continue
        status = str(row["status"])
        item = by_student.setdefault(
            student_id,
            {
                "student_id": student_id,
                "student_name": str(row["display_name"]),
                "count": 0,
                "total_tests": len(test_rows),
                "statuses": defaultdict(int),
                "tests": [],
            },
        )
        item["count"] = int(item["count"]) + 1
        item["statuses"][status] += 1
        item["tests"].append(
            {
                "name": test["name"],
                "period": test["period"],
                "school_year": test["school_year"],
                "status": status,
            }
        )
    result = []
    for item in by_student.values():
        statuses = dict(item["statuses"])
        most_common_status = max(statuses.items(), key=lambda pair: pair[1])[0] if statuses else ""
        result.append(
            {
                "student_id": item["student_id"],
                "student_name": item["student_name"],
                "count": item["count"],
                "total_tests": item["total_tests"],
                "statuses": statuses,
                "most_common_status": most_common_status,
                "tests": item["tests"],
            }
        )
    result.sort(key=lambda item: (-int(item["count"]), str(item["student_name"]).casefold()))
    return result


def development_data(
    database: SubjectDatabase,
    *,
    school_year_id: int | None = None,
    level: str | None = None,
    grade_year: str | None = None,
    group: str | None = None,
    selected_test_ids: set[int] | None = None,
) -> dict[str, object]:
    conditions = ["1=1"]
    parameters: list[object] = []
    if school_year_id is not None:
        conditions.append("t.school_year_id=?")
        parameters.append(school_year_id)
    if level:
        conditions.append("t.level=?")
        parameters.append(level)
    if grade_year:
        conditions.append("t.grade_year=?")
        parameters.append(grade_year)
    test_rows = [
        dict(row)
        for row in database.rows(
            "SELECT t.id, t.school_year_id, sy.name AS school_year, t.name, t.level, t.grade_year, "
            "t.period, t.test_type, t.test_date, t.created_at, t.weight, t.is_resit, t.original_test_id "
            "FROM tests t JOIN school_years sy ON sy.id=t.school_year_id "
            f"WHERE {' AND '.join(conditions)} ORDER BY sy.name, COALESCE(t.test_date, t.created_at), t.id",
            tuple(parameters),
        )
    ]
    if selected_test_ids is not None:
        test_rows = [row for row in test_rows if int(row["id"]) in selected_test_ids]
    attendance_issues = _attendance_issues(database, test_rows, group=group)

    raw_records: list[dict[str, Any]] = []
    all_dimension_defs: dict[str, dict[str, object]] = {}
    resit_candidates: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    group_cache: dict[tuple[int, int], list[str]] = {}

    for test in test_rows:
        test_id = int(test["id"])
        questions = _questions_for_test(database, test_id)
        if not questions:
            continue
        dimensions = _dimensions_for_test(database, test_id)
        for key, dimension in dimensions.items():
            target = all_dimension_defs.setdefault(
                key,
                {
                    "key": key,
                    "title": dimension["title"],
                    "raw_title": dimension["raw_title"],
                    "kind": dimension["kind"],
                    "category_order": [],
                },
            )
            for category in dimension["category_order"]:
                if category not in target["category_order"]:
                    target["category_order"].append(category)

        attempts = _complete_attempts(database, test_id, len(questions))
        attempt_ids = {int(attempt["id"]) for attempt in attempts}
        score_maps = _scores_for_attempts(database, attempt_ids)
        test_maximum = maximum_score(database, test_id)
        finalized = has_active_normalization(database, test_id)
        settings = load_normalization(database, test_id)
        logical_test_id = int(test["original_test_id"] or test_id) if int(test["is_resit"] or 0) else test_id

        for attempt in attempts:
            student_id = int(attempt["student_id"])
            cache_key = (student_id, int(test["school_year_id"]))
            if cache_key not in group_cache:
                group_cache[cache_key] = _student_groups(database, student_id, int(test["school_year_id"]))
            groups = group_cache[cache_key]
            if group and group not in groups:
                continue
            total = float(attempt["total_score"])
            grade_value = calculate_grade(total, test_maximum, settings) if finalized and test_maximum else None
            score_percentage = total / test_maximum * 100 if test_maximum else 0.0
            record = {
                "attempt_id": int(attempt["id"]),
                "student_id": student_id,
                "student_name": str(attempt["display_name"]),
                "groups": groups,
                "test": test,
                "test_id": test_id,
                "logical_test_id": logical_test_id,
                "is_resit": bool(test["is_resit"]),
                "original_test_id": test["original_test_id"],
                "questions": questions,
                "dimensions": dimensions,
                "scores": score_maps.get(int(attempt["id"]), {}),
                "total_score": total,
                "maximum_score": test_maximum,
                "score_percentage": score_percentage,
                "normalization_finalized": finalized,
                "grade": grade_value,
                "selection_value": (grade_value * 10 if grade_value is not None else score_percentage),
            }
            raw_records.append(record)
            if bool(test["is_resit"]) and test["original_test_id"]:
                resit_candidates[(student_id, int(test["original_test_id"]))].append(record)
            elif any(int(candidate["original_test_id"] or 0) == test_id for candidate in test_rows):
                resit_candidates[(student_id, test_id)].append(record)

    best_records: dict[tuple[int, int], dict[str, Any]] = {}
    for record in raw_records:
        key = (int(record["student_id"]), int(record["logical_test_id"]))
        current = best_records.get(key)
        if current is None:
            best_records[key] = record
            continue
        if (
            float(record["selection_value"]) > float(current["selection_value"])
            or (
                math.isclose(float(record["selection_value"]), float(current["selection_value"]))
                and bool(record["is_resit"])
                and not bool(current["is_resit"])
            )
        ):
            best_records[key] = record
    selected_records = list(best_records.values())

    dimension_order = sorted(
        all_dimension_defs.values(),
        key=lambda dimension: (
            0 if str(dimension["raw_title"]).casefold() == "rtti" else 1,
            0 if dimension["kind"] == "taxonomy" else 1,
            str(dimension["title"]).casefold(),
        ),
    )
    x_lookup: dict[tuple[str, str], float] = {}
    axis_categories: list[dict[str, object]] = []
    dimension_blocks: list[dict[str, object]] = []
    x_position = 0.0
    for dimension in dimension_order:
        categories = list(dimension["category_order"])
        if str(dimension["raw_title"]).casefold() == "rtti":
            preferred = {"R": 0, "T1": 1, "T2": 2, "I": 3}
            categories.sort(key=lambda value: (preferred.get(str(value), 99), str(value).casefold()))
        else:
            categories.sort(key=lambda value: str(value).casefold())
        start = x_position
        for category in categories:
            key = (str(dimension["key"]), str(category))
            x_lookup[key] = x_position
            axis_categories.append(
                {
                    "x": x_position,
                    "dimension_key": dimension["key"],
                    "dimension_title": dimension["title"],
                    "category": category,
                    "label": str(category),
                }
            )
            x_position += 1.0
        if categories:
            dimension_blocks.append(
                {
                    "title": dimension["title"],
                    "start": start - 0.42,
                    "end": x_position - 0.58,
                    "center": (start + x_position - 1.0) / 2,
                }
            )
            x_position += 0.72

    student_buckets: dict[tuple[int, str, str], dict[str, Any]] = {}
    dimension_test_buckets: dict[tuple[str, str, int], dict[str, Any]] = {}
    student_dimension_test_buckets: dict[tuple[int, str, str, int], dict[str, Any]] = {}
    student_totals: dict[int, dict[str, Any]] = {}
    test_summaries: dict[int, dict[str, Any]] = {}
    for record in selected_records:
        student_id = int(record["student_id"])
        student_total = student_totals.setdefault(
            student_id,
            {
                "student_id": student_id,
                "name": record["student_name"],
                "achieved": 0.0,
                "possible": 0.0,
                "grades": [],
                "tests": [],
            },
        )
        student_total["achieved"] += float(record["total_score"])
        student_total["possible"] += float(record["maximum_score"])
        if record["grade"] is not None:
            student_total["grades"].append(float(record["grade"]))
        student_total["tests"].append(
            {
                "test_id": record["test_id"],
                "logical_test_id": record["logical_test_id"],
                "name": record["test"]["name"],
                "school_year": record["test"]["school_year"],
                "period": record["test"]["period"],
                "score_percentage": record["score_percentage"],
                "grade": record["grade"],
                "weight": _test_weight(record["test"]),
                "is_resit": record["is_resit"],
            }
        )
        summary = test_summaries.setdefault(
            int(record["logical_test_id"]),
            {
                "test_id": int(record["logical_test_id"]),
                "name": record["test"]["name"],
                "school_year": record["test"]["school_year"],
                "period": record["test"]["period"],
                "scores": [],
                "grades": [],
                "weight": _test_weight(record["test"]),
                "participant_count": 0,
            },
        )
        summary["scores"].append(float(record["score_percentage"]))
        if record["grade"] is not None:
            summary["grades"].append(float(record["grade"]))
        summary["participant_count"] += 1

        for question in record["questions"]:
            question_id = int(question["id"])
            score = float(record["scores"].get(question_id, 0.0))
            maximum = float(question["maximum_score"])
            for dimension_key, dimension in record["dimensions"].items():
                category = str(dimension["mapping"].get(question_id, "")).strip()
                if not category:
                    continue
                bucket_key = (student_id, dimension_key, category)
                bucket = student_buckets.setdefault(
                    bucket_key,
                    {
                        "student_id": student_id,
                        "student_name": record["student_name"],
                        "dimension_key": dimension_key,
                        "dimension_title": dimension["title"],
                        "category": category,
                        "achieved": 0.0,
                        "possible": 0.0,
                        "tests": set(),
                    },
                )
                bucket["achieved"] += score
                bucket["possible"] += maximum
                bucket["tests"].add(str(record["test"]["name"]))
                logical_test_id = int(record["logical_test_id"])
                trend_bucket = dimension_test_buckets.setdefault(
                    (dimension_key, category, logical_test_id),
                    {"achieved": 0.0, "possible": 0.0, "students": set()},
                )
                trend_bucket["achieved"] += score
                trend_bucket["possible"] += maximum
                trend_bucket["students"].add(student_id)
                student_trend_bucket = student_dimension_test_buckets.setdefault(
                    (student_id, dimension_key, category, logical_test_id),
                    {"achieved": 0.0, "possible": 0.0},
                )
                student_trend_bucket["achieved"] += score
                student_trend_bucket["possible"] += maximum

    profile_points = []
    for (student_id, dimension_key, category), bucket in student_buckets.items():
        possible = float(bucket["possible"])
        if possible <= 0:
            continue
        base_x = x_lookup.get((dimension_key, category))
        if base_x is None:
            continue
        jitter_seed = (student_id * 37 + int(base_x * 100) * 17) % 100
        jitter = (jitter_seed / 100 - 0.5) * 0.24
        percentage = float(bucket["achieved"]) / possible * 100
        profile_points.append(
            {
                "student_id": student_id,
                "student_name": bucket["student_name"],
                "dimension_key": dimension_key,
                "dimension_title": bucket["dimension_title"],
                "category": category,
                "x": base_x,
                "x_jitter": base_x + jitter,
                "percentage": percentage,
                "achieved": bucket["achieved"],
                "possible": possible,
                "test_count": len(bucket["tests"]),
                "sufficient": percentage >= 55,
            }
        )

    values_by_axis: dict[tuple[str, str], list[float]] = defaultdict(list)
    for point in profile_points:
        values_by_axis[(str(point["dimension_key"]), str(point["category"]))].append(float(point["percentage"]))
    for point in profile_points:
        point.update(_rank_context(float(point["percentage"]), values_by_axis[(str(point["dimension_key"]), str(point["category"]))]))

    test_contexts: dict[int, dict[str, float | None]] = {}
    test_score_values: dict[int, list[float]] = {}
    for test_id, summary in test_summaries.items():
        scores = [float(score) for score in summary["scores"]]
        grades = [float(grade) for grade in summary["grades"]]
        test_score_values[int(test_id)] = scores
        test_contexts[int(test_id)] = {
            "mean_score_percentage": _average(scores),
            "min_score_percentage": min(scores) if scores else None,
            "max_score_percentage": max(scores) if scores else None,
            "mean_grade": _average(grades),
        }

    students = []
    overall_percentages = [
        float(total["achieved"]) / float(total["possible"]) * 100
        for total in student_totals.values()
        if float(total["possible"]) > 0
    ]
    for total in sorted(
        student_totals.values(),
        key=lambda item: student_sort_key(str(item.get("name") or "")),
    ):
        possible = float(total["possible"])
        percentage = float(total["achieved"]) / possible * 100 if possible else 0.0
        tests = []
        for test in sorted(total["tests"], key=lambda item: (str(item["school_year"]), str(item["period"]), str(item["name"]))):
            logical_test_id = int(test.get("logical_test_id") or test.get("test_id") or 0)
            context = test_contexts.get(logical_test_id, {})
            score_percentage = float(test.get("score_percentage") or 0.0)
            rank_context = _rank_context(score_percentage, test_score_values.get(logical_test_id, []))
            group_mean = context.get("mean_score_percentage")
            tests.append(
                {
                    **test,
                    "group_mean_score_percentage": context.get("mean_score_percentage"),
                    "group_min_score_percentage": context.get("min_score_percentage"),
                    "group_max_score_percentage": context.get("max_score_percentage"),
                    "deviation_from_group": (score_percentage - float(group_mean)) if group_mean is not None else None,
                    **rank_context,
                }
            )
        trend = _student_trend(tests)
        students.append(
            {
                "id": total["student_id"],
                "name": total["name"],
                "score_percentage": percentage,
                "mean_grade": _average(total["grades"]),
                "test_count": len(total["tests"]),
                "tests": tests,
                "trend": trend,
                **_rank_context(percentage, overall_percentages),
            }
        )

    group_dimensions = []
    for dimension in dimension_order:
        entries = []
        for category in dimension["category_order"]:
            values = values_by_axis.get((str(dimension["key"]), str(category)), [])
            if values:
                entries.append({"name": category, "percentage": _average(values), "student_count": len(values)})
        if entries:
            entries.sort(key=lambda item: float(item["percentage"] or 0), reverse=True)
            group_dimensions.append({"key": dimension["key"], "title": dimension["title"], "entries": entries})

    resit_rows = []
    for (student_id, original_id), records in resit_candidates.items():
        original_records = [record for record in records if not bool(record["is_resit"]) and int(record["test_id"]) == original_id]
        resit_records = [record for record in records if bool(record["is_resit"])]
        if not original_records or not resit_records:
            continue
        original = max(original_records, key=lambda record: float(record["selection_value"]))
        resit = max(resit_records, key=lambda record: float(record["selection_value"]))
        resit_rows.append(
            {
                "student_id": student_id,
                "student_name": original["student_name"],
                "original_test": original["test"]["name"],
                "resit_test": resit["test"]["name"],
                "original_percentage": original["score_percentage"],
                "resit_percentage": resit["score_percentage"],
                "delta_percentage": resit["score_percentage"] - original["score_percentage"],
                "original_grade": original["grade"],
                "resit_grade": resit["grade"],
                "delta_grade": (resit["grade"] - original["grade"]) if resit["grade"] is not None and original["grade"] is not None else None,
            }
        )
    resit_rows.sort(key=lambda row: float(row["delta_percentage"]), reverse=True)

    test_summary_rows = []
    for summary in sorted(test_summaries.values(), key=lambda item: (str(item["school_year"]), str(item["period"]), str(item["name"]))):
        context = test_contexts.get(int(summary["test_id"]), {})
        test_summary_rows.append(
            {
                "test_id": summary["test_id"],
                "name": summary["name"],
                "school_year": summary["school_year"],
                "period": summary["period"],
                "mean_score_percentage": context.get("mean_score_percentage"),
                "min_score_percentage": context.get("min_score_percentage"),
                "max_score_percentage": context.get("max_score_percentage"),
                "mean_grade": context.get("mean_grade"),
                "weight": summary.get("weight", 1),
                "participant_count": summary["participant_count"],
            }
        )

    group_trend_values = [
        float(test["mean_score_percentage"])
        for test in test_summary_rows
        if test.get("mean_score_percentage") is not None
    ]
    group_spreads = [
        float(test["max_score_percentage"]) - float(test["min_score_percentage"])
        for test in test_summary_rows
        if test.get("max_score_percentage") is not None and test.get("min_score_percentage") is not None
    ]
    group_delta = (group_trend_values[-1] - group_trend_values[0]) if len(group_trend_values) >= 2 else None
    group_recent_delta = (group_trend_values[-1] - group_trend_values[-2]) if len(group_trend_values) >= 2 else None
    spread_delta = (group_spreads[-1] - group_spreads[0]) if len(group_spreads) >= 2 else None
    group_trend = {
        "first": group_trend_values[0] if group_trend_values else None,
        "last": group_trend_values[-1] if group_trend_values else None,
        "delta": group_delta,
        "recent_delta": group_recent_delta,
        "stability": _standard_deviation(group_trend_values),
        "spread_first": group_spreads[0] if group_spreads else None,
        "spread_last": group_spreads[-1] if group_spreads else None,
        "spread_delta": spread_delta,
        "label": _trend_label(group_delta),
        "tone": _trend_tone(group_delta),
    }

    def sorted_categories_for_dimension(dimension: dict[str, object]) -> list[str]:
        categories = [str(category) for category in dimension["category_order"]]
        if str(dimension["raw_title"]).casefold() == "rtti":
            preferred = {"R": 0, "T1": 1, "T2": 2, "I": 3}
            categories.sort(key=lambda value: (preferred.get(value, 99), value.casefold()))
        else:
            categories.sort(key=lambda value: value.casefold())
        return categories

    dimension_trends = []
    for dimension in dimension_order:
        entries = []
        for category in sorted_categories_for_dimension(dimension):
            series = []
            values = []
            for test in test_summary_rows:
                bucket = dimension_test_buckets.get((str(dimension["key"]), category, int(test["test_id"])))
                percentage = None
                student_count = 0
                if bucket and float(bucket["possible"]) > 0:
                    percentage = float(bucket["achieved"]) / float(bucket["possible"]) * 100
                    values.append(percentage)
                    student_count = len(bucket["students"])
                series.append(
                    {
                        "test_id": test["test_id"],
                        "test_name": test["name"],
                        "period": test["period"],
                        "school_year": test["school_year"],
                        "percentage": percentage,
                        "student_count": student_count,
                    }
                )
            if values:
                delta = values[-1] - values[0] if len(values) >= 2 else None
                recent_delta = values[-1] - values[-2] if len(values) >= 2 else None
                entries.append(
                    {
                        "name": category,
                        "series": series,
                        "first": values[0],
                        "last": values[-1],
                        "delta": delta,
                        "recent_delta": recent_delta,
                        "stability": _standard_deviation(values),
                        "label": _trend_label(delta),
                        "tone": _trend_tone(delta),
                    }
                )
        if entries:
            dimension_trends.append(
                {
                    "key": dimension["key"],
                    "title": dimension["title"],
                    "entries": entries,
                }
            )

    for student in students:
        student_id = int(student["id"])
        student_dimension_trends = []
        for dimension in dimension_order:
            entries = []
            for category in sorted_categories_for_dimension(dimension):
                series = []
                values = []
                for test in test_summary_rows:
                    bucket = student_dimension_test_buckets.get(
                        (student_id, str(dimension["key"]), category, int(test["test_id"]))
                    )
                    percentage = None
                    if bucket and float(bucket["possible"]) > 0:
                        percentage = float(bucket["achieved"]) / float(bucket["possible"]) * 100
                        values.append(percentage)
                    series.append(
                        {
                            "test_id": test["test_id"],
                            "test_name": test["name"],
                            "period": test["period"],
                            "school_year": test["school_year"],
                            "percentage": percentage,
                        }
                    )
                if values:
                    delta = values[-1] - values[0] if len(values) >= 2 else None
                    recent_delta = values[-1] - values[-2] if len(values) >= 2 else None
                    entries.append(
                        {
                            "name": category,
                            "series": series,
                            "first": values[0],
                            "last": values[-1],
                            "delta": delta,
                            "recent_delta": recent_delta,
                            "stability": _standard_deviation(values),
                            "label": _trend_label(delta),
                            "tone": _trend_tone(delta),
                        }
                    )
            if entries:
                student_dimension_trends.append(
                    {
                        "key": dimension["key"],
                        "title": dimension["title"],
                        "entries": entries,
                    }
                )
        student["dimension_trends"] = student_dimension_trends

    overview_cards: list[dict[str, object]] = []
    if group_trend_values:
        overview_cards.append(
            {
                "title": "Groepstrend",
                "value": _format_delta(group_trend["delta"]),
                "detail": f"{group_trend['label']} over {len(group_trend_values)} toets(en).",
                "tone": group_trend["tone"],
            }
        )
        overview_cards.append(
            {
                "title": "Recente ontwikkeling",
                "value": _format_delta(group_trend["recent_delta"]),
                "detail": "Verschil tussen vorige en huidige toets.",
                "tone": _trend_tone(group_trend["recent_delta"]),
            }
        )
        if group_trend["spread_delta"] is not None:
            overview_cards.append(
                {
                    "title": "Verschillen in de groep",
                    "value": _format_delta(group_trend["spread_delta"]),
                    "detail": "Wordt het verschil tussen leerlingen groter of kleiner?",
                    "tone": "red" if float(group_trend["spread_delta"]) > 8 else "green",
                }
            )
    students_with_trend = [
        student for student in students
        if isinstance(student.get("trend"), dict) and student["trend"].get("delta") is not None
    ]
    if students_with_trend:
        strongest = max(students_with_trend, key=lambda student: float(student["trend"]["delta"]))
        weakest = min(students_with_trend, key=lambda student: float(student["trend"]["delta"]))
        overview_cards.append(
            {
                "title": "Sterkste ontwikkeling",
                "value": _format_delta(float(strongest["trend"]["delta"])),
                "detail": "Grootste stijging over alle gekozen toetsen.",
                "tone": "green" if float(strongest["trend"]["delta"]) >= 0 else "amber",
            }
        )
        overview_cards.append(
            {
                "title": "Grootste terugval",
                "value": _format_delta(float(weakest["trend"]["delta"])),
                "detail": "Grootste daling over alle gekozen toetsen.",
                "tone": "red" if float(weakest["trend"]["delta"]) < 0 else "green",
            }
        )

    all_dimension_entries = [
        {"dimension": dimension["title"], **entry}
        for dimension in group_dimensions
        for entry in dimension.get("entries", [])
        if entry.get("percentage") is not None
    ]
    if all_dimension_entries:
        strongest_entry = max(all_dimension_entries, key=lambda entry: float(entry.get("percentage") or 0))
        weakest_entry = min(all_dimension_entries, key=lambda entry: float(entry.get("percentage") or 0))
        overview_cards.append(
            {
                "title": "Sterkste onderdeel",
                "value": strongest_entry["name"],
                "detail": f"{strongest_entry['dimension']} · {round(float(strongest_entry.get('percentage') or 0))}%",
                "tone": "green",
            }
        )
        overview_cards.append(
            {
                "title": "Aandachtspunt groep",
                "value": weakest_entry["name"],
                "detail": f"{weakest_entry['dimension']} · {round(float(weakest_entry.get('percentage') or 0))}%",
                "tone": "red" if float(weakest_entry.get("percentage") or 0) < 55 else "amber",
            }
        )

    if resit_rows:
        overview_cards.append(
            {
                "title": "Herkansingen",
                "value": f"{sum(1 for row in resit_rows if float(row['delta_percentage']) > 0)} verbeterd",
                "detail": f"Gemiddeld {_format_delta(_average([float(row['delta_percentage']) for row in resit_rows]))}",
                "tone": "green",
            }
        )

    if test_summary_rows:
        lowest_test = min(test_summary_rows, key=lambda item: float(item.get("mean_score_percentage") or 0))
        overview_cards.append(
            {
                "title": "Laagste toetsgemiddelde",
                "value": lowest_test["name"],
                "detail": f"{round(float(lowest_test.get('mean_score_percentage') or 0))}% gemiddeld",
                "tone": "amber" if float(lowest_test.get("mean_score_percentage") or 0) >= 55 else "red",
            }
        )

    student_signals: list[dict[str, object]] = []
    group_signals: list[dict[str, object]] = []
    positive_students = sorted(
        students_with_trend,
        key=lambda item: float(item["trend"]["delta"]),
        reverse=True,
    )
    for student in positive_students[:4]:
        delta = float(student["trend"]["delta"])
        if delta >= 10:
            student_signals.append(
                {
                    "title": "Sterke vooruitgang",
                    "subject": student["name"],
                    "detail": f"{_format_delta(delta)} over alle gekozen toetsen.",
                    "tone": "green",
                }
            )
    recent_positive_students = sorted(
        [
            student for student in students_with_trend
            if student["trend"].get("recent_delta") is not None
        ],
        key=lambda item: float(item["trend"]["recent_delta"]),
        reverse=True,
    )
    for student in recent_positive_students[:3]:
        recent_delta = float(student["trend"]["recent_delta"])
        if recent_delta >= 10:
            student_signals.append(
                {
                    "title": "Recente vooruitgang",
                    "subject": student["name"],
                    "detail": f"{_format_delta(recent_delta)} tussen vorige en huidige toets.",
                    "tone": "green",
                }
            )
    position_positive_students = sorted(
        [
            student for student in students_with_trend
            if student["trend"].get("percentile_delta") is not None
        ],
        key=lambda item: float(item["trend"]["percentile_delta"]),
        reverse=True,
    )
    for student in position_positive_students[:3]:
        percentile_delta = float(student["trend"]["percentile_delta"])
        if percentile_delta >= 15:
            student_signals.append(
                {
                    "title": "Positie in groep stijgt",
                    "subject": student["name"],
                    "detail": f"{_format_delta(percentile_delta)} hoger ten opzichte van klasgenoten.",
                    "tone": "green",
                }
            )
    for student in sorted(students, key=lambda item: float(item.get("score_percentage") or 0))[:5]:
        if float(student.get("score_percentage") or 0) < 55:
            student_signals.append(
                {
                    "title": "Leerling onder 55%",
                    "subject": student["name"],
                    "detail": f"Totaal {round(float(student.get('score_percentage') or 0))}% van de punten over {student.get('test_count')} toets(en).",
                    "tone": "red",
                }
            )
    for student in sorted(students_with_trend, key=lambda item: float(item["trend"]["delta"]))[:5]:
        delta = float(student["trend"]["delta"])
        if delta <= -10:
            student_signals.append(
                {
                    "title": "Dalende lijn",
                    "subject": student["name"],
                    "detail": f"{_format_delta(delta)} over alle gekozen toetsen.",
                    "tone": "amber" if delta > -20 else "red",
                }
            )
    for student in students_with_trend:
        trend = student["trend"]
        recent_delta = trend.get("recent_delta")
        if recent_delta is not None and float(recent_delta) <= -10:
            student_signals.append(
                {
                    "title": "Recente terugval",
                    "subject": student["name"],
                    "detail": f"{_format_delta(float(recent_delta))} tussen vorige en huidige toets.",
                    "tone": "amber" if float(recent_delta) > -20 else "red",
                }
            )
        stability = trend.get("stability")
        if stability is not None and float(stability) >= 15:
            student_signals.append(
                {
                    "title": "Wisselende prestaties",
                    "subject": student["name"],
                    "detail": f"Resultaten wisselen ongeveer {round(float(stability))} punten op de 0-100 schaal tussen toetsen.",
                    "tone": "amber",
                }
            )
        percentile_delta = trend.get("percentile_delta")
        if percentile_delta is not None and float(percentile_delta) <= -15:
            student_signals.append(
                {
                    "title": "Positie in de groep zakt",
                    "subject": student["name"],
                    "detail": f"{_format_delta(float(percentile_delta))} lager ten opzichte van klasgenoten.",
                    "tone": "amber" if float(percentile_delta) > -25 else "red",
                }
            )

    if group_trend["delta"] is not None and float(group_trend["delta"]) >= 5:
        group_signals.append(
            {
                "title": "Stijgende groepstrend",
                "subject": "Gemiddelde score",
                "detail": f"{_format_delta(float(group_trend['delta']))} over alle gekozen toetsen.",
                "tone": "green",
            }
        )
    if group_trend["delta"] is not None and float(group_trend["delta"]) <= -5:
        group_signals.append(
            {
                "title": "Dalende groepstrend",
                "subject": "Gemiddelde score",
                "detail": f"{_format_delta(float(group_trend['delta']))} over alle gekozen toetsen.",
                "tone": "amber" if float(group_trend["delta"]) > -12 else "red",
            }
        )
    if group_trend["spread_delta"] is not None and float(group_trend["spread_delta"]) <= -8:
        group_signals.append(
            {
                "title": "Groep groeit naar elkaar toe",
                "subject": "Groepsverschillen",
                "detail": f"{abs(round(float(group_trend['spread_delta'])))} punten minder verschil tussen hoogste en laagste score.",
                "tone": "green",
            }
        )
    if group_trend["spread_delta"] is not None and float(group_trend["spread_delta"]) >= 8:
        group_signals.append(
            {
                "title": "Verschillen nemen toe",
                "subject": "Groepsverschillen",
                "detail": f"{_format_delta(float(group_trend['spread_delta']))} meer verschil tussen hoogste en laagste score.",
                "tone": "amber",
            }
        )
    for item in attendance_issues[:5]:
        if int(item["count"]) >= 2:
            student_signals.append(
                {
                    "title": "Vaak niet meegedaan",
                    "subject": item["student_name"],
                    "detail": f"{item['count']} keer niet gemaakt of afwezig in deze selectie.",
                    "tone": "amber",
                }
            )
    for entry in sorted(all_dimension_entries, key=lambda item: float(item.get("percentage") or 0))[:8]:
        percentage = float(entry.get("percentage") or 0)
        if percentage < 55:
            group_signals.append(
                {
                    "title": "Zwak onderdeel",
                    "subject": f"{entry['dimension']}: {entry['name']}",
                    "detail": f"Groepsgemiddelde {round(percentage)}% van de punten.",
                    "tone": "amber" if percentage >= 45 else "red",
                }
            )
    for dimension in dimension_trends:
        rising_entries = sorted(
            [
                entry for entry in dimension.get("entries", [])
                if entry.get("delta") is not None and float(entry.get("delta") or 0) >= 8
            ],
            key=lambda item: float(item.get("delta") or 0),
            reverse=True,
        )
        for entry in rising_entries[:3]:
            group_signals.append(
                {
                    "title": "Stijgend onderdeel",
                    "subject": f"{dimension['title']}: {entry['name']}",
                    "detail": f"{_format_delta(float(entry['delta']))} over alle gekozen toetsen.",
                    "tone": "green",
                }
            )
        for entry in dimension.get("entries", []):
            delta = entry.get("delta")
            if delta is not None and float(delta) <= -8:
                group_signals.append(
                    {
                        "title": "Dalend onderdeel",
                        "subject": f"{dimension['title']}: {entry['name']}",
                        "detail": f"{_format_delta(float(delta))} over alle gekozen toetsen.",
                        "tone": "amber" if float(delta) > -15 else "red",
                    }
                )
    if not student_signals and selected_records:
        student_signals.append(
            {
                "title": "Geen duidelijke leerlingrisico's",
                "subject": "Leerlingen stabiel",
                "detail": "Er zijn geen leerlingen gevonden die onder de ingestelde signaleringsgrenzen vallen.",
                "tone": "green",
            }
        )
    if not group_signals and selected_records:
        group_signals.append(
            {
                "title": "Geen duidelijke groepsrisico's",
                "subject": "Onderdelen stabiel",
                "detail": "Er zijn geen onderdelen of groepsontwikkelingen gevonden die onder de signaleringsgrenzen vallen.",
                "tone": "green",
            }
        )
    signals = (student_signals[:8] + group_signals[:8])[:14]

    return {
        "filters": {
            "school_year_id": school_year_id,
            "level": level,
            "grade_year": grade_year,
            "group": group,
        },
        "summary": {
            "student_count": len(students),
            "test_count": len({int(record["logical_test_id"]) for record in selected_records}),
            "record_count": len(selected_records),
            "dimension_count": len(group_dimensions),
            "profile_point_count": len(profile_points),
            "mean_score_percentage": _average(overall_percentages),
            "mean_grade": _average([float(student["mean_grade"]) for student in students if student["mean_grade"] is not None]),
            "resit_count": len(resit_rows),
        },
        "overview": overview_cards,
        "signals": signals,
        "student_signals": student_signals[:12],
        "group_signals": group_signals[:12],
        "group_trend": group_trend,
        "dimension_trends": dimension_trends,
        "students": students,
        "profile_chart": {
            "categories": axis_categories,
            "dimension_blocks": dimension_blocks,
            "points": profile_points,
        },
        "group_dimensions": group_dimensions,
        "test_summaries": test_summary_rows,
        "attendance_issues": attendance_issues,
        "resits": {
            "rows": resit_rows,
            "improved_count": sum(1 for row in resit_rows if float(row["delta_percentage"]) > 0),
            "mean_delta_percentage": _average([float(row["delta_percentage"]) for row in resit_rows]),
            "mean_delta_grade": _average([float(row["delta_grade"]) for row in resit_rows if row["delta_grade"] is not None]),
        },
    }
