import tempfile
import unittest
from pathlib import Path

from toetsanalyse.database import SubjectDatabase
from toetsanalyse.results import save_score, regrade_multiple_choice_question, ResultValidationError
from toetsanalyse.test_versions import (create_versions, versions, assign_students, mapped_questions,
                                       save_question_mapping, project_version, student_version)
from toetsanalyse.analysis import analysis_data
from toetsanalyse.norming import maximum_score, save_normalization, load_normalization, has_active_normalization


class TestVersions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = SubjectDatabase.create(Path(self.temp.name) / "test.db", "Wiskunde", "2026-2027")
        c = self.db.connection
        self.test_id = c.execute("INSERT INTO tests(school_year_id,name,period,test_type) VALUES(1,'Toets','1','SO')").lastrowid
        self.pupils = [c.execute("INSERT INTO students(display_name) VALUES(?)", (name,)).lastrowid for name in ("Ada", "Bo", "Cato")]
        c.executemany("INSERT INTO test_students(test_id,student_id) VALUES(?,?)", [(self.test_id, sid) for sid in self.pupils])
        self.shared = c.execute("INSERT INTO matrix_questions(test_id,question_number,maximum_score,is_multiple_choice,multiple_choice_answer) VALUES(?,'1',2,1,'A')", (self.test_id,)).lastrowid
        self.specific = c.execute("INSERT INTO matrix_questions(test_id,question_number,maximum_score) VALUES(?,'2',4)", (self.test_id,)).lastrowid
        c.execute("UPDATE matrix_questions SET shared_title='Snelheid berekenen' WHERE id=?",(self.shared,))
        create_versions(self.db, self.test_id, ["A", "B", "C"])
        self.a, self.b, self.c = [v["id"] for v in versions(self.db, self.test_id)]
        self.mapping = {(self.a,self.shared): ('3a',None), (self.b,self.shared): ('7b','C'), (self.c,self.shared): ('2',None), (self.b,self.specific): ('1',None)}
        self.db.connection.commit()
        save_question_mapping(self.db, self.test_id, self.mapping)
        assign_students(self.db, self.test_id, dict(zip(self.pupils,[self.a,self.b,self.c])))

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def fill(self):
        save_score(self.db,self.test_id,self.pupils[0],self.shared,'A')
        save_score(self.db,self.test_id,self.pupils[1],self.shared,'C')
        save_score(self.db,self.test_id,self.pupils[1],self.specific,'3')
        save_score(self.db,self.test_id,self.pupils[2],self.shared,'B')

    def test_scoring_respects_version_membership_and_answer(self):
        self.fill()
        with self.assertRaises(ResultValidationError):
            save_score(self.db,self.test_id,self.pupils[0],self.specific,'1')
        self.assertEqual(['1','7b'], [q['label'] for q in mapped_questions(self.db,self.test_id,self.b)])
        regrade_multiple_choice_question(self.db,self.test_id,self.shared)
        self.assertEqual(2, self.db.scalar("SELECT s.score FROM scores s JOIN test_attempts a ON a.id=s.attempt_id WHERE a.student_id=? AND s.question_id=?", (self.pupils[1],self.shared)))

    def test_assignment_is_atomic_and_blocked_until_scores_erased(self):
        self.fill()
        with self.assertRaises(ValueError):
            assign_students(self.db,self.test_id,{self.pupils[0]:self.b,self.pupils[2]:self.a})
        self.assertEqual(self.c,student_version(self.db,self.test_id,self.pupils[2]))
        save_score(self.db,self.test_id,self.pupils[0],self.shared,'')
        assign_students(self.db,self.test_id,{self.pupils[0]:self.b})
        self.assertEqual(self.b,student_version(self.db,self.test_id,self.pupils[0]))

    def test_mapping_locks_membership_but_allows_renumbering(self):
        self.fill()
        changed = dict(self.mapping)
        changed[self.a,self.shared] = ('19c',None)
        save_question_mapping(self.db,self.test_id,changed)
        changed.pop((self.b,self.specific))
        with self.assertRaises(ValueError):
            save_question_mapping(self.db,self.test_id,changed)
        self.assertEqual('19c',mapped_questions(self.db,self.test_id,self.a)[0]['label'])

    def test_norming_persists_separately_and_projection_leaves_source_untouched(self):
        self.fill()
        for vid, maximum, nterm in ((self.a,2,1.0),(self.b,6,1.5)):
            projected = project_version(self.db,self.test_id,vid)
            try:
                self.assertEqual(maximum,maximum_score(projected,self.test_id))
                save_normalization(projected,self.test_id,{'method':'n_term','n_term':nterm})
            finally:
                projected.close()
        projected = project_version(self.db,self.test_id,self.a)
        try:
            self.assertEqual(1.0,load_normalization(projected,self.test_id)['n_term'])
            self.assertTrue(has_active_normalization(projected,self.test_id))
        finally:
            projected.close()
        self.assertEqual(2,self.db.scalar('SELECT COUNT(*) FROM matrix_questions'))
        self.assertEqual(3,self.db.scalar('SELECT COUNT(*) FROM test_attempts'))

    def test_analysis_per_version_and_pooled_question_counts(self):
        self.fill()
        per_version = analysis_data(self.db,self.test_id,version_id=self.b)
        self.assertEqual(1,per_version['participant_count'])
        self.assertEqual(6,per_version['maximum_score'])
        combined = analysis_data(self.db,self.test_id)
        self.assertEqual(3,combined['participant_count'])
        items = {i['id']:i for i in combined['item_analysis']}
        self.assertEqual(3,items[self.shared]['participant_count'])
        self.assertAlmostEqual(2/3,items[self.shared]['p_value'])
        self.assertEqual(1,items[self.specific]['participant_count'])
        self.assertEqual(.75,items[self.specific]['p_value'])

    def test_question_can_be_shared_by_only_two_forms(self):
        self.mapping.pop((self.c,self.shared))
        save_question_mapping(self.db,self.test_id,self.mapping)
        self.assertEqual([],mapped_questions(self.db,self.test_id,self.c))
        with self.assertRaises(ResultValidationError):
            save_score(self.db,self.test_id,self.pupils[2],self.shared,'A')

    def test_delete_unanswered_question_is_blocked_if_its_form_has_other_results(self):
        import sqlite3
        save_score(self.db,self.test_id,self.pupils[1],self.shared,'C')
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.connection.execute('DELETE FROM matrix_questions WHERE id=?',(self.specific,))
        self.db.connection.rollback()

    def test_distractors_are_pooled_by_content_not_display_letter(self):
        identity = {'A':'A','B':'B','C':'C','D':'D'}
        shuffled = {'A':'B','B':'D','C':'A','D':'C'}
        option_maps = {(self.a,self.shared):identity,(self.b,self.shared):shuffled,(self.c,self.shared):identity}
        save_question_mapping(self.db,self.test_id,dict(self.mapping),option_maps)
        save_score(self.db,self.test_id,self.pupils[0],self.shared,'B')
        save_score(self.db,self.test_id,self.pupils[1],self.shared,'A')
        save_score(self.db,self.test_id,self.pupils[1],self.specific,'4')
        save_score(self.db,self.test_id,self.pupils[2],self.shared,'A')
        mc = analysis_data(self.db,self.test_id)['multiple_choice']['items']
        self.assertEqual(1,len(mc))
        counts = {entry['option']:entry['count'] for entry in mc[0]['responses']}
        self.assertEqual({'A':1,'B':2,'C':0,'D':0},counts)
        self.assertEqual(3,mc[0]['participant_count'])
        self.assertEqual(1,mc[0]['correct_count'])
        per_version = analysis_data(self.db,self.test_id,version_id=self.b)
        self.assertEqual('C',per_version['multiple_choice']['items'][0]['answer_key'])
        with self.assertRaises(ResultValidationError):
            save_score(self.db,self.test_id,self.pupils[1],self.shared,'E')

    def test_alternative_mapping_requires_unique_content_and_cannot_change_after_scores(self):
        identity = {'A':'A','B':'B','C':'C','D':'D'}
        with self.assertRaises(ValueError):
            save_question_mapping(self.db,self.test_id,dict(self.mapping),{(self.a,self.shared):{'A':'A','B':'A'}})
        maps = {(self.a,self.shared):identity}
        save_question_mapping(self.db,self.test_id,dict(self.mapping),maps)
        save_score(self.db,self.test_id,self.pupils[0],self.shared,'B')
        maps[self.a,self.shared] = {'A':'A','B':'C','C':'B','D':'D'}
        with self.assertRaises(ValueError):
            save_question_mapping(self.db,self.test_id,dict(self.mapping),maps)

    def test_shared_titles_and_per_question_alternative_reference(self):
        identity = {'A':'A','B':'B','C':'C','D':'D'}
        shuffled = {'A':'B','B':'D','C':'A','D':'C'}
        maps = {(self.a,self.shared):identity,(self.b,self.shared):shuffled,(self.c,self.shared):identity}
        save_question_mapping(self.db,self.test_id,dict(self.mapping),maps,
                              alternative_references={self.shared:self.b})
        save_score(self.db,self.test_id,self.pupils[0],self.shared,'B')
        save_score(self.db,self.test_id,self.pupils[1],self.shared,'A')
        save_score(self.db,self.test_id,self.pupils[1],self.specific,'4')
        save_score(self.db,self.test_id,self.pupils[2],self.shared,'A')
        data = analysis_data(self.db,self.test_id)
        question = next(item for item in data['item_analysis'] if item['id'] == self.shared)
        self.assertIn('Snelheid berekenen',question['display_label'])
        self.assertIn('A: 3a',question['display_label'])
        mc = data['multiple_choice']['items'][0]
        self.assertEqual('B',mc['reference_version'])
        self.assertEqual('C',mc['answer_key'])
        self.assertEqual(2,next(entry['count'] for entry in mc['responses'] if entry['option']=='A'))
        correct = next(entry for entry in mc['responses'] if entry['option']=='C')
        self.assertTrue(correct['accepted'])
        self.assertIn({'version':'A','option':'A'},correct['version_options'])
        with self.assertRaises(ValueError):
            save_question_mapping(self.db,self.test_id,dict(self.mapping),maps,titles={self.shared:''})

    def test_grades_refresh_after_score_edit_and_clear(self):
        self.fill()
        projected = project_version(self.db,self.test_id,self.b)
        save_normalization(projected,self.test_id,{'method':'n_term','n_term':1.0})
        projected.close()
        save_score(self.db,self.test_id,self.pupils[1],self.specific,'4')
        self.assertEqual(10,self.db.scalar('SELECT grade FROM test_attempts WHERE student_id=?',(self.pupils[1],)))
        save_score(self.db,self.test_id,self.pupils[1],self.specific,'')
        self.assertIsNone(self.db.scalar('SELECT grade FROM test_attempts WHERE student_id=?',(self.pupils[1],)))

    def test_import_skips_other_versions_and_exports_only_selected_form(self):
        try:
            from openpyxl import load_workbook
        except ModuleNotFoundError:
            self.skipTest('openpyxl ontbreekt')
        from toetsanalyse.importers import import_results, preview_results_import
        from toetsanalyse.results import export_scores_xlsx
        mapping = {'student_name':'Naam','questions':{self.shared:'Vraag'}}
        rows = [{'Naam':'Ada','Vraag':'A'},{'Naam':'Bo','Vraag':'C'}]
        preview = preview_results_import(self.db,self.test_id,rows,mapping,version_id=self.b)
        self.assertEqual(1,preview['matched_rows'])
        imported = import_results(self.db,self.test_id,rows,mapping,version_id=self.b)
        self.assertEqual(1,imported.skipped_rows)
        self.assertEqual(1,imported.updated_scores)
        self.assertEqual(1,self.db.scalar('SELECT COUNT(*) FROM test_attempts'))
        output = Path(self.temp.name)/'B.xlsx'
        export_scores_xlsx(self.db,self.test_id,output,version_id=self.b)
        workbook = load_workbook(output,data_only=True)
        try:
            sheet = workbook['Scores']
            self.assertEqual(['1 / 4','7b / 2','Totaal / 6'],[cell.value for cell in sheet[4]][4:])
            self.assertEqual('Bo',sheet['B5'].value)
            self.assertIsNone(sheet['B6'].value)
        finally:
            workbook.close()

    def test_version_ui_scopes_results_analysis_and_norming(self):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        try:
            from PySide6.QtWidgets import QApplication
            from toetsanalyse.app import TestDialog, NormingPage
            from toetsanalyse.results_page import ResultsPage
            from toetsanalyse.analysis_page import AnalysisPage
            from toetsanalyse.version_dialog import VersionDialog
        except ModuleNotFoundError:
            self.skipTest('PySide6 ontbreekt')
        app = QApplication.instance() or QApplication([])
        self.fill()
        dialog = TestDialog([],allow_versions=False)
        self.assertTrue(dialog.use_versions.isHidden())
        enabled = TestDialog([],allow_versions=True)
        self.assertFalse(enabled.use_versions.isHidden())
        manager = VersionDialog(self.db,self.test_id)
        self.assertEqual(3,len(manager.student_choices))
        results = ResultsPage(self.db,1)
        results.select_test(self.test_id)
        results.version.setCurrentIndex(results.version.findData(self.b))
        self.assertEqual(['1','7b'],[q['label'] for q in results.questions])
        self.assertEqual([self.pupils[1]],[s['id'] for s in results.all_students])
        norming = NormingPage(self.db,1)
        norming.select_test(self.test_id)
        norming.version.setCurrentIndex(norming.version.findData(self.b))
        self.assertEqual(6,maximum_score(norming.norming_database(),self.test_id))
        analysis = AnalysisPage(self.db,1)
        analysis.select_test(self.test_id)
        self.assertEqual(4,analysis.version.count())
        if norming._version_projection is not None:
            norming._version_projection.close()
        for widget in (dialog,enabled,manager,results,norming,analysis):
            widget.close()
        app.processEvents()

    def test_question_entry_has_shared_title_and_alternative_reference_controls(self):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        try:
            from PySide6.QtWidgets import QApplication
            from toetsanalyse.question_dialogs import QuestionDialog
            from toetsanalyse.version_dialog import NewQuestionVersionFields, AlternativeMappingDialog
        except ModuleNotFoundError:
            self.skipTest('PySide6 ontbreekt')
        app = QApplication.instance() or QApplication([])
        dialog = QuestionDialog([],[],default_number='3')
        fields = NewQuestionVersionFields(self.db,self.test_id,dialog)
        fields.title.setText('Energie behouden')
        self.assertTrue(fields.validate())
        qid = self.db.connection.execute("INSERT INTO matrix_questions(test_id,question_number,maximum_score) VALUES(?,'3',1)",(self.test_id,)).lastrowid
        fields.save({qid})
        self.assertEqual('Energie behouden',self.db.scalar('SELECT shared_title FROM matrix_questions WHERE id=?',(qid,)))
        self.assertEqual(3,self.db.scalar('SELECT COUNT(*) FROM version_questions WHERE question_id=?',(qid,)))
        forms = [(self.a,'A'),(self.b,'B')]
        editor = AlternativeMappingDialog(forms,{},'A',reference_version_id=self.b)
        editor.accept()
        self.assertEqual(self.b,editor.reference.currentData())
        self.assertEqual({'A':'A','B':'B','C':'C','D':'D'},editor.option_maps[self.b])
        dialog.close()
        editor.close()
        app.processEvents()

    def qt(self):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        try:
            from PySide6.QtWidgets import QApplication
        except ModuleNotFoundError:
            self.skipTest('PySide6 ontbreekt')
        self._qt_app = QApplication.instance() or QApplication([])

    def configure_option_maps(self):
        identity = {'A':'A','B':'B','C':'C','D':'D'}
        shuffled = {'A':'B','B':'D','C':'A','D':'C'}
        save_question_mapping(self.db,self.test_id,self.mapping,
                              {(self.a,self.shared):identity,(self.b,self.shared):shuffled,(self.c,self.shared):identity})

    def test_question_kind_shows_only_relevant_version_fields(self):
        self.qt()
        from toetsanalyse.question_dialogs import QuestionDialog
        from toetsanalyse.version_dialog import NewQuestionVersionFields
        dialog = QuestionDialog([],[],default_number='3')
        fields = NewQuestionVersionFields(self.db,self.test_id,dialog)
        fields.title.setText('Gedeelde vraag')
        self.assertFalse(fields.title.isHidden())
        self.assertTrue(fields.specific_version.isHidden())
        fields.kind.setCurrentIndex(fields.kind.findData('specific'))
        fields.specific_version.setCurrentIndex(fields.specific_version.findData(self.b))
        self.assertTrue(fields.title.isHidden())
        self.assertEqual([self.b],[vid for vid,(check,_,_) in fields.entries.items() if check.isChecked()])
        self.assertTrue(fields.version_rows[self.a].isHidden())
        self.assertFalse(fields.version_rows[self.b].isHidden())
        self.assertTrue(fields.validate())
        fields.kind.setCurrentIndex(fields.kind.findData('shared'))
        self.assertEqual(3,sum(check.isChecked() for check,_,_ in fields.entries.values()))
        dialog.close()

    def test_overview_reports_missing_data_and_single_save_saves_both_tabs(self):
        self.qt()
        self.configure_option_maps()
        from toetsanalyse.version_dialog import VersionDialog
        manager = VersionDialog(self.db,self.test_id)
        self.assertEqual('Overzicht',manager.tabs.tabText(0))
        manager.titles[self.shared].clear()
        manager.student_choices[self.pupils[0]].setCurrentIndex(0)
        self.assertIn('Gedeelde vragen zonder titel: 1',manager.progress.text())
        self.assertIn('Leerlingen zonder versie: 1',manager.progress.text())
        self.assertEqual('Niet-opgeslagen wijzigingen',manager.save_state.text())
        manager.titles[self.shared].setText('Krachten berekenen')
        choice = manager.student_choices[self.pupils[0]]
        choice.setCurrentIndex(choice.findData(self.c))
        self.assertTrue(manager.save_all())
        self.assertEqual('Krachten berekenen',self.db.scalar('SELECT shared_title FROM matrix_questions WHERE id=?',(self.shared,)))
        self.assertEqual(self.c,student_version(self.db,self.test_id,self.pupils[0]))
        self.assertEqual('Alles opgeslagen',manager.save_state.text())
        manager.close()

    def test_single_save_rolls_back_questions_if_student_assignment_fails(self):
        self.qt()
        self.configure_option_maps()
        self.fill()
        from unittest.mock import patch
        from PySide6.QtWidgets import QMessageBox
        from toetsanalyse.version_dialog import VersionDialog
        manager = VersionDialog(self.db,self.test_id)
        manager.titles[self.shared].setText('Niet bewaren')
        choice = manager.student_choices[self.pupils[0]]
        self.assertFalse(choice.isEnabled())
        choice.setCurrentIndex(choice.findData(self.b))
        with patch.object(QMessageBox,'warning'):
            self.assertFalse(manager.save_all())
        self.assertEqual('Snelheid berekenen',self.db.scalar('SELECT shared_title FROM matrix_questions WHERE id=?',(self.shared,)))
        self.assertEqual(self.a,student_version(self.db,self.test_id,self.pupils[0]))
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Discard):
            manager.close()

    def test_alternative_mapping_example_tracks_letters_and_reference(self):
        self.qt()
        from toetsanalyse.version_dialog import AlternativeMappingDialog
        editor = AlternativeMappingDialog([(self.a,'A'),(self.b,'B')],{},'A')
        editor.combos[self.b,'A'].setCurrentText('C')
        editor.reference.setCurrentIndex(editor.reference.findData(self.b))
        self.assertIn('A in versie A = C in versie B',editor.example.text())
        self.assertIn('letters van versie B',editor.example.text())
        self.assertFalse(editor.use_button.isEnabled())
        self.assertIn('meer dan één keer',editor.mapping_status.text())
        editor.combos[self.b,'C'].setCurrentText('A')
        self.assertTrue(editor.use_button.isEnabled())
        editor.close()

    def test_closing_unsaved_version_changes_can_be_cancelled_or_discarded(self):
        self.qt()
        from unittest.mock import patch
        from PySide6.QtWidgets import QMessageBox
        from toetsanalyse.version_dialog import VersionDialog
        manager = VersionDialog(self.db,self.test_id)
        manager.show()
        manager.titles[self.shared].setText('Niet opslaan')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Cancel):
            manager.close()
        self.assertTrue(manager.isVisible())
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Discard):
            manager.close()
        self.assertFalse(manager.isVisible())
        self.assertEqual('Snelheid berekenen',self.db.scalar('SELECT shared_title FROM matrix_questions WHERE id=?',(self.shared,)))


if __name__ == '__main__':
    unittest.main()
