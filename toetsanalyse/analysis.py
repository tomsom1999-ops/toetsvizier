from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Any

from .database import SubjectDatabase
from .name_sorting import student_sort_key
from .norming import calculate_grade, has_active_normalization, load_normalization, maximum_score
from .results import QUESTION_ORDER_SQL, is_not_made_score, normalize_multiple_choice_option_list, normalize_multiple_choice_response


MIN_RELIABLE_ANALYSIS_PARTICIPANTS = 5


def _average(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def _mode(values: list[float]) -> tuple[float | None, int]:
    if not values:
        return None, 0
    modes = statistics.multimode(values)
    if not modes or len(modes) == len(values):
        return None, 0
    mode_value = float(modes[0])
    return mode_value, values.count(mode_value)


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2 or len(left) != len(right):
        return None
    mean_left = statistics.mean(left)
    mean_right = statistics.mean(right)
    numerator = sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right))
    denominator = math.sqrt(
        sum((a - mean_left) ** 2 for a in left)
        * sum((b - mean_right) ** 2 for b in right)
    )
    if math.isclose(denominator, 0.0):
        return None
    return numerator / denominator


def _cronbach(matrix: list[list[float]]) -> float | None:
    if len(matrix) < 2 or not matrix or len(matrix[0]) < 2:
        return None
    totals = [sum(row) for row in matrix]
    total_variance = statistics.variance(totals)
    if math.isclose(total_variance, 0.0):
        return None
    item_count = len(matrix[0])
    item_variance = sum(statistics.variance([row[index] for row in matrix]) for index in range(item_count))
    return item_count / (item_count - 1) * (1 - item_variance / total_variance)


def _status(level: str, label: str, advice: str, range_label: str) -> dict[str, str]:
    return {"level": level, "label": label, "advice": advice, "range": range_label}


def _metric_status(kind: str, value: float | None) -> dict[str, str]:
    if value is None:
        return _status("neutral", "Geen data", "Meer complete resultaten nodig.", "-")
    if kind == "p":
        if value < 0.20:
            return _status("bad", "Zeer moeilijk", "Controleer vraag en normering.", "< 0,20")
        if value < 0.30:
            return _status("attention", "Moeilijk", "Passend voor uitdaging.", "0,20 - 0,30")
        if value <= 0.80:
            return _status("good", "Goed", "Geen actie nodig.", "0,30 - 0,80")
        if value <= 0.90:
            return _status("attention", "Makkelijk", "Overweeg meer uitdaging.", "0,80 - 0,90")
        return _status("bad", "Zeer makkelijk", "Voegt weinig onderscheid toe.", "> 0,90")
    if kind == "rit":
        if value < 0:
            return _status("bad", "Ernstig probleem", "Controleer of scoring en vraagstelling kloppen.", "< 0,00")
        if value < 0.20:
            return _status("bad", "Zwak", "Deze vraag maakt nog weinig onderscheid in totaalscores.", "0,00 - 0,20")
        if value < 0.30:
            return _status("attention", "Redelijk", "Mogelijke verbetering.", "0,20 - 0,30")
        if value < 0.40:
            return _status("good", "Goed", "Geen actie nodig.", "0,30 - 0,40")
        if value <= 0.60:
            return _status("good", "Zeer goed", "Sterke vraag.", "0,40 - 0,60")
        return _status("excellent", "Uitstekend", "Behouden als voorbeeldvraag.", "> 0,60")
    if kind == "rir":
        if value < 0:
            return _status("bad", "Ernstig probleem", "Controleer of scoring en vraagstelling kloppen.", "< 0,00")
        if value < 0.10:
            return _status("bad", "Zwak", "Deze vraag sluit nog zwak aan op de rest van de toets.", "0,00 - 0,10")
        if value < 0.20:
            return _status("attention", "Acceptabel", "Mogelijk verbeteren.", "0,10 - 0,20")
        if value < 0.30:
            return _status("attention", "Redelijk", "Geen directe actie nodig.", "0,20 - 0,30")
        if value <= 0.50:
            return _status("good", "Goed", "Goede onderscheidende vraag.", "0,30 - 0,50")
        return _status("excellent", "Uitstekend", "Zeer sterke vraag.", "> 0,50")
    if kind == "alpha":
        if value < 0.50:
            return _status("bad", "Onvoldoende", "Toetsinhoud opnieuw bekijken.", "< 0,50")
        if value < 0.60:
            return _status("bad", "Zwak", "Betrouwbaarheid verbeteren.", "0,50 - 0,60")
        if value < 0.70:
            return _status("attention", "Matig", "Acceptabel bij kleine toetsen.", "0,60 - 0,70")
        if value < 0.80:
            return _status("good", "Goed", "Voldoende betrouwbaar.", "0,70 - 0,80")
        if value < 0.90:
            return _status("good", "Zeer goed", "Sterke toets.", "0,80 - 0,90")
        if value <= 0.95:
            return _status("excellent", "Uitstekend", "Zeer betrouwbaar.", "0,90 - 0,95")
        return _status("overlap", "Mogelijk overlap", "Controleer op vergelijkbare vragen.", "> 0,95")
    if kind == "sem":
        if value < 5:
            return _status("good", "Klein", "Toets is nauwkeurig.", "< 5%")
        if value <= 10:
            return _status("attention", "Redelijk", "Acceptabel, maar kan beter.", "5% - 10%")
        return _status("bad", "Groot", "Meer items of betere vragen overwegen.", "> 10%")
    return _status("neutral", "-", "-", "-")


def _item_status(p_value: float | None, rit: float | None, rir: float | None) -> dict[str, str]:
    p_status = _metric_status("p", p_value)
    rit_status = _metric_status("rit", rit)
    rir_status = _metric_status("rir", rir)
    metric_statuses = [("P-waarde", p_status), ("Rit", rit_status), ("Rir", rir_status)]
    problem_statuses = [(name, status) for name, status in metric_statuses if status["level"] == "bad"]
    attention_statuses = [(name, status) for name, status in metric_statuses if status["level"] in {"attention", "neutral"}]
    if problem_statuses:
        level, label = "bad", "Bekijken"
    elif attention_statuses:
        level, label = "attention", "Aandacht"
    else:
        return {
            "level": "good",
            "label": "Goed",
            "reason": "De vraag zit qua moeilijkheid en onderscheidend vermogen binnen de advieswaarden.",
            "advice": "Geen directe actie nodig.",
        }
    if rit_status["level"] == "bad" and rir_status["level"] == "bad":
        reason = (
            f"Rit is {rit_status['label'].lower()} en Rir is {rir_status['label'].lower()}: "
            "deze vraag hangt zwak samen met zowel de totaalscore als de rest van de toets."
        )
    elif rit_status["level"] == "bad":
        reason = (
            f"Rit is {rit_status['label'].lower()}: "
            "deze vraag sluit beperkt aan op de totale toetsprestatie van leerlingen."
        )
    elif rir_status["level"] == "bad":
        reason = (
            f"Rir is {rir_status['label'].lower()}: "
            "deze vraag sluit beperkt aan op het patroon van de overige vragen."
        )
    elif p_status["level"] == "bad":
        reason = (
            f"P-waarde is {p_status['label'].lower()}: "
            "de moeilijkheid wijkt sterk af en geeft mogelijk weinig bruikbaar onderscheid."
        )
    else:
        reason = (
            "Een of meer waarden zitten net buiten de voorkeurszone; "
            "de vraag is bruikbaar maar verdient aandacht."
        )
    advice = " ".join(
        dict.fromkeys(
            status["advice"]
            for _, status in metric_statuses
            if status["level"] in {"bad", "attention"}
        )
    ) or "Geen directe actie nodig."
    return {"level": level, "label": label, "reason": reason, "advice": advice}


def _categorical_results(
    name: str,
    mapping: dict[int, str],
    questions: list[dict[str, Any]],
    score_matrix: list[dict[int, float]],
    preferred_order: list[str] | None = None,
) -> dict[str, object]:
    if not score_matrix:
        return {"title": name, "entries": []}
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for question in questions:
        category = str(mapping.get(question["id"], "")).strip()
        if category:
            buckets[category].append(question)
    results = []
    for category, category_questions in buckets.items():
        possible = sum(float(question["maximum_score"]) for question in category_questions) * len(score_matrix)
        achieved = sum(
            scores.get(question["id"], 0.0)
            for scores in score_matrix
            for question in category_questions
        )
        results.append(
            {
                "name": category,
                "percentage": achieved / possible * 100 if possible else 0.0,
                "question_count": len(category_questions),
                "maximum_points": sum(float(question["maximum_score"]) for question in category_questions),
            }
        )
    if preferred_order:
        order = {value.casefold(): index for index, value in enumerate(preferred_order)}
        results.sort(key=lambda item: (order.get(str(item["name"]).casefold(), len(order)), str(item["name"]).lower()))
    else:
        results.sort(key=lambda item: (-float(item["percentage"]), str(item["name"]).lower()))
    return {"title": name, "entries": results}


def _student_categories(
    dimensions: dict[str, dict[str, object]],
    scores: dict[int, float],
    questions: list[dict[str, Any]],
    comparison_values: dict[str, dict[str, list[float]]] | None = None,
) -> dict[str, list[dict[str, object]]]:
    results: dict[str, list[dict[str, object]]] = {}
    for key, dimension in dimensions.items():
        mapping = dimension["mapping"]
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for question in questions:
            category = str(mapping.get(question["id"], "")).strip()
            if category:
                buckets[category].append(question)
        entries = []
        group_entries = {entry["name"]: entry for entry in dimension["results"]["entries"]}
        for category, category_questions in buckets.items():
            possible = sum(float(question["maximum_score"]) for question in category_questions)
            achieved = sum(scores.get(question["id"], 0.0) for question in category_questions)
            percentage = achieved / possible * 100 if possible else 0.0
            entries.append(
                {
                    "name": category,
                    "percentage": percentage,
                    "group_percentage": group_entries.get(category, {}).get("percentage", 0.0),
                    **_rank_context(
                        percentage,
                        (comparison_values or {}).get(key, {}).get(category, []),
                    ),
                }
            )
        group_order = {
            str(entry["name"]): index
            for index, entry in enumerate(dimension["results"]["entries"])
        }
        entries.sort(key=lambda item: (group_order.get(str(item["name"]), len(group_order)), str(item["name"]).lower()))
        results[key] = entries
    return results


def _profile_percentage(
    mapping: dict[int, str],
    scores: dict[int, float],
    questions: list[dict[str, Any]],
) -> float | None:
    relevant_questions = [
        question for question in questions if str(mapping.get(question["id"], "")).strip()
    ]
    possible = sum(float(question["maximum_score"]) for question in relevant_questions)
    if not possible:
        return None
    achieved = sum(scores.get(question["id"], 0.0) for question in relevant_questions)
    return achieved / possible * 100


def _rank_context(value: float | None, values: list[float]) -> dict[str, int | None]:
    if value is None or not values:
        return {"rank": None, "rank_count": None, "rank_end": None, "tied_count": None, "percentile": None, "top_percentage": None}
    rank = 1 + sum(candidate > value and not math.isclose(candidate, value, rel_tol=0.0, abs_tol=1e-9) for candidate in values)
    tied_count = sum(math.isclose(candidate, value, rel_tol=0.0, abs_tol=1e-9) for candidate in values)
    percentile = round(sum(candidate < value and not math.isclose(candidate, value, rel_tol=0.0, abs_tol=1e-9) for candidate in values) / len(values) * 100)
    top_percentage = max(1, math.ceil(rank / len(values) * 100))
    return {
        "rank": rank,
        "rank_count": len(values),
        "rank_end": rank + tied_count - 1,
        "tied_count": tied_count,
        "percentile": percentile,
        "top_percentage": top_percentage,
    }


def _accepted_multiple_choice_answers(question: dict[str, Any]) -> list[str]:
    accepted: list[str] = []
    try:
        key = normalize_multiple_choice_response(str(question.get("multiple_choice_answer") or ""))
    except ValueError:
        key = None
    if key:
        accepted.append(key)
    if bool(question.get("multiple_choice_correction_enabled")):
        mode = str(question.get("multiple_choice_correction_mode") or "none")
        if mode == "extra":
            for option in normalize_multiple_choice_option_list(str(question.get("multiple_choice_extra_answers") or "")):
                if option not in accepted:
                    accepted.append(option)
        elif mode == "neutralize":
            return ["Alle antwoorden"]
    return accepted


def _multiple_choice_conclusion(
    question: dict[str, Any],
    response_entries: list[dict[str, object]],
    p_value: float | None,
    rit: float | None,
    rir: float | None,
    not_made_count: int = 0,
    total_response_count: int = 0,
) -> dict[str, str]:
    status = _item_status(p_value, rit, rir)
    if bool(question.get("multiple_choice_correction_enabled")) and str(question.get("multiple_choice_correction_mode") or "") == "neutralize":
        return {
            "level": "neutral",
            "label": "Geneutraliseerd",
            "text": "Deze meerkeuzevraag is geneutraliseerd: alle ingevoerde antwoorden tellen goed. Interpreteer de itemstatistieken daarom voorzichtig.",
        }
    total = sum(int(entry["count"]) for entry in response_entries)
    correct_count = sum(int(entry["count"]) for entry in response_entries if entry.get("accepted"))
    most_chosen_wrong = next(
        (entry for entry in sorted(response_entries, key=lambda entry: int(entry["count"]), reverse=True) if not entry.get("accepted")),
        None,
    )
    unused_wrong = [
        str(entry["option"])
        for entry in response_entries
        if not entry.get("accepted") and int(entry["count"]) == 0 and str(entry["option"]) != "Leeg"
    ]
    correct_percentage = correct_count / total * 100 if total else 0.0
    if status["level"] in {"bad", "attention"}:
        text = status["reason"]
    elif correct_percentage >= 90:
        text = "Veel leerlingen kiezen het juiste antwoord; de vraag is waarschijnlijk makkelijk en onderscheidt beperkt."
        status = {"level": "attention", "label": "Makkelijk"}
    elif correct_percentage <= 20:
        text = "Weinig leerlingen kiezen het juiste antwoord; controleer vraagstelling, sleutel en eventuele misconcepties."
        status = {"level": "bad", "label": "Controlepunt"}
    else:
        text = "De vraag heeft een bruikbare spreiding en de toetsstatistieken vallen binnen of dicht bij de advieswaarden."
    if most_chosen_wrong and int(most_chosen_wrong["count"]) > correct_count:
        text += f" Afleider {most_chosen_wrong['option']} wordt vaker gekozen dan het juiste antwoord."
        status = {"level": "bad", "label": "Controlepunt"}
    elif unused_wrong:
        text += " Niet gekozen afleider(s): " + ", ".join(unused_wrong[:4]) + "."
    if not_made_count:
        not_made_percentage = not_made_count / total_response_count * 100 if total_response_count else 0.0
        text += (
            f" {not_made_count} leerling(en) ({not_made_percentage:.0f}%) hebben deze vraag als niet gemaakt ingevoerd; "
            "let op mogelijke tijdnood, onduidelijke vraagstelling of overslaan."
        )
        if not_made_percentage >= 20 and str(status["level"]) == "good":
            status = {"level": "attention", "label": "Veel N-scores"}
    return {
        "level": str(status["level"]),
        "label": str(status["label"]),
        "text": text,
    }


def _participant_lookup(data: dict[str, object]) -> dict[int, dict[str, object]]:
    return {
        int(participant["student_id"]): participant
        for participant in data.get("participants", [])
    }


def _participant_profile_lookup(
    data: dict[str, object],
    participant: dict[str, object],
) -> dict[tuple[str, str], float]:
    dimension_titles = {
        str(dimension["key"]): str(dimension["title"])
        for dimension in data.get("student_dimensions", [])
    }
    lookup: dict[tuple[str, str], float] = {}
    for dimension_key, entries in participant.get("profiles", {}).items():
        dimension_title = dimension_titles.get(str(dimension_key), str(dimension_key))
        for entry in entries:
            try:
                lookup[(dimension_title, str(entry["name"]))] = float(entry["percentage"])
            except (TypeError, ValueError, KeyError):
                continue
    return lookup


def _resit_pair(database: SubjectDatabase, test_id: int, test: dict[str, object]) -> tuple[int, int] | None:
    if int(test.get("is_resit") or 0) and test.get("original_test_id"):
        return int(test["original_test_id"]), int(test_id)
    row = database.connection.execute(
        "SELECT id FROM tests WHERE original_test_id=? "
        "ORDER BY COALESCE(test_date, created_at) DESC, created_at DESC, id DESC LIMIT 1",
        (test_id,),
    ).fetchone()
    if not row:
        return None
    return int(test_id), int(row["id"])


def _resit_analysis(
    database: SubjectDatabase,
    test_id: int,
    test: dict[str, object],
    current_data: dict[str, object],
) -> dict[str, object] | None:
    pair = _resit_pair(database, test_id, test)
    if not pair:
        return None
    original_id, resit_id = pair
    if original_id == resit_id:
        return None
    original_data = current_data if original_id == test_id else analysis_data(database, original_id, include_resit=False)
    resit_data = current_data if resit_id == test_id else analysis_data(database, resit_id, include_resit=False)
    original_participants = _participant_lookup(original_data)
    resit_participants = _participant_lookup(resit_data)
    shared_student_ids = sorted(
        set(original_participants) & set(resit_participants),
        key=lambda student_id: str(original_participants[student_id].get("name", "")).casefold(),
    )
    grade_available = bool(
        original_data.get("normalization_finalized")
        and resit_data.get("normalization_finalized")
    )
    student_rows: list[dict[str, object]] = []
    category_buckets: dict[tuple[str, str], dict[str, object]] = defaultdict(
        lambda: {"deltas": [], "students": set()}
    )
    for student_id in shared_student_ids:
        original = original_participants[student_id]
        resit = resit_participants[student_id]
        original_percentage = float(original.get("score_percentage", 0.0))
        resit_percentage = float(resit.get("score_percentage", 0.0))
        delta_percentage = resit_percentage - original_percentage
        original_grade = float(original["grade"]) if grade_available and original.get("grade") is not None else None
        resit_grade = float(resit["grade"]) if grade_available and resit.get("grade") is not None else None
        delta_grade = (
            resit_grade - original_grade
            if original_grade is not None and resit_grade is not None
            else None
        )
        final_grade = max(original_grade, resit_grade) if delta_grade is not None else None
        final_percentage = max(original_percentage, resit_percentage)
        student_rows.append(
            {
                "student_id": student_id,
                "name": original.get("name") or resit.get("name") or f"Leerling {student_id}",
                "original_percentage": original_percentage,
                "resit_percentage": resit_percentage,
                "delta_percentage": delta_percentage,
                "original_grade": original_grade if grade_available else None,
                "resit_grade": resit_grade if grade_available else None,
                "delta_grade": delta_grade if grade_available else None,
                "final_grade": final_grade,
                "final_percentage": final_percentage,
                "final_improved": (
                    resit_grade > original_grade + 0.05
                    if original_grade is not None and resit_grade is not None
                    else resit_percentage > original_percentage + 0.5
                ),
            }
        )
        original_profiles = _participant_profile_lookup(original_data, original)
        resit_profiles = _participant_profile_lookup(resit_data, resit)
        for key in set(original_profiles) & set(resit_profiles):
            bucket = category_buckets[key]
            bucket["deltas"].append(resit_profiles[key] - original_profiles[key])
            bucket["students"].add(student_id)
    student_rows.sort(key=lambda row: float(row["delta_percentage"]), reverse=True)
    category_rows = []
    for (dimension, category), bucket in category_buckets.items():
        deltas = [float(value) for value in bucket["deltas"]]
        if not deltas:
            continue
        category_rows.append(
            {
                "dimension": dimension,
                "category": category,
                "student_count": len(bucket["students"]),
                "mean_delta_percentage": _average(deltas),
            }
        )
    category_rows.sort(key=lambda row: float(row["mean_delta_percentage"] or 0.0), reverse=True)
    delta_percentages = [float(row["delta_percentage"]) for row in student_rows]
    delta_grades = [
        float(row["delta_grade"])
        for row in student_rows
        if row.get("delta_grade") is not None
    ]
    return {
        "original_test": original_data.get("test", {}),
        "resit_test": resit_data.get("test", {}),
        "comparison_count": len(student_rows),
        "improved_count": sum(1 for row in student_rows if float(row["delta_percentage"]) > 0.5),
        "lower_count": sum(1 for row in student_rows if float(row["delta_percentage"]) < -0.5),
        "same_count": sum(1 for row in student_rows if abs(float(row["delta_percentage"])) <= 0.5),
        "mean_delta_percentage": _average(delta_percentages),
        "grade_available": grade_available,
        "mean_delta_grade": _average(delta_grades),
        "final_effect_count": sum(1 for row in student_rows if bool(row.get("final_improved"))),
        "students": student_rows,
        "categories": category_rows,
    }


def analysis_data(
    database: SubjectDatabase,
    test_id: int,
    include_resit: bool = True,
    analysis_part_id: int | None = None,
) -> dict[str, object]:
    test_row = database.connection.execute(
        "SELECT t.id, t.name, t.level, t.grade_year, t.period, t.test_type, t.test_date, "
        "t.is_resit, t.original_test_id, sy.name AS school_year "
        "FROM tests t JOIN school_years sy ON sy.id=t.school_year_id WHERE t.id=?",
        (test_id,),
    ).fetchone()
    if not test_row:
        raise ValueError("De geselecteerde toets bestaat niet meer.")
    test = dict(test_row)
    full_maximum = maximum_score(database, test_id)
    analysis_parts = [
        dict(row)
        for row in database.rows(
            "SELECT id, name, sort_order FROM test_analysis_parts WHERE test_id=? ORDER BY sort_order",
            (test_id,),
        )
    ]
    selected_part = None
    if analysis_part_id is not None:
        selected_part = next((part for part in analysis_parts if int(part["id"]) == int(analysis_part_id)), None)
        if selected_part is None:
            raise ValueError("De geselecteerde deeltoets bestaat niet meer.")
    all_questions = [
        dict(row)
        for row in database.rows(
            "SELECT id, question_number, subquestion, question_number || COALESCE(subquestion, '') AS label, "
            "maximum_score, short_description, "
            "is_multiple_choice, multiple_choice_answer, multiple_choice_correction_enabled, "
            "multiple_choice_correction_mode, multiple_choice_extra_answers "
            f"FROM matrix_questions WHERE test_id=? ORDER BY {QUESTION_ORDER_SQL}",
            (test_id,),
        )
    ]
    for question in all_questions:
        question["maximum_score"] = float(question["maximum_score"])
    if selected_part is not None:
        assigned_question_ids = {
            int(row["question_id"])
            for row in database.rows(
                "SELECT qap.question_id FROM question_analysis_parts qap "
                "JOIN test_analysis_parts tap ON tap.id=qap.part_id "
                "WHERE tap.test_id=? AND tap.id=?",
                (test_id, int(selected_part["id"])),
            )
        }
        questions = [question for question in all_questions if int(question["id"]) in assigned_question_ids]
        maximum = sum(float(question["maximum_score"]) for question in questions)
    else:
        questions = all_questions
        maximum = full_maximum
    question_count = len(questions)

    if question_count:
        question_ids = [int(question["id"]) for question in questions]
        if selected_part is not None:
            placeholders = ",".join("?" for _ in question_ids)
            attempts_query = (
                "SELECT a.id, a.student_id, s.display_name, COALESCE(s.first_name, '') AS first_name, "
                "COALESCE(s.last_name, '') AS last_name, a.total_score "
                "FROM test_attempts a JOIN students s ON s.id=a.student_id "
                "WHERE a.test_id=? AND a.status='gemaakt' AND a.total_score IS NOT NULL "
                f"AND (SELECT COUNT(*) FROM scores sc WHERE sc.attempt_id=a.id AND sc.question_id IN ({placeholders}) "
                "AND sc.score IS NOT NULL)=? ORDER BY s.display_name"
            )
            attempts_parameters: tuple[object, ...] = (test_id, *question_ids, question_count)
        else:
            attempts_query = (
                "SELECT a.id, a.student_id, s.display_name, COALESCE(s.first_name, '') AS first_name, "
                "COALESCE(s.last_name, '') AS last_name, a.total_score "
                "FROM test_attempts a JOIN students s ON s.id=a.student_id "
                "WHERE a.test_id=? AND a.status='gemaakt' AND a.total_score IS NOT NULL "
                "AND (SELECT COUNT(*) FROM scores sc WHERE sc.attempt_id=a.id AND sc.score IS NOT NULL)=? "
                "ORDER BY s.display_name"
            )
            attempts_parameters = (test_id, question_count)
        attempts = [dict(row) for row in database.rows(attempts_query, attempts_parameters)]
    else:
        question_ids = []
        attempts = []
    attempts.sort(key=lambda attempt: student_sort_key(attempt["display_name"], attempt["first_name"], attempt["last_name"]))
    attempt_ids = {int(row["id"]) for row in attempts}
    score_by_attempt: dict[int, dict[int, float]] = {attempt_id: {} for attempt_id in attempt_ids}
    response_by_attempt: dict[int, dict[int, str]] = {attempt_id: {} for attempt_id in attempt_ids}
    if question_ids:
        score_placeholders = ",".join("?" for _ in question_ids)
        score_query = (
            "SELECT sc.attempt_id, sc.question_id, sc.score, sc.response_text FROM scores sc "
            "JOIN test_attempts a ON a.id=sc.attempt_id WHERE a.test_id=? "
            f"AND sc.question_id IN ({score_placeholders}) AND sc.score IS NOT NULL"
        )
        score_parameters: tuple[object, ...] = (test_id, *question_ids)
    else:
        score_query = (
            "SELECT sc.attempt_id, sc.question_id, sc.score, sc.response_text FROM scores sc "
            "JOIN test_attempts a ON a.id=sc.attempt_id WHERE a.test_id=? AND sc.score IS NOT NULL"
        )
        score_parameters = (test_id,)
    for row in database.rows(score_query, score_parameters):
        attempt_id = int(row["attempt_id"])
        if attempt_id in score_by_attempt:
            question_id = int(row["question_id"])
            score_by_attempt[attempt_id][question_id] = float(row["score"])
            response_text = str(row["response_text"] or "").strip().upper()
            if response_text:
                response_by_attempt[attempt_id][question_id] = response_text

    settings = load_normalization(database, test_id)
    finalized = has_active_normalization(database, test_id)
    participants: list[dict[str, object]] = []
    score_matrix: list[dict[int, float]] = []
    for attempt in attempts:
        scores = score_by_attempt[int(attempt["id"])]
        full_total = float(attempt["total_score"])
        total = sum(scores.get(int(question["id"]), 0.0) for question in questions)
        grade = (
            calculate_grade(total, maximum, settings)
            if finalized and maximum > 0 and selected_part is None
            else None
        )
        full_grade = calculate_grade(full_total, full_maximum, settings) if finalized and full_maximum > 0 else None
        score_matrix.append(scores)
        participants.append(
            {
                "student_id": int(attempt["student_id"]),
                "name": attempt["display_name"],
                "total_score": total,
                "score_percentage": total / maximum * 100 if maximum else 0.0,
                "grade": grade,
                "full_total_score": full_total,
                "full_score_percentage": full_total / full_maximum * 100 if full_maximum else 0.0,
                "full_grade": full_grade,
                "sufficient": grade >= 5.5 if grade is not None else None,
                "scores": scores,
            }
        )

    totals = [float(participant["total_score"]) for participant in participants]
    mode_score, mode_count = _mode(totals)
    grades = [float(participant["grade"]) for participant in participants if participant["grade"] is not None]
    matrix = [[scores.get(question["id"], 0.0) for question in questions] for scores in score_matrix]
    alpha = _cronbach(matrix)
    score_sd = statistics.stdev(totals) if len(totals) >= 2 else None
    sem_score = (
        score_sd * math.sqrt(max(0.0, 1 - alpha))
        if score_sd is not None and alpha is not None and alpha <= 1
        else None
    )
    sem_percentage = sem_score / maximum * 100 if sem_score is not None and maximum else None
    item_analysis = []
    for index, question in enumerate(questions):
        values = [row[index] for row in matrix]
        total_values = [sum(row) for row in matrix]
        rest_values = [sum(row) - row[index] for row in matrix]
        p_value = (_average(values) or 0.0) / question["maximum_score"] if values and question["maximum_score"] else None
        rit = _pearson(values, total_values)
        rir = _pearson(values, rest_values)
        item_analysis.append(
            {
                "id": question["id"],
                "label": question["label"],
                "display_label": f"Vraag {question['label']}",
                "question_number": str(question["question_number"]),
                "subquestion": question["subquestion"] or None,
                "row_type": "subquestion" if question["subquestion"] else "question",
                "description": question["short_description"] or "",
                "maximum_score": question["maximum_score"],
                "is_multiple_choice": bool(question.get("is_multiple_choice")),
                "p_value": p_value,
                "rit": rit,
                "rir": rir,
                "p_status": _metric_status("p", p_value),
                "rit_status": _metric_status("rit", rit),
                "rir_status": _metric_status("rir", rir),
                "status": _item_status(p_value, rit, rir),
            }
        )

    item_by_question_id = {int(item["id"]): item for item in item_analysis}
    question_group_analysis = []
    grouped_questions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for question in questions:
        grouped_questions[str(question["question_number"])].append(question)
    for question_number, group_questions in grouped_questions.items():
        has_subquestions = any(question["subquestion"] for question in group_questions)
        if not has_subquestions:
            item = dict(item_by_question_id[int(group_questions[0]["id"])])
            item["display_label"] = f"Vraag {question_number}"
            question_group_analysis.append(item)
            continue
        child_items = []
        group_indexes = [questions.index(question) for question in group_questions]
        group_values = [sum(row[index] for index in group_indexes) for row in matrix]
        total_values = [sum(row) for row in matrix]
        rest_values = [total - group_score for total, group_score in zip(total_values, group_values)]
        group_maximum = sum(float(question["maximum_score"]) for question in group_questions)
        p_value = (_average(group_values) or 0.0) / group_maximum if group_values and group_maximum else None
        rit = _pearson(group_values, total_values)
        rir = _pearson(group_values, rest_values)
        for question in group_questions:
            child = dict(item_by_question_id[int(question["id"])])
            child["label"] = question["subquestion"] or question["label"]
            child["display_label"] = str(question["subquestion"] or question["label"])
            child["row_type"] = "subquestion"
            child_items.append(child)
        question_group_analysis.append(
            {
                "id": f"group-{question_number}",
                "label": str(question_number),
                "display_label": f"Vraag {question_number}",
                "question_number": str(question_number),
                "subquestion": None,
                "row_type": "group",
                "description": "Totaal van de subvragen",
                "maximum_score": group_maximum,
                "is_multiple_choice": False,
                "p_value": p_value,
                "rit": rit,
                "rir": rir,
                "p_status": _metric_status("p", p_value),
                "rit_status": _metric_status("rit", rit),
                "rir_status": _metric_status("rir", rir),
                "status": _item_status(p_value, rit, rir),
                "children": child_items,
            }
        )

    multiple_choice_items = []
    for question in questions:
        if not bool(question.get("is_multiple_choice")):
            continue
        item = item_analysis[[q["id"] for q in questions].index(question["id"])]
        accepted = _accepted_multiple_choice_answers(question)
        responses = [
            response_by_attempt.get(int(attempt["id"]), {}).get(int(question["id"]), "")
            for attempt in attempts
        ]
        not_made_count = sum(1 for response in responses if is_not_made_score(str(response)))
        choice_responses = [response for response in responses if not is_not_made_score(str(response))]
        response_options = sorted(
            {
                response
                for response in choice_responses
                if response
            }
            | {option for option in accepted if option != "Alle antwoorden"}
        )
        if not response_options:
            response_options = ["Leeg"]
        response_entries = []
        total_responses = len(choice_responses)
        for option in response_options:
            count = sum(1 for response in choice_responses if (response or "Leeg") == option)
            response_entries.append(
                {
                    "option": option,
                    "count": count,
                    "percentage": count / total_responses * 100 if total_responses else 0.0,
                    "accepted": option in accepted or "Alle antwoorden" in accepted,
                }
            )
        response_entries.sort(key=lambda entry: (not bool(entry["accepted"]), str(entry["option"])))
        multiple_choice_items.append(
            {
                "id": question["id"],
                "label": question["label"],
                "description": question["short_description"] or "",
                "maximum_score": question["maximum_score"],
                "answer_key": question.get("multiple_choice_answer") or "",
                "accepted_answers": accepted,
                "correction_enabled": bool(question.get("multiple_choice_correction_enabled")),
                "correction_mode": question.get("multiple_choice_correction_mode") or "none",
                "response_count": total_responses,
                "not_made_count": not_made_count,
                "not_made_percentage": not_made_count / len(responses) * 100 if responses else 0.0,
                "correct_count": sum(int(entry["count"]) for entry in response_entries if entry["accepted"]),
                "p_value": item["p_value"],
                "rit": item["rit"],
                "rir": item["rir"],
                "p_status": item["p_status"],
                "rit_status": item["rit_status"],
                "rir_status": item["rir_status"],
                "responses": response_entries,
                "conclusion": _multiple_choice_conclusion(
                    question,
                    response_entries,
                    item["p_value"],
                    item["rit"],
                    item["rir"],
                    not_made_count,
                    len(responses),
                ),
            }
        )
    multiple_choice_summary = {
        "question_count": len(multiple_choice_items),
        "mean_p_value": _average([float(item["p_value"]) for item in multiple_choice_items if item["p_value"] is not None]),
        "mean_rit": _average([float(item["rit"]) for item in multiple_choice_items if item["rit"] is not None]),
        "mean_rir": _average([float(item["rir"]) for item in multiple_choice_items if item["rir"] is not None]),
        "attention_count": sum(1 for item in multiple_choice_items if item["conclusion"]["level"] in {"bad", "attention"}),
    }

    taxonomy_values: dict[str, dict[int, str]] = defaultdict(dict)
    taxonomy_labels: dict[str, str] = {}
    for row in database.rows(
        "SELECT d.name AS definition_name, qtv.question_id, tv.name AS value_name "
        "FROM question_taxonomy_values qtv "
        "JOIN taxonomy_definitions d ON d.id=qtv.taxonomy_id "
        "JOIN taxonomy_values tv ON tv.id=qtv.taxonomy_value_id "
        "JOIN matrix_questions q ON q.id=qtv.question_id WHERE q.test_id=?",
        (test_id,),
    ):
        definition_name = str(row["definition_name"])
        definition_key = definition_name.casefold()
        taxonomy_labels[definition_key] = definition_name
        taxonomy_values[definition_key][int(row["question_id"])] = row["value_name"]
    property_values: dict[str, dict[int, str]] = defaultdict(dict)
    property_labels: dict[str, str] = {}
    for row in database.rows(
        "SELECT p.name AS definition_name, qpv.question_id, qpv.value "
        "FROM question_property_values qpv JOIN property_definitions p ON p.id=qpv.property_id "
        "JOIN matrix_questions q ON q.id=qpv.question_id WHERE q.test_id=?",
        (test_id,),
    ):
        definition_name = str(row["definition_name"])
        definition_key = definition_name.casefold()
        property_labels[definition_key] = definition_name
        property_values[definition_key][int(row["question_id"])] = row["value"]

    dimensions: dict[str, dict[str, object]] = {}
    preferred_keys = ["rtti", "domein", "vraagtype"]
    taxonomy_keys = sorted(
        (key for key, mapping in taxonomy_values.items() if mapping),
        key=lambda key: (0 if key in preferred_keys else 1, taxonomy_labels.get(key, key).lower()),
    )
    property_keys = sorted(
        (key for key, mapping in property_values.items() if mapping),
        key=lambda key: (0 if key in preferred_keys else 1, property_labels.get(key, key).lower()),
    )
    for taxonomy_key in taxonomy_keys:
        safe_key = "taxonomy_" + "".join(
            character if character.isalnum() else "_"
            for character in taxonomy_key
        ).strip("_")
        dimensions[safe_key] = {
            "title": taxonomy_labels.get(taxonomy_key, taxonomy_key),
            "mapping": taxonomy_values[taxonomy_key],
            "orientation": "vertical",
            "is_rtti": taxonomy_key == "rtti",
            "kind": "taxonomy",
        }
    for property_key in property_keys:
        safe_key = "property_" + "".join(
            character if character.isalnum() else "_"
            for character in property_key
        ).strip("_")
        dimensions[safe_key] = {
            "title": property_labels.get(property_key, property_key),
            "mapping": property_values[property_key],
            "orientation": "horizontal",
            "is_rtti": False,
            "kind": "property",
        }
    for key, dimension in dimensions.items():
        dimension["results"] = _categorical_results(
            str(dimension["title"]),
            dimension["mapping"],
            questions,
            score_matrix,
            preferred_order=["R", "T1", "T2", "I"] if dimension.get("is_rtti") else None,
        )
    group_dimensions: list[dict[str, object]] = [
        {
            "key": key,
            "title": str(dimension["title"]),
            "entries": list(dimension["results"]["entries"]),
            "orientation": str(dimension.get("orientation", "vertical")),
            "is_rtti": bool(dimension.get("is_rtti")),
            "kind": str(dimension.get("kind", "property")),
        }
        for key, dimension in dimensions.items()
        if dimension["results"]["entries"]
    ]
    rtti_dimension = next(
        (dimension["results"] for dimension in dimensions.values() if str(dimension["title"]).casefold() == "rtti"),
        {"title": "RTTI", "entries": []},
    )
    domain_dimension = next(
        (dimension["results"] for dimension in dimensions.values() if str(dimension["title"]).casefold() == "domein"),
        {"title": "Domeinen", "entries": []},
    )
    question_type_dimension = next(
        (dimension["results"] for dimension in dimensions.values() if str(dimension["title"]).casefold() == "vraagtype"),
        {"title": "Vraagtypen", "entries": []},
    )

    item_by_id = {int(item["id"]): item for item in item_analysis}
    participant_totals = [float(participant["total_score"]) for participant in participants]
    profile_values = {
        key: [
            percentage
            for scores in score_matrix
            if (percentage := _profile_percentage(dimension["mapping"], scores, questions)) is not None
        ]
        for key, dimension in dimensions.items()
    }
    category_values: dict[str, dict[str, list[float]]] = {}
    for key, dimension in dimensions.items():
        values_by_category: dict[str, list[float]] = defaultdict(list)
        for peer_scores in score_matrix:
            for entry in _student_categories({key: dimension}, peer_scores, questions).get(key, []):
                values_by_category[str(entry["name"])].append(float(entry["percentage"]))
        category_values[key] = dict(values_by_category)
    student_dimensions = [
        {
            "key": dimension["key"],
            "title": dimension["title"],
            "is_rtti": dimension["is_rtti"],
            "kind": dimension["kind"],
        }
        for dimension in group_dimensions
    ]
    for participant, scores in zip(participants, score_matrix):
        participant["profiles"] = _student_categories(dimensions, scores, questions, category_values)
        participant.update(_rank_context(float(participant["total_score"]), participant_totals))
        participant["profile_summaries"] = {}
        for key, dimension in dimensions.items():
            percentage = _profile_percentage(dimension["mapping"], scores, questions)
            if percentage is None or not dimension["results"]["entries"]:
                continue
            group_percentage = _average(profile_values[key])
            participant["profile_summaries"][key] = {
                "percentage": percentage,
                "group_percentage": group_percentage,
                **_rank_context(percentage, profile_values[key]),
            }
        participant["items"] = [
            {
                "label": question["label"],
                "component": property_values.get("domein", {}).get(question["id"])
                or question["short_description"]
                or "-",
                "rtti": taxonomy_values.get("rtti", {}).get(question["id"], "-"),
                "score": scores.get(question["id"], 0.0),
                "maximum_score": question["maximum_score"],
                "percentage": scores.get(question["id"], 0.0) / question["maximum_score"] * 100
                if question["maximum_score"]
                else 0.0,
                "group_percentage": (item_by_id[question["id"]]["p_value"] or 0.0) * 100
                if item_by_id[question["id"]]["p_value"] is not None
                else None,
            }
            for question in questions
        ]
    mean_p = _average([float(item["p_value"]) for item in item_analysis if item["p_value"] is not None])
    mean_rit = _average([float(item["rit"]) for item in item_analysis if item["rit"] is not None])
    mean_rir = _average([float(item["rir"]) for item in item_analysis if item["rir"] is not None])
    difficult = sorted(item_analysis, key=lambda item: item["p_value"] if item["p_value"] is not None else 2)[:5]
    easy = sorted(
        item_analysis, key=lambda item: item["p_value"] if item["p_value"] is not None else -1, reverse=True
    )[:5]
    if question_count and selected_part is not None:
        placeholders = ",".join("?" for _ in question_ids)
        incomplete = int(
            database.scalar(
                "SELECT COUNT(*) FROM test_attempts a WHERE a.test_id=? AND a.status='gemaakt' AND "
                f"(SELECT COUNT(*) FROM scores sc WHERE sc.attempt_id=a.id AND sc.question_id IN ({placeholders}) "
                "AND sc.score IS NOT NULL)<?",
                (test_id, *question_ids, question_count),
            )
            or 0
        )
    else:
        incomplete = int(
            database.scalar(
                "SELECT COUNT(*) FROM test_attempts a WHERE a.test_id=? AND a.status='gemaakt' AND "
                "(SELECT COUNT(*) FROM scores sc WHERE sc.attempt_id=a.id AND sc.score IS NOT NULL)<?",
                (test_id, question_count),
            )
            or 0
        ) if question_count else 0
    subtest_context = None
    if selected_part is not None:
        part_percentages = [float(participant["score_percentage"]) for participant in participants]
        full_percentages = [float(participant["full_score_percentage"]) for participant in participants]
        part_mean = _average(part_percentages)
        full_mean = _average(full_percentages)
        subtest_context = {
            "id": int(selected_part["id"]),
            "name": str(selected_part["name"]),
            "question_count": question_count,
            "maximum_score": maximum,
            "total_test_maximum": full_maximum,
            "mean_percentage": part_mean,
            "total_mean_percentage": full_mean,
            "difference_percentage": (part_mean - full_mean) if part_mean is not None and full_mean is not None else None,
            "correlation_with_total": _pearson(part_percentages, full_percentages),
        }
    result = {
        "test": test,
        "maximum_score": maximum,
        "full_maximum_score": full_maximum,
        "analysis_parts": analysis_parts,
        "selected_analysis_part_id": int(analysis_part_id) if analysis_part_id is not None else None,
        "subtest_context": subtest_context,
        "normalization_finalized": finalized,
        "participants": participants,
        "participant_count": len(participants),
        "sample": {
            "minimum": MIN_RELIABLE_ANALYSIS_PARTICIPANTS,
            "is_small_group": len(participants) < MIN_RELIABLE_ANALYSIS_PARTICIPANTS,
            "message": (
                f"Voorzichtig interpreteren: er zijn {len(participants)} complete resultaten. "
                f"Vanaf ongeveer {MIN_RELIABLE_ANALYSIS_PARTICIPANTS} leerlingen worden itemstatistieken en betrouwbaarheid stabieler."
            ),
        },
        "incomplete_count": incomplete,
        "question_count": question_count,
        "summary": {
            "mean_score": _average(totals),
            "median_score": statistics.median(totals) if totals else None,
            "mode_score": mode_score,
            "mode_count": mode_count,
            "sd_score": score_sd,
            "mean_grade": _average(grades),
            "sd_grade": statistics.stdev(grades) if len(grades) >= 2 else None,
            "highest_score": max(totals) if totals else None,
            "lowest_score": min(totals) if totals else None,
            "sufficient_percentage": sum(bool(participant["sufficient"]) for participant in participants)
            / len(participants)
            * 100
            if finalized and participants and selected_part is None
            else None,
        },
        "quality": {
            "alpha": {"value": alpha, "status": _metric_status("alpha", alpha)},
            "p_value": {"value": mean_p, "status": _metric_status("p", mean_p)},
            "rit": {"value": mean_rit, "status": _metric_status("rit", mean_rit)},
            "rir": {"value": mean_rir, "status": _metric_status("rir", mean_rir)},
            "sem": {
                "value": sem_percentage,
                "score_value": sem_score,
                "status": _metric_status("sem", sem_percentage),
            },
        },
        "item_analysis": item_analysis,
        "question_group_analysis": question_group_analysis,
        "multiple_choice": {
            "summary": multiple_choice_summary,
            "items": multiple_choice_items,
        },
        "easy_items": easy,
        "difficult_items": difficult,
        "groups": {
            "rtti": rtti_dimension,
            "domains": domain_dimension,
            "question_types": question_type_dimension,
        },
        "group_dimensions": group_dimensions,
        "student_dimensions": student_dimensions,
    }
    result["resit_analysis"] = _resit_analysis(database, test_id, test, result) if include_resit else None
    return result
