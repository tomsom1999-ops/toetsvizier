import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from toetsanalyse.database import SubjectDatabase
from toetsanalyse.importers import (
    StudentImportError,
    import_results,
    import_students,
    preview_results_import,
    read_magister_students,
    read_results_rows,
    suggest_results_mapping,
)


class MagisterImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        directory = Path(self.temporary_directory.name)
        self.database = SubjectDatabase.create(directory / "natuurkunde.db", "Natuurkunde", "2025-2026")
        self.year_id = self.database.scalar("SELECT id FROM school_years LIMIT 1")
        self.database.execute(
            "INSERT INTO classes(school_year_id, name, level, grade_year) VALUES(?, ?, ?, ?)",
            (self.year_id, "H4A", "havo", "4"),
        )
        self.class_id = self.database.scalar("SELECT id FROM classes WHERE name='H4A'")
        self.excel_path = directory / "magister.xlsx"
        self.results_csv_path = directory / "resultaten.csv"

    def tearDown(self) -> None:
        self.database.close()
        self.temporary_directory.cleanup()

    def make_excel(self, rows: list[tuple[object, ...]], headers=None, leading_rows=None) -> None:
        workbook = Workbook()
        sheet = workbook.active
        for leading_row in leading_rows or []:
            sheet.append(leading_row)
        sheet.append(headers or ["Stamnummer", "Roepnaam", "Tussenvoegsel", "Achternaam"])
        for row in rows:
            sheet.append(row)
        workbook.save(self.excel_path)

    def test_magister_excel_import_builds_names_and_class_enrollment(self) -> None:
        self.make_excel([(12345, "Mila", "de", "Vries"), (67890, "Sam", "", "Jansen")])

        students, skipped = read_magister_students(self.excel_path)
        result = import_students(self.database, self.year_id, self.class_id, students, skipped)

        self.assertEqual((2, 0, 0), (result.added, result.updated, result.skipped))
        names = self.database.rows(
            "SELECT s.display_name, c.name FROM students s JOIN enrollments e ON e.student_id=s.id "
            "JOIN classes c ON c.id=e.class_id ORDER BY s.display_name"
        )
        self.assertEqual([("Mila de Vries", "H4A"), ("Sam Jansen", "H4A")], [tuple(row) for row in names])

    def test_second_import_updates_matching_stamnummer(self) -> None:
        self.make_excel([(12345, "Mila", "de", "Vries")])
        students, skipped = read_magister_students(self.excel_path)
        import_students(self.database, self.year_id, self.class_id, students, skipped)
        self.make_excel([(12345, "Amelia", "de", "Vries")])

        students, skipped = read_magister_students(self.excel_path)
        result = import_students(self.database, self.year_id, self.class_id, students, skipped)

        self.assertEqual((0, 1), (result.added, result.updated))
        self.assertEqual(1, self.database.scalar("SELECT COUNT(*) FROM students"))
        self.assertEqual("Amelia de Vries", self.database.scalar("SELECT display_name FROM students"))

    def test_export_with_heading_on_row_four_ignores_magister_class(self) -> None:
        self.make_excel(
            [(12345, "Mila", "de", "Vries", "H4X", "mila@example.nl")],
            headers=["Stamnummer", "Roepnaam", "Tussenvoegsel", "Achternaam", "Klas", "Email"],
            leading_rows=[("Leerlingen",), ("Lesperiode:", "2025-2026"), ()],
        )

        students, skipped = read_magister_students(self.excel_path)
        result = import_students(self.database, self.year_id, self.class_id, students, skipped)

        imported = self.database.rows(
            "SELECT s.display_name, s.email, c.name FROM students s "
            "JOIN enrollments e ON e.student_id=s.id JOIN classes c ON c.id=e.class_id"
        )[0]
        self.assertEqual((1, 0), (result.added, result.skipped))
        self.assertEqual(("Mila de Vries", "mila@example.nl", "H4A"), tuple(imported))
        self.assertEqual(1, self.database.scalar("SELECT COUNT(*) FROM classes"))

    def test_import_requires_magister_headers(self) -> None:
        self.make_excel([("Mila", "de Vries")], headers=["Voornaam", "Naam"])

        with self.assertRaises(StudentImportError):
            read_magister_students(self.excel_path)

    def test_total_row_is_not_imported_or_counted_as_invalid(self) -> None:
        self.make_excel(
            [("Totaal", "", "", ""), (12345, "Mila", "de", "Vries")],
            leading_rows=[("Leerlingen",), ("Lesperiode:", "2025-2026"), ()],
        )

        students, skipped = read_magister_students(self.excel_path)

        self.assertEqual(1, len(students))
        self.assertEqual(0, skipped)
        self.assertEqual("Mila de Vries", students[0].display_name)

    def test_same_stamnummer_in_new_year_keeps_one_student_identity(self) -> None:
        self.make_excel([(12345, "Mila", "de", "Vries")])
        students, skipped = read_magister_students(self.excel_path)
        import_students(self.database, self.year_id, self.class_id, students, skipped)
        self.database.add_school_year("2026-2027")
        next_year_id = self.database.scalar("SELECT id FROM school_years WHERE name='2026-2027'")
        self.database.execute(
            "INSERT INTO classes(school_year_id, name, level, grade_year) VALUES(?, ?, ?, ?)",
            (next_year_id, "Cluster B", "havo", "5"),
        )
        next_class_id = self.database.scalar("SELECT id FROM classes WHERE name='Cluster B'")

        result = import_students(self.database, next_year_id, next_class_id, students, skipped)

        self.assertEqual((0, 1), (result.added, result.updated))
        self.assertEqual(1, self.database.scalar("SELECT COUNT(*) FROM students"))
        self.assertEqual(2, self.database.scalar("SELECT COUNT(*) FROM enrollments"))

    def test_results_import_supports_csv_auto_mapping_and_preview(self) -> None:
        self.make_excel([(12345, "Mila", "de", "Vries")])
        students, skipped = read_magister_students(self.excel_path)
        import_students(self.database, self.year_id, self.class_id, students, skipped)
        self.database.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
            (self.year_id, "SO1", "Toetsweek 1", "SO"),
        )
        test_id = self.database.scalar("SELECT id FROM tests WHERE name='SO1'")
        self.database.execute("INSERT INTO test_classes(test_id, class_id) VALUES(?, ?)", (test_id, self.class_id))
        self.database.execute(
            "INSERT INTO matrix_questions(test_id, question_number, maximum_score) VALUES(?, ?, ?)",
            (test_id, "1", 4),
        )
        self.database.execute(
            "INSERT INTO matrix_questions(test_id, question_number, maximum_score) VALUES(?, ?, ?)",
            (test_id, "2", 6),
        )
        self.results_csv_path.write_text(
            "Leerlingnummer,Status,V1,V2\n12345,gemaakt,3,5\n",
            encoding="utf-8",
        )
        headers, rows = read_results_rows(self.results_csv_path)
        questions = [dict(row) for row in self.database.rows(
            "SELECT id, question_number || COALESCE(subquestion, '') AS label, maximum_score FROM matrix_questions WHERE test_id=? ORDER BY id",
            (test_id,),
        )]
        mapping = suggest_results_mapping(headers, questions)
        checked = preview_results_import(self.database, test_id, rows, mapping)
        summary = import_results(self.database, test_id, rows, mapping, allow_half_points=False)
        attempt = self.database.rows("SELECT status, total_score FROM test_attempts WHERE test_id=?", (test_id,))[0]

        self.assertEqual(1, checked["matched_rows"])
        self.assertEqual(2, checked["score_cells"])
        self.assertEqual((2, 0, 1, 0), (summary.updated_scores, summary.cleared_scores, summary.status_updates, summary.skipped_rows))
        self.assertEqual(("gemaakt", 8.0), tuple(attempt))

    def test_results_import_reads_semicolon_csv(self) -> None:
        self.results_csv_path.write_text(
            "Leerlingnummer;Status;V1\n12345;gemaakt;3\n",
            encoding="utf-8",
        )

        headers, rows = read_results_rows(self.results_csv_path)

        self.assertEqual(["Leerlingnummer", "Status", "V1"], headers)
        self.assertEqual("gemaakt", rows[0]["Status"])
        self.assertEqual("3", rows[0]["V1"])

    def test_results_import_rejects_duplicate_headers(self) -> None:
        self.results_csv_path.write_text(
            "Leerlingnummer,V1,V 1\n12345,3,4\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(Exception, "Dubbele kolomnamen"):
            read_results_rows(self.results_csv_path)

    def test_preview_checks_all_rows_for_unmatched_students_and_invalid_statuses(self) -> None:
        self.make_excel([(12345, "Mila", "de", "Vries")])
        students, skipped = read_magister_students(self.excel_path)
        import_students(self.database, self.year_id, self.class_id, students, skipped)
        self.database.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
            (self.year_id, "SO all rows", "Toetsweek 1", "SO"),
        )
        test_id = self.database.scalar("SELECT id FROM tests WHERE name='SO all rows'")
        self.database.execute(
            "INSERT INTO matrix_questions(test_id, question_number, maximum_score) VALUES(?, ?, ?)",
            (test_id, "1", 4),
        )
        question_id = self.database.scalar("SELECT id FROM matrix_questions WHERE test_id=?", (test_id,))
        good_rows = ["12345,gemaakt,3" for _ in range(25)]
        self.results_csv_path.write_text(
            "Leerlingnummer,Status,V1\n" + "\n".join(good_rows + ["99999,afwezig door excursie,2"]) + "\n",
            encoding="utf-8",
        )
        headers, rows = read_results_rows(self.results_csv_path)
        mapping = {
            "student_number": "Leerlingnummer",
            "student_name": None,
            "status": "Status",
            "questions": {question_id: "V1"},
        }

        checked = preview_results_import(self.database, test_id, rows, mapping)

        self.assertEqual(25, checked["matched_rows"])
        self.assertEqual(1, checked["unknown_students"])
        self.assertEqual(1, len(checked["invalid_statuses"]))
        self.assertEqual("27", checked["invalid_statuses"][0]["row"])

    def test_results_import_allows_manual_mapping_when_headers_are_unusual(self) -> None:
        self.make_excel([(999, "Sam", "", "Jansen")])
        students, skipped = read_magister_students(self.excel_path)
        import_students(self.database, self.year_id, self.class_id, students, skipped)
        self.database.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
            (self.year_id, "SO2", "Toetsweek 1", "SO"),
        )
        test_id = self.database.scalar("SELECT id FROM tests WHERE name='SO2'")
        self.database.execute("INSERT INTO test_classes(test_id, class_id) VALUES(?, ?)", (test_id, self.class_id))
        self.database.execute(
            "INSERT INTO matrix_questions(test_id, question_number, maximum_score) VALUES(?, ?, ?)",
            (test_id, "1", 4),
        )
        question_id = self.database.scalar("SELECT id FROM matrix_questions WHERE test_id=? LIMIT 1", (test_id,))
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["ID", "Q_1"])
        sheet.append([999, 4])
        workbook.save(self.excel_path)
        headers, rows = read_results_rows(self.excel_path)
        mapping = {
            "student_number": "ID",
            "student_name": None,
            "status": None,
            "questions": {question_id: "Q_1"},
        }
        summary = import_results(self.database, test_id, rows, mapping, allow_half_points=False)
        stored = self.database.scalar(
            "SELECT s.score FROM scores s JOIN test_attempts a ON a.id=s.attempt_id WHERE a.test_id=?",
            (test_id,),
        )

        self.assertEqual((1, 0, 0, 0), (summary.updated_scores, summary.cleared_scores, summary.status_updates, summary.skipped_rows))
        self.assertEqual(4.0, stored)

    def test_results_import_rolls_back_completely_when_one_score_is_invalid(self) -> None:
        self.make_excel([(111, "Mila", "", "Vries"), (222, "Sam", "", "Jansen")])
        students, skipped = read_magister_students(self.excel_path)
        import_students(self.database, self.year_id, self.class_id, students, skipped)
        self.database.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
            (self.year_id, "SO rollback", "Toetsweek 1", "SO"),
        )
        test_id = self.database.scalar("SELECT id FROM tests WHERE name='SO rollback'")
        self.database.execute("INSERT INTO test_classes(test_id, class_id) VALUES(?, ?)", (test_id, self.class_id))
        self.database.execute(
            "INSERT INTO matrix_questions(test_id, question_number, maximum_score) VALUES(?, ?, ?)",
            (test_id, "1", 4),
        )
        question_id = self.database.scalar("SELECT id FROM matrix_questions WHERE test_id=?", (test_id,))
        self.results_csv_path.write_text(
            "Leerlingnummer,V1\n111,3\n222,9\n",
            encoding="utf-8",
        )
        headers, rows = read_results_rows(self.results_csv_path)
        mapping = {"student_number": "Leerlingnummer", "student_name": None, "status": None, "questions": {question_id: "V1"}}

        with self.assertRaises(Exception):
            import_results(self.database, test_id, rows, mapping, allow_half_points=False)

        self.assertEqual(0, self.database.scalar("SELECT COUNT(*) FROM test_attempts WHERE test_id=?", (test_id,)))
        self.assertEqual(
            0,
            self.database.scalar(
                "SELECT COUNT(*) FROM scores s JOIN test_attempts a ON a.id=s.attempt_id WHERE a.test_id=?",
                (test_id,),
            ),
        )


if __name__ == "__main__":
    unittest.main()
