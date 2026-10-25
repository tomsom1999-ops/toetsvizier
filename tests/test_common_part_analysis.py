import math
from pathlib import Path
import statistics
import tempfile
import unittest

from toetsanalyse.analysis import analysis_data
from toetsanalyse.database import SubjectDatabase
from toetsanalyse.results import save_score
from toetsanalyse.test_versions import create_versions, versions, assign_students, save_question_mapping


class CommonPartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = SubjectDatabase.create(Path(self.temp.name) / 'test.db', 'Natuurkunde', '2026-2027')
        self.addCleanup(self.db.close)
        c = self.db.connection
        self.test = c.execute("INSERT INTO tests(school_year_id,name,period,test_type) VALUES(1,'SE1','1','SE')").lastrowid
        self.questions = [c.execute("INSERT INTO matrix_questions(test_id,question_number,maximum_score) VALUES(?,?,2)", (self.test, str(i + 1))).lastrowid for i in range(5)]
        self.specific = c.execute("INSERT INTO matrix_questions(test_id,question_number,maximum_score) VALUES(?,'6',100)", (self.test,)).lastrowid
        c.execute("UPDATE matrix_questions SET shared_title='Gemeenschappelijke vraag ' || question_number WHERE test_id=?", (self.test,))
        create_versions(self.db, self.test, ['A', 'B'])
        self.forms = versions(self.db, self.test)
        mapping = {(form['id'], qid): (str(i + 1), None) for form in self.forms for i, qid in enumerate(self.questions)}
        mapping[self.forms[0]['id'], self.specific] = ('6', None)
        save_question_mapping(self.db, self.test, mapping)
        self.students = [c.execute('INSERT INTO students(display_name) VALUES(?)', (f'Leerling {i}',)).lastrowid for i in range(24)]
        c.executemany('INSERT INTO test_students(test_id,student_id) VALUES(?,?)', [(self.test, sid) for sid in self.students])
        c.commit()
        assign_students(self.db, self.test, {sid: self.forms[i % 2]['id'] for i, sid in enumerate(self.students)})
        self.matrix = [[float(min(2, (i // 4 + j % 2) % 3)) for j in range(5)] for i in range(24)]
        for sid, values in zip(self.students, self.matrix):
            for qid, value in zip(self.questions, values):
                save_score(self.db, self.test, sid, qid, str(value))

    def test_metrics_use_common_scores_even_when_specific_scores_are_incomplete(self):
        data = analysis_data(self.db, self.test)
        common = data['common_part']
        self.assertTrue(common['available'])
        self.assertEqual(24, common['participant_count'])
        self.assertEqual(10, common['maximum_score'])
        totals = [sum(row) for row in self.matrix]
        expected = 5 / 4 * (1 - sum(statistics.variance([row[j] for row in self.matrix]) for j in range(5)) / statistics.variance(totals))
        self.assertAlmostEqual(expected, data['quality']['alpha']['value'])
        self.assertAlmostEqual(statistics.stdev(totals) * math.sqrt(1 - expected), data['quality']['sem']['score_value'])
        self.assertAlmostEqual(data['quality']['sem']['score_value'] / 10 * 100, data['quality']['sem']['value'])
        before = [(item['rit'], item['rir']) for item in data['item_analysis']]
        for i, sid in enumerate(self.students):
            if i % 2 == 0:
                save_score(self.db, self.test, sid, self.specific, str(i * 4))
        after = analysis_data(self.db, self.test)
        self.assertEqual(before, [(item['rit'], item['rir']) for item in after['item_analysis']])
        self.assertNotIn(self.specific, after['common_part']['question_ids'])

    def test_high_points_do_not_compensate_for_too_few_independent_questions(self):
        for i, qid in enumerate(self.questions):
            self.db.execute("UPDATE matrix_questions SET question_number='1',subquestion=? WHERE id=?", (chr(97+i), qid))
        common = analysis_data(self.db, self.test)['common_part']
        self.assertEqual(1, common['unit_count'])
        self.assertFalse(common['available'])
        self.assertIsNone(common['alpha'])

    def test_missing_common_score_is_excluded_not_imputed_as_zero(self):
        save_score(self.db, self.test, self.students[0], self.questions[0], '')
        common = analysis_data(self.db, self.test)['common_part']
        self.assertEqual(23, common['participant_count'])

    def test_no_score_variation_blocks_psychometrics(self):
        self.db.execute('UPDATE scores SET score=1')
        common = analysis_data(self.db, self.test)['common_part']
        self.assertFalse(common['available'])
        self.assertIsNone(common['alpha'])
        self.assertIsNone(common['sem_score'])
        self.assertTrue(any('spreiding' in reason for reason in common['reasons']))

    def test_small_sample_blocks_correlations_and_reliability(self):
        self.db.execute("UPDATE test_attempts SET status='afwezig' WHERE student_id IN (" + ','.join('?' for _ in self.students[:6]) + ')', tuple(self.students[:6]))
        data = analysis_data(self.db, self.test)
        self.assertFalse(data['common_part']['available'])
        self.assertIsNone(data['quality']['alpha']['value'])
        self.assertTrue(all(item['rit'] is None and item['rir'] is None for item in data['item_analysis']))

    def test_negative_alpha_is_visible_but_has_no_sem(self):
        for i, sid in enumerate(self.students):
            value = i % 3
            for qid, score in zip(self.questions, [value, 2-value, value, 2-value, (i // 3) % 3]):
                save_score(self.db, self.test, sid, qid, str(score))
        common = analysis_data(self.db, self.test)['common_part']
        self.assertTrue(common['available'])
        self.assertLess(common['alpha'], 0)
        self.assertIsNone(common['sem_score'])
        self.assertIn('Alpha is negatief', common['note'])

    def test_questions_shared_by_only_some_versions_are_outside_common_part(self):
        c = self.db.connection
        third = c.execute("INSERT INTO test_versions(test_id,name) VALUES(?,'C')", (self.test,)).lastrowid
        for i, qid in enumerate(self.questions[:4]):
            c.execute('INSERT INTO version_questions(version_id,question_id,label) VALUES(?,?,?)', (third, qid, str(i+1)))
        c.commit()
        data = analysis_data(self.db, self.test)
        self.assertNotIn(self.questions[4], data['common_part']['question_ids'])
        self.assertIsNone(next(item for item in data['item_analysis'] if item['id'] == self.questions[4])['rir'])
