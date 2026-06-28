import unittest

from toetsanalyse.name_sorting import sortable_last_name, student_sort_key


class NameSortingTests(unittest.TestCase):
    def test_dutch_prefixes_do_not_determine_surname_order(self) -> None:
        names = [
            {"display_name": "Jordi van Roij", "first_name": "Jordi", "last_name": "van Roij"},
            {"display_name": "Noor de Vries", "first_name": "Noor", "last_name": "de Vries"},
            {"display_name": "Anne Bakker", "first_name": "Anne", "last_name": "Bakker"},
            {"display_name": "Mila van der Meer", "first_name": "Mila", "last_name": "van der Meer"},
        ]

        ordered = sorted(names, key=lambda item: student_sort_key(item["display_name"], item["first_name"], item["last_name"]))

        self.assertEqual(
            ["Anne Bakker", "Mila van der Meer", "Jordi van Roij", "Noor de Vries"],
            [item["display_name"] for item in ordered],
        )

    def test_display_name_fallback_still_ignores_prefix_before_final_surname(self) -> None:
        self.assertEqual("Meer", sortable_last_name("", "Mila van der Meer"))


if __name__ == "__main__":
    unittest.main()
