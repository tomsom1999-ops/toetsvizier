from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP

from .database import SubjectDatabase
from .name_sorting import student_sort_key


METHODS = {
    "fouten_per_punt": "Fouten per punt",
    "cvte_cesuur": "CvTE-methode",
    "n_term": "N-term",
    "cesuur": "Lineaire methode",
    "cesuur_knik": "Lineaire methode met knik",
    "percentage_voldoende": "Percentage goed voor 5,5",
}


@dataclass(frozen=True)
class SavedNormalization:
    method: str
    configuration: dict[str, object]
    decimal_places: int
    rounding_method: str


def maximum_score(database: SubjectDatabase, test_id: int) -> float:
    value = database.scalar("SELECT SUM(maximum_score) FROM matrix_questions WHERE test_id=?", (test_id,))
    return float(value or 0.0)


def default_settings(maximum: float) -> dict[str, object]:
    pass_score = max(1.0, math.ceil(maximum * 0.55 * 2) / 2) if maximum else 0.0
    return {
        "method": "n_term",
        "n_term": 1.0,
        "deduction": 0.25,
        "pass_score": pass_score,
        "pass_percentage": 55.0,
        "decimal_places": 1,
        "rounding_method": "standaard",
    }


def load_normalization(database: SubjectDatabase, test_id: int) -> dict[str, object]:
    maximum = maximum_score(database, test_id)
    settings = default_settings(maximum)
    row = database.connection.execute(
        "SELECT method, configuration_json, decimal_places, rounding_method "
        "FROM normalizations WHERE test_id=? AND is_active=1 ORDER BY id DESC LIMIT 1",
        (test_id,),
    ).fetchone()
    if not row:
        return settings
    configuration = json.loads(row["configuration_json"] or "{}")
    settings.update(configuration)
    settings["method"] = row["method"]
    if row["method"] == "omzettingstabel":
        settings["method"] = "percentage_voldoende"
        if maximum:
            settings["pass_percentage"] = (
                float(settings.get("pass_score", maximum * 0.55))
                / maximum
                * 100
            )
    settings["decimal_places"] = int(row["decimal_places"])
    settings["rounding_method"] = row["rounding_method"]
    return settings


def has_active_normalization(database: SubjectDatabase, test_id: int) -> bool:
    return bool(
        database.scalar(
            "SELECT COUNT(*) FROM normalizations WHERE test_id=? AND is_active=1",
            (test_id,),
        )
    )


def _clamp_grade(value: float) -> float:
    return max(1.0, min(10.0, value))


def _validate_settings(maximum: float, settings: dict[str, object]) -> dict[str, object]:
    if maximum <= 0:
        raise ValueError("Maak eerst een toetsmatrijs met minimaal 1 punt voordat u normering vaststelt.")
    configuration = default_settings(maximum)
    configuration.update(settings)
    method = str(configuration.get("method", "n_term"))
    if method not in METHODS:
        raise ValueError("Deze normeringsmethode wordt niet ondersteund.")
    configuration["method"] = method
    if method == "n_term":
        n_term = float(configuration.get("n_term", 1.0))
        if n_term < 0.0 or n_term > 4.0 or not math.isclose(n_term * 10, round(n_term * 10), abs_tol=1e-9):
            raise ValueError("Een officiele N-term heeft een decimaal en ligt voor deze berekening tussen 0,0 en 4,0.")
        configuration["n_term"] = n_term
        configuration["decimal_places"] = 1
        configuration["rounding_method"] = "standaard"
    if method == "fouten_per_punt":
        deduction = float(configuration.get("deduction", 0.25))
        if deduction <= 0:
            raise ValueError("Aftrek per fout moet groter zijn dan nul.")
        configuration["deduction"] = deduction
    if method in {"cvte_cesuur", "cesuur", "cesuur_knik"}:
        pass_score = float(configuration.get("pass_score", maximum * 0.55))
        if not 0 < pass_score <= maximum:
            raise ValueError("De cesuur moet groter zijn dan nul en binnen de maximumscore vallen.")
        if method == "cvte_cesuur":
            if pass_score < maximum / 4 or pass_score > maximum * 3 / 4:
                raise ValueError("Bij de CvTE-methode moet de 5,5-score tussen 25% en 75% van de maximumscore liggen.")
            if not math.isclose(pass_score * 10, round(pass_score * 10), abs_tol=1e-9):
                raise ValueError("Bij de CvTE-methode mag de 5,5-score maximaal een decimaal hebben.")
            configuration["decimal_places"] = 1
            configuration["rounding_method"] = "standaard"
        configuration["pass_score"] = pass_score
    if method == "percentage_voldoende":
        percentage = float(configuration.get("pass_percentage", 55.0))
        if not math.isfinite(percentage) or not 0 < percentage < 100:
            raise ValueError("Het percentage voor een 5,5 moet groter zijn dan 0% en kleiner dan 100%.")
        configuration["pass_percentage"] = percentage
    return configuration


def _official_n_term_grade(score: float, maximum: float, n_term: float) -> float:
    main_relation = 9.0 * score / maximum + n_term
    if n_term > 1.0:
        lower_boundary = 1.0 + score * (9.0 / maximum) * 2.0
        upper_boundary = 10.0 - (maximum - score) * (9.0 / maximum) * 0.5
        return min(main_relation, lower_boundary, upper_boundary)
    if n_term < 1.0:
        lower_boundary = 1.0 + score * (9.0 / maximum) * 0.5
        upper_boundary = 10.0 - (maximum - score) * (9.0 / maximum) * 2.0
        return max(main_relation, lower_boundary, upper_boundary)
    return main_relation


def unrounded_grade(score: float, maximum: float, settings: dict[str, object]) -> float:
    if maximum <= 0:
        return 1.0
    method = str(settings.get("method", "n_term"))
    score = max(0.0, min(maximum, float(score)))
    pass_score = max(0.1, min(maximum, float(settings.get("pass_score", maximum * 0.55))))
    if method == "percentage_voldoende":
        pass_score = maximum * float(settings.get("pass_percentage", 55.0)) / 100
    if method == "fouten_per_punt":
        result = 10.0 - (maximum - score) * float(settings.get("deduction", 0.25))
    elif method == "cvte_cesuur":
        cito_n_term = 5.45 - (9.0 * pass_score / maximum)
        result = _official_n_term_grade(score, maximum, cito_n_term)
    elif method == "n_term":
        result = _official_n_term_grade(score, maximum, float(settings.get("n_term", 1.0)))
    elif method == "cesuur":
        result = 10.0 - (maximum - score) * (4.5 / max(0.1, maximum - pass_score))
    elif method == "cesuur_knik":
        if score <= pass_score:
            result = 1.0 + 4.5 * score / pass_score
        else:
            result = 5.5 + 4.5 * (score - pass_score) / max(0.1, maximum - pass_score)
    elif method == "percentage_voldoende":
        if score <= pass_score:
            result = 1.0 + 4.5 * score / pass_score
        else:
            result = 5.5 + 4.5 * (score - pass_score) / max(0.1, maximum - pass_score)
    else:
        result = 1.0 + 9.0 * score / maximum
    return _clamp_grade(result)


def round_grade(value: float, decimal_places: int = 1, method: str = "standaard") -> float:
    decimal_value = Decimal(str(value))
    if method == "halve cijfers":
        return float((decimal_value * 2).quantize(Decimal("1"), rounding=ROUND_HALF_UP) / 2)
    if method == "hele cijfers":
        return float(decimal_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    quantum = Decimal("1").scaleb(-max(0, min(2, decimal_places)))
    rounding = {
        "naar boven": ROUND_CEILING,
        "naar beneden": ROUND_FLOOR,
    }.get(method, ROUND_HALF_UP)
    return float(decimal_value.quantize(quantum, rounding=rounding))


def calculate_grade(score: float, maximum: float, settings: dict[str, object]) -> float:
    return round_grade(
        unrounded_grade(score, maximum, settings),
        int(settings.get("decimal_places", 1)),
        str(settings.get("rounding_method", "standaard")),
    )


def sufficient_score(maximum: float, settings: dict[str, object]) -> float | None:
    if maximum <= 0:
        return None
    steps = int(math.ceil(maximum * 2))
    for step in range(steps + 1):
        score = step / 2
        if calculate_grade(score, maximum, settings) >= 5.5:
            return score
    return None


def _reliability(database: SubjectDatabase, test_id: int) -> float | None:
    question_ids = [
        row["id"] for row in database.rows("SELECT id FROM matrix_questions WHERE test_id=? ORDER BY id", (test_id,))
    ]
    if len(question_ids) < 2:
        return None
    rows = database.rows(
        "SELECT a.student_id, s.question_id, s.score FROM test_attempts a "
        "JOIN scores s ON s.attempt_id=a.id "
        "WHERE a.test_id=? AND a.status='gemaakt' AND s.score IS NOT NULL",
        (test_id,),
    )
    per_student: dict[int, dict[int, float]] = {}
    for row in rows:
        per_student.setdefault(row["student_id"], {})[row["question_id"]] = float(row["score"])
    complete = [
        [student_scores[question_id] for question_id in question_ids]
        for student_scores in per_student.values()
        if all(question_id in student_scores for question_id in question_ids)
    ]
    if len(complete) < 2:
        return None
    total_values = [sum(scores) for scores in complete]
    total_variance = statistics.variance(total_values)
    if math.isclose(total_variance, 0.0):
        return None
    item_variance = sum(statistics.variance([scores[index] for scores in complete]) for index in range(len(question_ids)))
    alpha = len(question_ids) / (len(question_ids) - 1) * (1 - item_variance / total_variance)
    return round(alpha, 2)


def dashboard_data(database: SubjectDatabase, test_id: int) -> dict[str, object]:
    test = database.connection.execute(
        "SELECT t.id, t.name, t.level, t.grade_year, t.period, sy.name AS school_year "
        "FROM tests t JOIN school_years sy ON sy.id=t.school_year_id WHERE t.id=?",
        (test_id,),
    ).fetchone()
    if not test:
        raise ValueError("De geselecteerde toets bestaat niet meer.")
    question_count = int(database.scalar("SELECT COUNT(*) FROM matrix_questions WHERE test_id=?", (test_id,)) or 0)
    participant_rows = [
        dict(row)
        for row in database.rows(
            "SELECT s.display_name, COALESCE(s.first_name, '') AS first_name, "
            "COALESCE(s.last_name, '') AS last_name, a.total_score FROM test_attempts a "
            "JOIN students s ON s.id=a.student_id "
            "WHERE a.test_id=? AND a.status='gemaakt' AND a.total_score IS NOT NULL "
            "AND (SELECT COUNT(*) FROM scores sc WHERE sc.attempt_id=a.id AND sc.score IS NOT NULL)=? "
            "ORDER BY s.display_name",
            (test_id, question_count),
        )
    ]
    participant_rows.sort(key=lambda row: student_sort_key(row["display_name"], row["first_name"], row["last_name"]))
    participants = [
        {
            "name": row["display_name"],
            "score": float(row["total_score"]),
        }
        for row in participant_rows
    ]
    incomplete_count = int(
        database.scalar(
            "SELECT COUNT(*) FROM test_attempts a WHERE a.test_id=? AND a.status='gemaakt' "
            "AND a.total_score IS NOT NULL "
            "AND (SELECT COUNT(*) FROM scores sc WHERE sc.attempt_id=a.id AND sc.score IS NOT NULL)<?",
            (test_id, question_count),
        )
        or 0
    )
    return {
        "test": dict(test),
        "maximum_score": maximum_score(database, test_id),
        "participants": participants,
        "incomplete_count": incomplete_count,
        "reliability": _reliability(database, test_id),
    }


def save_normalization(database: SubjectDatabase, test_id: int, settings: dict[str, object]) -> SavedNormalization:
    maximum = maximum_score(database, test_id)
    configuration = _validate_settings(maximum, settings)
    method = str(configuration["method"])
    decimal_places = max(0, min(2, int(configuration.get("decimal_places", 1))))
    rounding_method = str(configuration.get("rounding_method", "standaard"))
    connection = database.connection
    try:
        connection.execute("UPDATE normalizations SET is_active=0 WHERE test_id=?", (test_id,))
        connection.execute(
            "INSERT INTO normalizations(test_id, method, configuration_json, decimal_places, rounding_method, is_active) "
            "VALUES(?, ?, ?, ?, ?, 1)",
            (
                test_id,
                method,
                json.dumps(configuration),
                decimal_places,
                rounding_method,
            ),
        )
        question_count = int(connection.execute("SELECT COUNT(*) FROM matrix_questions WHERE test_id=?", (test_id,)).fetchone()[0])
        connection.execute(
            "UPDATE test_attempts SET grade=NULL, updated_at=CURRENT_TIMESTAMP "
            "WHERE test_id=? AND status='gemaakt' AND total_score IS NOT NULL "
            "AND (SELECT COUNT(*) FROM scores sc WHERE sc.attempt_id=test_attempts.id AND sc.score IS NOT NULL)<?",
            (test_id, question_count),
        )
        attempts = connection.execute(
            "SELECT id, total_score FROM test_attempts "
            "WHERE test_id=? AND status='gemaakt' AND total_score IS NOT NULL "
            "AND (SELECT COUNT(*) FROM scores sc WHERE sc.attempt_id=test_attempts.id AND sc.score IS NOT NULL)=?",
            (test_id, question_count),
        ).fetchall()
        for attempt in attempts:
            grade = calculate_grade(float(attempt["total_score"]), maximum, configuration)
            connection.execute("UPDATE test_attempts SET grade=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (grade, attempt["id"]))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return SavedNormalization(method, configuration, decimal_places, rounding_method)


def remove_normalization(database: SubjectDatabase, test_id: int) -> None:
    connection = database.connection
    try:
        connection.execute("DELETE FROM normalizations WHERE test_id=?", (test_id,))
        connection.execute(
            "UPDATE test_attempts SET grade=NULL, updated_at=CURRENT_TIMESTAMP WHERE test_id=?",
            (test_id,),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
