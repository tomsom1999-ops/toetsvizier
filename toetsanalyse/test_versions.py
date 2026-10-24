from __future__ import annotations

import json
from contextlib import nullcontext

from .database import SubjectDatabase


def versions(database: SubjectDatabase, test_id: int | None) -> list[dict]:
    if test_id is None or getattr(database, "version_source", None) is not None:
        return []
    return [dict(row) for row in database.rows("SELECT * FROM test_versions WHERE test_id=? ORDER BY id", (test_id,))]


def create_versions(database: SubjectDatabase, test_id: int, names: list[str]) -> None:
    names = [name.strip() for name in names]
    if len(names) < 2 or any(not name for name in names) or len(set(names)) != len(names):
        raise ValueError("Vul minstens twee verschillende versienamen in.")
    if versions(database, test_id):
        raise ValueError("Deze toets heeft al versies.")
    database.connection.executemany("INSERT INTO test_versions(test_id, name) VALUES(?, ?)",
                                    [(test_id, name) for name in names])


def question_references(database: SubjectDatabase, test_id: int) -> dict[int, dict]:
    chosen = {row["question_id"]:row["version_id"] for row in database.rows(
        "SELECT r.* FROM question_alternative_references r JOIN matrix_questions q ON q.id=r.question_id WHERE q.test_id=?",(test_id,))}
    result = {}
    for form in versions(database,test_id):
        for row in database.rows("SELECT * FROM version_questions WHERE version_id=?",(form["id"],)):
            if row["question_id"] not in result or chosen.get(row["question_id"]) == form["id"]:
                result[row["question_id"]] = dict(row,version_name=form["name"])
    return result


def student_version(database: SubjectDatabase, test_id: int, student_id: int) -> int | None:
    value = database.scalar("SELECT version_id FROM student_test_versions WHERE test_id=? AND student_id=?",
                            (test_id, student_id))
    return int(value) if value is not None else None


def has_results(database: SubjectDatabase, test_id: int, version_id: int) -> bool:
    return bool(database.scalar(
        "SELECT COUNT(*) FROM scores s JOIN test_attempts a ON a.id=s.attempt_id "
        "JOIN student_test_versions v ON v.test_id=a.test_id AND v.student_id=a.student_id "
        "WHERE a.test_id=? AND v.version_id=? AND (s.score IS NOT NULL OR COALESCE(s.response_text,'')<>'')",
        (test_id, version_id)))


def assign_students(database: SubjectDatabase, test_id: int, assignments: dict[int, int | None], *, commit: bool = True) -> None:
    from .results import test_students
    allowed = {int(v["id"]) for v in versions(database, test_id)}
    pupils = {int(s["id"]) for s in test_students(database, test_id)}
    for student_id, version_id in assignments.items():
        if student_id not in pupils or (version_id is not None and version_id not in allowed):
            raise ValueError("Leerling of versie hoort niet bij deze toets.")
        old = student_version(database, test_id, student_id)
        if old != version_id and database.scalar(
            "SELECT COUNT(*) FROM scores s JOIN test_attempts a ON a.id=s.attempt_id "
            "WHERE a.test_id=? AND a.student_id=? AND (s.score IS NOT NULL OR COALESCE(s.response_text,'')<>'')",
            (test_id, student_id)):
            raise ValueError("Wis eerst de resultaten van de leerling voordat u de versie wijzigt.")
    with (database.connection if commit else nullcontext(database.connection)) as connection:
        for student_id, version_id in assignments.items():
            if student_version(database, test_id, student_id) == version_id:
                continue
            connection.execute("DELETE FROM student_test_versions WHERE test_id=? AND student_id=?", (test_id, student_id))
            if version_id is not None:
                connection.execute("INSERT INTO student_test_versions VALUES(?, ?, ?)", (test_id, student_id, version_id))
            connection.execute("UPDATE test_attempts SET grade=NULL WHERE test_id=? AND student_id=?", (test_id, student_id))


def mapped_questions(database: SubjectDatabase, test_id: int, version_id: int) -> list[dict]:
    from .results import test_questions
    mapping = {int(row["question_id"]): dict(row) for row in database.rows(
        "SELECT vq.* FROM version_questions vq JOIN test_versions v ON v.id=vq.version_id "
        "WHERE v.test_id=? AND v.id=?", (test_id, version_id))}
    result = []
    for question in test_questions(database, test_id):
        if question["id"] in mapping:
            entry = mapping[question["id"]]
            question["label"] = entry["label"]
            question = apply_alternative_map(question, entry)
            result.append(question)
    import re
    return sorted(result, key=lambda q: [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", q["label"])])


def apply_alternative_map(question: dict, entry: dict) -> dict:
    question = dict(question)
    if not question.get("is_multiple_choice"):
        return question
    option_map = json.loads(entry.get("alternatives_json") or "{}")
    if option_map:
        inverse = {canonical:letter for letter,canonical in option_map.items()}
        canonical_answer = question.get("multiple_choice_answer")
        if canonical_answer not in inverse:
            raise ValueError("De antwoordsleutel ontbreekt in de alternatievenkoppeling. Controleer de toetsversies.")
        question["multiple_choice_answer"] = inverse[canonical_answer]
        from .results import normalize_multiple_choice_option_list
        extra = normalize_multiple_choice_option_list(str(question.get("multiple_choice_extra_answers") or ""))
        question["multiple_choice_extra_answers"] = ",".join(inverse.get(letter,letter) for letter in extra)
    elif entry.get("answer"):
        question["multiple_choice_answer"] = entry["answer"]
    return question


def save_question_mapping(database: SubjectDatabase, test_id: int,
                          mapping: dict[tuple[int, int], tuple[str, str | None]],
                          alternatives: dict[tuple[int, int], dict[str, str]] | None = None,
                          alternative_references: dict[int,int] | None = None,
                          titles: dict[int,str] | None = None, *, commit: bool = True) -> None:
    mapping = dict(mapping)
    version_ids = {int(v["id"]) for v in versions(database, test_id)}
    questions = {int(row["id"]): dict(row) for row in database.rows("SELECT * FROM matrix_questions WHERE test_id=?", (test_id,))}
    titles = titles if titles is not None else {qid:question["shared_title"] for qid,question in questions.items()}
    for qid in questions:
        if sum(question_id == qid for _,question_id in mapping) > 1 and not titles.get(qid,"").strip():
            raise ValueError("Geef elke gedeelde vraag een herkenbare titel.")
    if alternative_references is None:
        alternative_references = {row["question_id"]:row["version_id"] for row in database.rows(
            "SELECT r.* FROM question_alternative_references r JOIN matrix_questions q ON q.id=r.question_id WHERE q.test_id=?",(test_id,))
            if (row["version_id"],row["question_id"]) in mapping}
    if any((vid,qid) not in mapping for qid,vid in alternative_references.items()):
        raise ValueError("De referentie voor antwoordalternatieven moet een versie zijn waarin de vraag voorkomt.")
    old = {(int(row["version_id"]), int(row["question_id"])): (row["label"], row["answer"])
           for row in database.rows("SELECT vq.* FROM version_questions vq JOIN test_versions v ON v.id=vq.version_id WHERE v.test_id=?", (test_id,))}
    old_alternatives = {(int(row["version_id"]), int(row["question_id"])): json.loads(row["alternatives_json"])
                        for row in database.rows("SELECT vq.* FROM version_questions vq JOIN test_versions v ON v.id=vq.version_id WHERE v.test_id=?", (test_id,))}
    alternatives = alternatives if alternatives is not None else old_alternatives
    for key, option_map in alternatives.items():
        if key not in mapping or not option_map:
            continue
        letters = list(option_map) + list(option_map.values())
        if any(len(letter) != 1 or not letter.isascii() or not letter.isalpha() or letter != letter.upper() for letter in letters):
            raise ValueError("Gebruik één hoofdletter per alternatief.")
        if len(set(option_map.values())) != len(option_map):
            raise ValueError("Koppel elk alternatief precies één keer.")
        canonical_answer = questions[key[1]]["multiple_choice_answer"]
        if canonical_answer not in option_map.values():
            raise ValueError("De standaard antwoordsleutel ontbreekt in de alternatievenkoppeling.")
        effective_answer = next(letter for letter, canonical in option_map.items() if canonical == canonical_answer)
        label, _ = mapping[key]
        mapping[key] = (label, effective_answer)
    for qid in questions:
        maps = [option_map for (vid, question_id), option_map in alternatives.items() if question_id == qid and (vid,qid) in mapping and option_map]
        if maps and any(set(option_map.values()) != set(maps[0].values()) for option_map in maps):
            raise ValueError("Gebruik voor een gedeelde vraag dezelfde basisalternatieven in alle versies.")
    labels = set()
    for (version_id, question_id), (label, answer) in mapping.items():
        if version_id not in version_ids or question_id not in questions or not label.strip():
            raise ValueError("Vul voor elke aangevinkte versie een vraagnummer in.")
        if (version_id, label.strip()) in labels:
            raise ValueError(f"Vraagnummer {label} komt tweemaal voor in dezelfde versie.")
        labels.add((version_id, label.strip()))
        if answer and (len(answer) != 1 or not answer.isascii() or not answer.isalpha() or not questions[question_id]["is_multiple_choice"]):
            raise ValueError("De afwijkende antwoordsleutel moet één letter zijn bij een meerkeuzevraag.")
    for version_id in version_ids:
        before = {qid for vid, qid in old if vid == version_id}
        after = {qid for vid, qid in mapping if vid == version_id}
        if before != after and has_results(database, test_id, version_id):
            raise ValueError("Vragen toevoegen of verwijderen kan pas nadat alle resultaten van deze versie zijn gewist.")
        for key in before & after:
            if old[version_id, key][1] != mapping[version_id, key][1] and has_results(database, test_id, version_id):
                raise ValueError("Wis eerst de resultaten van deze versie voordat u de afwijkende antwoordsleutel wijzigt.")
            if old_alternatives.get((version_id,key), {}) != alternatives.get((version_id,key), {}) and has_results(database,test_id,version_id):
                raise ValueError("Wis eerst de resultaten van deze versie voordat u alternatieven opnieuw koppelt.")
    with (database.connection if commit else nullcontext(database.connection)) as connection:
        for version_id in version_ids:
            connection.execute("DELETE FROM version_questions WHERE version_id=?", (version_id,))
        connection.executemany("INSERT INTO version_questions(version_id,question_id,label,answer,alternatives_json) VALUES(?, ?, ?, ?, ?)",
                               [(vid, qid, label.strip(), answer.upper() if answer else None, json.dumps(alternatives.get((vid,qid), {})))
                                for (vid, qid), (label, answer) in mapping.items()])
        for qid in questions:
            connection.execute("UPDATE matrix_questions SET shared_title=? WHERE id=?",(titles.get(qid,questions[qid]["shared_title"]).strip(),qid))
            connection.execute("DELETE FROM question_alternative_references WHERE question_id=?",(qid,))
            if qid in alternative_references:
                connection.execute("INSERT INTO question_alternative_references VALUES(?,?)",(qid,alternative_references[qid]))


def project_version(database: SubjectDatabase, test_id: int, version_id: int) -> SubjectDatabase:
    """Isolated read model lets existing analysis and norming use only this form."""
    version = next((v for v in versions(database, test_id) if v["id"] == version_id), None)
    if version is None:
        raise ValueError("Kies een geldige toetsversie.")
    database.connection.commit()
    projected = SubjectDatabase(":memory:")
    database.connection.backup(projected.connection)
    connection = projected.connection
    connection.execute("DROP TRIGGER IF EXISTS protect_version_question_deletion")
    connection.execute("DROP TRIGGER IF EXISTS protect_version_question_structure")
    connection.execute("PRAGMA foreign_keys=OFF")
    mapped = mapped_questions(database, test_id, version_id)
    keep = {q["id"] for q in mapped}
    for row in connection.execute("SELECT id FROM matrix_questions WHERE test_id=?", (test_id,)).fetchall():
        if row["id"] not in keep:
            connection.execute("DELETE FROM scores WHERE question_id=?", (row["id"],))
            connection.execute("DELETE FROM matrix_questions WHERE id=?", (row["id"],))
    # Avoid transient uniqueness collisions when numbering is swapped.
    connection.execute("UPDATE matrix_questions SET question_number='__version_' || id, subquestion=NULL WHERE test_id=?", (test_id,))
    for q in mapped:
        import re
        parts = re.fullmatch(r"(\d+)([A-Za-z]+)", q["label"])
        number, subquestion = (parts.group(1), parts.group(2)) if parts else (q["label"], None)
        connection.execute("UPDATE matrix_questions SET question_number=?, subquestion=?, multiple_choice_answer=?, multiple_choice_extra_answers=? WHERE id=?",
                           (number, subquestion, q["multiple_choice_answer"], q.get("multiple_choice_extra_answers"), q["id"]))
    connection.execute("DELETE FROM test_attempts WHERE test_id=? AND student_id NOT IN "
                       "(SELECT student_id FROM student_test_versions WHERE test_id=? AND version_id=?)", (test_id, test_id, version_id))
    connection.execute("DELETE FROM test_classes WHERE test_id=?", (test_id,))
    connection.execute("DELETE FROM test_students WHERE test_id=?", (test_id,))
    connection.execute("INSERT INTO test_students(test_id,student_id) SELECT test_id,student_id FROM student_test_versions WHERE test_id=? AND version_id=?", (test_id,version_id))
    connection.execute("DELETE FROM normalizations WHERE test_id=?", (test_id,))
    if version["normalization_json"]:
        settings = json.loads(version["normalization_json"])
        connection.execute("INSERT INTO normalizations(test_id,method,configuration_json,decimal_places,rounding_method) VALUES(?,?,?,?,?)",
                           (test_id, settings["method"], json.dumps(settings), settings.get("decimal_places", 1), settings.get("rounding_method", "standaard")))
    connection.execute("UPDATE tests SET name=name || ' — ' || ? WHERE id=?", (version["name"], test_id))
    connection.commit()
    projected.version_source = database
    projected.version_id = version_id
    return projected


def persist_normalization(database: SubjectDatabase, test_id: int, settings: dict | None) -> None:
    source = getattr(database, "version_source", None)
    if source is None:
        return
    with source.connection as connection:
        connection.execute("UPDATE test_versions SET normalization_json=? WHERE id=?", (json.dumps(settings) if settings else None, database.version_id))
        for row in database.rows("SELECT id, grade FROM test_attempts WHERE test_id=?", (test_id,)):
            connection.execute("UPDATE test_attempts SET grade=? WHERE id=?", (row["grade"], row["id"]))


def refresh_version_grade(database: SubjectDatabase, test_id: int, student_id: int) -> None:
    """Keep saved grades current after editing a score; incomplete attempts have no grade."""
    version_id = student_version(database, test_id, student_id)
    if version_id is None:
        return
    settings_json = database.scalar("SELECT normalization_json FROM test_versions WHERE id=?", (version_id,))
    questions = mapped_questions(database, test_id, version_id)
    attempt = database.rows("SELECT id, status, total_score FROM test_attempts WHERE test_id=? AND student_id=?", (test_id,student_id))
    if not attempt:
        return
    attempt = attempt[0]
    count = database.scalar("SELECT COUNT(*) FROM scores s JOIN version_questions vq ON vq.question_id=s.question_id "
                            "WHERE s.attempt_id=? AND vq.version_id=? AND s.score IS NOT NULL", (attempt["id"],version_id))
    maximum = sum(float(q["maximum_score"]) for q in questions)
    grade = None
    if settings_json and maximum > 0 and count == len(questions) and attempt["status"] == "gemaakt" and attempt["total_score"] is not None:
        from .norming import calculate_grade
        grade = calculate_grade(float(attempt["total_score"]), maximum, json.loads(settings_json))
    database.connection.execute("UPDATE test_attempts SET grade=? WHERE id=?", (grade,attempt["id"]))
