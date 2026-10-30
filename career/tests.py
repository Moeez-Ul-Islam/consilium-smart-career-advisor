import json
import re
from datetime import timedelta
from unittest.mock import patch, Mock

from django.test import SimpleTestCase, TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import EmailOTP
from .password_strength import password_strength, is_acceptable
from .boards import grade_for_percentage
from .scoring import (
    normalize_riasec,
    subject_pct,
    weighted_subject_avg,
    score_degree,
    score_all_degrees,
    group_into_careers,
    career_admission_note,
    is_flat_profile,
    onet_personality_match,
    run_validation,
)
from .degrees_data import DEGREES


def _deg(key):
    return next(d for d in DEGREES if d['key'] == key)


def cs_student_data(**overrides):
    data = dict(
        matric_pct=85, inter_pct=88,
        matric_subjects={
            'Computer Science': {'obtained': 90, 'total': 100},
            'Mathematics': {'obtained': 85, 'total': 100},
            'Physics': {'obtained': 80, 'total': 100},
            'English': {'obtained': 75, 'total': 100},
        },
        inter_subjects={
            'Computer Science': {'obtained': 92, 'total': 100},
            'Mathematics': {'obtained': 88, 'total': 100},
            'Physics': {'obtained': 82, 'total': 100},
            'English': {'obtained': 78, 'total': 100},
        },
        norm_scores={'I': 85, 'C': 80, 'R': 60, 'E': 50, 'A': 45, 'S': 40},
    )
    data.update(overrides)
    return data


def score_one(key, **overrides):
    data = cs_student_data()
    data.update(overrides)
    return score_degree(_deg(key), data['matric_subjects'], data['inter_subjects'],
                        data['matric_pct'], data['inter_pct'], data['norm_scores'])

User = get_user_model()


class NormalizeTests(SimpleTestCase):
    def test_raw_25_gives_100(self):
        self.assertEqual(normalize_riasec({'R': 25})['R'], 100)

    def test_raw_5_gives_0(self):
        self.assertEqual(normalize_riasec({'R': 5})['R'], 0)

    def test_midpoint(self):
        self.assertEqual(normalize_riasec({'I': 15})['I'], 50)

    def test_missing_trait_defaults_neutral(self):
        self.assertEqual(normalize_riasec({})['A'], 50)


class SubjectHelpersTests(SimpleTestCase):
    def test_subject_pct(self):
        subs = {'Mathematics': {'obtained': 80, 'total': 100}}
        self.assertEqual(subject_pct(subs, 'Mathematics'), 80)
        self.assertIsNone(subject_pct(subs, 'Biology'))
        self.assertIsNone(subject_pct({}, 'Biology'))
        self.assertIsNone(subject_pct({'X': {'obtained': 5, 'total': 0}}, 'X'))

    def test_weighted_subject_avg_respects_weights(self):
        subs = {'Computer Science': {'obtained': 90, 'total': 100},
                'Mathematics': {'obtained': 80, 'total': 100}}

        self.assertAlmostEqual(
            weighted_subject_avg(subs, {'Computer Science': 2, 'Mathematics': 1}),
            86.67, places=1)
        self.assertIsNone(weighted_subject_avg(subs, {'Biology': 2}))


class DegreeScoringTests(SimpleTestCase):
    def test_46_degrees_defined(self):
        self.assertEqual(len(DEGREES), 46)
        self.assertEqual({d['career'] for d in DEGREES},
                         {'cs', 'engineering', 'medicine', 'business', 'arts'})

    def test_subject_fit_capped_at_100(self):
        self.assertEqual(score_one('bs_se')['subject_fit'], 100)

    def test_final_is_academic_psych_blend(self):
        r = score_one('bs_cs')
        expected = round(min(100, r['academic_fit'] * 0.7 + r['psych_fit'] * 0.3), 1)
        self.assertEqual(r['score'], expected)
        self.assertEqual(set(r), {'key', 'name', 'career', 'score',
                                  'academic_fit', 'psych_fit', 'subject_fit',
                                  'subject_avg', 'overall_pct', 'matched',
                                  'psych_breakdown', 'bridge', 'notes'})

    def test_psych_perfect_match_gives_100(self):
        r = score_one('bs_se', norm_scores={'R': 81, 'I': 81, 'A': 50,
                                            'S': 50, 'E': 50, 'C': 50})
        self.assertEqual(r['psych_fit'], 100)

    def test_psych_opposite_scores_low(self):
        r = score_one('bs_se', norm_scores={'R': 0, 'I': 0, 'A': 100,
                                            'S': 100, 'E': 100, 'C': 0})
        self.assertLess(r['psych_fit'], 50)

    def test_score_capped_at_100(self):
        r = score_one('bs_se', matric_pct=100, inter_pct=100,
                      norm_scores={'R': 86, 'I': 86, 'A': 50,
                                   'S': 50, 'E': 50, 'C': 50})
        self.assertLessEqual(r['score'], 100)


class BridgeTests(SimpleTestCase):
    def test_required_biology_triggers_bridge(self):
        r = score_one('mbbs')
        self.assertTrue(r['bridge'])
        self.assertTrue(any('Biology' in n for n in r['notes']))

        self.assertAlmostEqual(r['subject_fit'], r['overall_pct'] * 0.7, places=1)

    def test_biology_present_no_bridge(self):
        bio = {'Biology': {'obtained': 90, 'total': 100},
               'Chemistry': {'obtained': 85, 'total': 100}}
        r = score_one('mbbs', matric_subjects=bio, inter_subjects=bio)
        self.assertFalse(r['bridge'])
        self.assertEqual(r['notes'], [])

    def test_no_key_subjects_triggers_bridge(self):
        r = score_one('bs_isl')
        self.assertTrue(r['bridge'])

    def test_biomedical_requires_biology(self):


        r = score_one('bs_bme')
        self.assertTrue(r['bridge'])
        self.assertTrue(any('Biology' in n for n in r['notes']))

    def test_hec_math_note_for_cs_without_inter_maths(self):
        data = cs_student_data()
        inter_no_math = {k: v for k, v in data['inter_subjects'].items()
                         if k != 'Mathematics'}
        self.assertIn('Additional Mathematics',
                      career_admission_note('cs', inter_no_math))
        self.assertEqual(career_admission_note('cs', data['inter_subjects']), '')

    def test_pec_math_note_for_engineering_without_inter_maths(self):
        data = cs_student_data()
        inter_no_math = {k: v for k, v in data['inter_subjects'].items()
                         if k != 'Mathematics'}
        self.assertIn('8-week',
                      career_admission_note('engineering', inter_no_math))
        self.assertEqual(career_admission_note('business', inter_no_math), '')


class LoopTests(SimpleTestCase):
    def _ranked(self, **overrides):
        data = cs_student_data()
        data.update(overrides)
        degs = score_all_degrees(data['matric_pct'], data['inter_pct'],
                                 data['matric_subjects'], data['inter_subjects'],
                                 data['norm_scores'])
        return group_into_careers(degs, data['inter_subjects'], data['norm_scores'])

    def test_loop1_scores_46_degrees_sorted(self):
        data = cs_student_data()
        degs = score_all_degrees(data['matric_pct'], data['inter_pct'],
                                 data['matric_subjects'], data['inter_subjects'],
                                 data['norm_scores'])
        self.assertEqual(len(degs), 46)
        scores = [d['score'] for d in degs]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_loop2_five_careers_sorted_by_average(self):
        careers = self._ranked()
        self.assertEqual(len(careers), 5)
        scores = [c['score'] for c in careers]
        self.assertEqual(scores, sorted(scores, reverse=True))
        for c in careers:
            avg = sum(d['score'] for d in c['degrees']) / len(c['degrees'])
            self.assertAlmostEqual(c['score'], round(avg, 1))
            dscores = [d['score'] for d in c['degrees']]
            self.assertEqual(dscores, sorted(dscores, reverse=True))

    def test_cs_student_top_career_is_cs(self):
        self.assertEqual(self._ranked()[0]['key'], 'cs')

    def test_premedical_top_career_is_medicine(self):
        bio = {'Biology': {'obtained': 90, 'total': 100},
               'Chemistry': {'obtained': 85, 'total': 100},
               'Physics': {'obtained': 80, 'total': 100}}
        careers = self._ranked(matric_subjects=bio, inter_subjects=bio,
                               norm_scores={'I': 80, 'S': 85, 'C': 60,
                                            'R': 55, 'A': 50, 'E': 45})
        top2 = [c['key'] for c in careers[:2]]
        self.assertIn('medicine', top2)

    def test_reasoning_mentions_top_degree(self):
        top = self._ranked()[0]
        self.assertIn(top['degrees'][0]['name'], top['reasoning'])
        self.assertIn('strong match', top['reasoning'])

    def test_validation_suite_passes(self):
        self.assertTrue(run_validation())


class FlatProfileTests(SimpleTestCase):

    def test_is_flat_profile(self):
        self.assertTrue(is_flat_profile({'R': 5, 'I': 5, 'A': 5, 'S': 5, 'E': 5, 'C': 5}))
        self.assertTrue(is_flat_profile({'R': 0, 'I': 0, 'A': 0, 'S': 0, 'E': 0, 'C': 0}))
        self.assertFalse(is_flat_profile({'R': 5, 'I': 6, 'A': 5, 'S': 5, 'E': 5, 'C': 5}))
        self.assertFalse(is_flat_profile({}))

    def test_flat_reasoning_never_says_high(self):
        data = cs_student_data(norm_scores={'R': 0, 'I': 0, 'A': 0, 'S': 0, 'E': 0, 'C': 0})
        degs = score_all_degrees(data['matric_pct'], data['inter_pct'],
                                 data['matric_subjects'], data['inter_subjects'],
                                 data['norm_scores'])
        careers = group_into_careers(degs, data['inter_subjects'], data['norm_scores'])
        for c in careers:
            self.assertNotIn('high ', c['reasoning'])
            self.assertIn('academics', c['reasoning'])

    def test_normal_reasoning_still_says_high(self):
        data = cs_student_data()
        degs = score_all_degrees(data['matric_pct'], data['inter_pct'],
                                 data['matric_subjects'], data['inter_subjects'],
                                 data['norm_scores'])
        careers = group_into_careers(degs, data['inter_subjects'], data['norm_scores'])
        self.assertIn('high ', careers[0]['reasoning'])


class FlatProfileViewTests(TestCase):

    def test_results_show_no_clear_type(self):
        from .models import AcademicRecord, PsychResult
        user = User.objects.create_user(email='flat@test.com', password='Str0ng!Pass12',
                                        full_name='Flat')
        AcademicRecord.objects.create(
            user=user, level='matric', stream='matric_cs',
            subjects_data={'Mathematics': {'obtained': 80, 'total': 100}},
            total_obtained=80, total_possible=100, percentage=80)
        AcademicRecord.objects.create(
            user=user, level='inter', stream='ics_physics',
            subjects_data={'Mathematics': {'obtained': 80, 'total': 100}},
            total_obtained=80, total_possible=100, percentage=80)
        PsychResult.objects.create(
            user=user, answers={f'q{i}': 1 for i in range(1, 31)},
            scores={'R': 5, 'I': 5, 'A': 5, 'S': 5, 'E': 5, 'C': 5},
            dominant='R', completed=True)
        c = Client()
        c.force_login(user)
        r = c.get('/results/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'No clear type')
        self.assertContains(r, "didn&#x27;t show a strong lean")
        self.assertNotContains(r, 'high Realistic (0.0/100)')


class PasswordStrengthTests(SimpleTestCase):
    def test_weak_passwords(self):
        for pw in ('abc', 'abcdef', '12345678', 'abcdefgh'):
            level, _ = password_strength(pw)
            self.assertEqual(level, 'weak', pw)
            self.assertFalse(is_acceptable(pw))

    def test_moderate_password(self):
        level, _ = password_strength('Pass1234')
        self.assertEqual(level, 'moderate')
        self.assertTrue(is_acceptable('Pass1234'))

    def test_strong_password(self):
        level, _ = password_strength('Str0ng!Pass12')
        self.assertEqual(level, 'strong')
        self.assertTrue(is_acceptable('Str0ng!Pass12'))


def _register(client, email='otp@test.com', password='Str0ng!Pass12',
              full_name='Test User'):
    return client.post('/register/', {
        'full_name': full_name, 'email': email,
        'password1': password, 'password2': password,
    })


class OTPFlowTests(TestCase):
    @patch('career.views.send_otp_email', return_value=True)
    def test_register_sends_otp_and_redirects_to_verify(self, mock_send):
        c = Client()
        r = _register(c)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/verify/')
        mock_send.assert_called_once()

        self.assertFalse(User.objects.filter(email='otp@test.com').exists())
        self.assertTrue(EmailOTP.objects.filter(email='otp@test.com').exists())

    @patch('career.views.send_otp_email', return_value=True)
    def test_verify_correct_code_creates_and_logs_in_user(self, mock_send):
        c = Client()
        _register(c, email='v@test.com')
        otp = EmailOTP.objects.filter(email='v@test.com').latest('created_at')
        r = c.post('/verify/', {'code': otp.code})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/dashboard/')
        user = User.objects.get(email='v@test.com')
        self.assertEqual(user.full_name, 'Test User')
        self.assertTrue(user.check_password('Str0ng!Pass12'))

        self.assertEqual(c.get('/dashboard/').status_code, 200)

    @patch('career.views.send_otp_email', return_value=True)
    def test_verify_wrong_code_fails(self, mock_send):
        c = Client()
        _register(c, email='w@test.com')
        r = c.post('/verify/', {'code': '000000'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Incorrect code')
        self.assertFalse(User.objects.filter(email='w@test.com').exists())

    @patch('career.views.send_otp_email', return_value=True)
    def test_verify_duplicate_email_redirects_to_login(self, mock_send):


        c = Client()
        _register(c, email='dup@test.com')
        User.objects.create_user(email='dup@test.com', full_name='Existing',
                                 password='Str0ng!Pass12')
        otp = EmailOTP.objects.filter(email='dup@test.com').latest('created_at')
        r = c.post('/verify/', {'code': otp.code})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/login/')

        self.assertEqual(User.objects.filter(email='dup@test.com').count(), 1)

    def test_register_form_rejects_duplicate_email(self):
        User.objects.create_user(email='taken@test.com', full_name='Existing',
                                 password='Str0ng!Pass12')
        c = Client()
        r = c.post('/register/', {
            'full_name': 'New User', 'email': 'taken@test.com',
            'password1': 'Str0ng!Pass12', 'password2': 'Str0ng!Pass12',
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'already exists')

    @patch('career.views.send_otp_email', return_value=True)
    def test_expired_otp_rejected(self, mock_send):
        c = Client()
        _register(c, email='e@test.com')
        otp = EmailOTP.objects.filter(email='e@test.com').latest('created_at')
        otp.expires_at = timezone.now() - timedelta(minutes=1)
        otp.save(update_fields=['expires_at'])
        r = c.post('/verify/', {'code': otp.code})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'expire')
        self.assertFalse(User.objects.filter(email='e@test.com').exists())

    @patch('career.views.send_otp_email', return_value=True)
    def test_resend_issues_new_code(self, mock_send):
        c = Client()
        _register(c, email='r@test.com')
        first = EmailOTP.objects.filter(email='r@test.com').latest('created_at').code
        r = c.post('/resend/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/verify/')
        self.assertEqual(mock_send.call_count, 2)
        second = EmailOTP.objects.filter(email='r@test.com').latest('created_at').code
        self.assertNotEqual(first, second)

    @patch('career.views.send_otp_email', return_value=True)
    def test_resend_requires_post(self, mock_send):
        c = Client()
        _register(c, email='rp@test.com')
        r = c.get('/resend/')
        self.assertEqual(r.status_code, 405)
        self.assertEqual(mock_send.call_count, 1)

    @patch('career.views.send_otp_email', return_value=True)
    def test_resend_rate_limited(self, mock_send):
        c = Client()
        _register(c, email='rl@test.com')
        self.assertEqual(c.post('/resend/').status_code, 302)
        self.assertEqual(c.post('/resend/').status_code, 302)
        r = c.post('/resend/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/verify/')

        self.assertEqual(
            EmailOTP.objects.filter(email='rl@test.com').count(), 3)
        self.assertEqual(mock_send.call_count, 3)

        r = c.get('/verify/')
        msgs = [m.message for m in r.context['messages']]
        self.assertTrue(any('Too many resend' in m for m in msgs))

    def test_brevo_failure_shows_friendly_error(self):
        from career.brevo import EmailSendError
        c = Client()
        with patch('career.views.send_otp_email',
                   side_effect=EmailSendError('Email service could not send the code.')):
            r = _register(c, email='f@test.com')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Email service')

    def test_register_rejects_weak_password_server_side(self):
        c = Client()
        r = _register(c, email='weak@test.com', password='abc123')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'weak')
        self.assertFalse(User.objects.filter(email='weak@test.com').exists())

    def test_register_rejects_email_without_at(self):
        c = Client()
        r = c.post('/register/', {'full_name': 'X', 'email': 'notanemail',
                                  'password1': 'Str0ng!Pass12',
                                  'password2': 'Str0ng!Pass12'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '@')
        self.assertFalse(User.objects.filter(email='notanemail').exists())

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user(email='d@test.com', password='Str0ng!Pass12',
                                 full_name='Dup')
        c = Client()
        with patch('career.views.send_otp_email', return_value=True):
            r = _register(c, email='d@test.com')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'already exists')

    def test_register_rejects_duplicate_email_case_insensitive(self):
        User.objects.create_user(email='Case@Test.com', password='Str0ng!Pass12',
                                 full_name='Dup')
        c = Client()
        with patch('career.views.send_otp_email', return_value=True):
            r = _register(c, email='CASE@test.com')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'already exists')

        self.assertFalse(EmailOTP.objects.filter(email='case@test.com').exists())


class PasswordResetTests(TestCase):
    def _make_user(self, email='reset@test.com'):
        return User.objects.create_user(
            email=email, password='OldPass123!', full_name='Reset User')

    @patch('career.views.send_password_reset_email', return_value=True)
    def test_forgot_sends_code_and_redirects(self, mock_send):
        self._make_user()
        c = Client()
        r = c.post('/forgot/', {'email': 'reset@test.com'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/reset/')
        mock_send.assert_called_once()
        self.assertTrue(EmailOTP.objects.filter(email='reset@test.com').exists())

    @patch('career.views.send_password_reset_email', return_value=True)
    def test_forgot_unknown_email_does_not_reveal(self, mock_send):
        c = Client()
        r = c.post('/forgot/', {'email': 'nobody@test.com'})

        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/login/')
        mock_send.assert_not_called()
        self.assertFalse(EmailOTP.objects.filter(email='nobody@test.com').exists())

    @patch('career.views.send_password_reset_email', return_value=True)
    def test_reset_with_correct_code_changes_password(self, mock_send):
        self._make_user()
        c = Client()
        c.post('/forgot/', {'email': 'reset@test.com'})
        otp = EmailOTP.objects.filter(email='reset@test.com').latest('created_at')

        r = c.post('/reset/', {'code': otp.code})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/reset/')

        r = c.post('/reset/', {'new_password1': 'NewPass123!',
                               'new_password2': 'NewPass123!'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/login/')
        user = User.objects.get(email='reset@test.com')
        self.assertTrue(user.check_password('NewPass123!'))
        self.assertFalse(user.check_password('OldPass123!'))

    @patch('career.views.send_password_reset_email', return_value=True)
    def test_reset_with_wrong_code_fails(self, mock_send):
        self._make_user()
        c = Client()
        c.post('/forgot/', {'email': 'reset@test.com'})
        r = c.post('/reset/', {'code': '000000'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Incorrect code')
        user = User.objects.get(email='reset@test.com')
        self.assertTrue(user.check_password('OldPass123!'))

    @patch('career.views.send_password_reset_email', return_value=True)
    def test_reset_rejects_weak_password(self, mock_send):
        self._make_user()
        c = Client()
        c.post('/forgot/', {'email': 'reset@test.com'})
        otp = EmailOTP.objects.filter(email='reset@test.com').latest('created_at')

        c.post('/reset/', {'code': otp.code})

        r = c.post('/reset/', {'new_password1': 'abc123',
                               'new_password2': 'abc123'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'weak')
        user = User.objects.get(email='reset@test.com')
        self.assertTrue(user.check_password('OldPass123!'))

    def test_reset_without_session_redirects(self):
        c = Client()
        r = c.get('/reset/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/forgot/')

    def test_login_page_has_forgot_link(self):
        c = Client()
        r = c.get('/login/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '/forgot/')


class LoginTests(TestCase):
    def test_email_login_works(self):
        User.objects.create_user(email='l@test.com', password='Str0ng!Pass12',
                                 full_name='Log In')
        c = Client()
        r = c.post('/login/', {'username': 'l@test.com', 'password': 'Str0ng!Pass12'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/dashboard/')

    def test_login_wrong_password_shows_error(self):
        User.objects.create_user(email='l2@test.com', password='Str0ng!Pass12',
                                 full_name='Log In')
        c = Client()
        r = c.post('/login/', {'username': 'l2@test.com', 'password': 'wrongpass'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Incorrect')


class StreamsJsonRegressionTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email='s@test.com', password='Str0ng!Pass12', full_name='Stream')
        self.client.force_login(self.user)

    def _assert_streams_json_valid(self, url, expected_keys):
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        m = re.search(
            r'<script id="streams-data" type="application/json">(.*?)</script>',
            html, re.S)
        self.assertIsNotNone(m, 'streams-data json_script block missing')
        data = json.loads(m.group(1))

        self.assertIsInstance(data, dict)
        self.assertEqual(set(data.keys()), set(expected_keys))
        for key, stream in data.items():
            self.assertIn('name', stream)
            self.assertIn('compulsory', stream)
            self.assertIn('elective', stream)


        stream_sel = re.search(r'<select[^>]*id="stream"[^>]*>(.*?)</select>', html, re.S)
        self.assertIsNotNone(stream_sel, 'stream select missing from page')
        options = re.findall(r'<option value="([^"]+)"', stream_sel.group(1))
        options = [o for o in options if o]
        for o in options:
            self.assertIn(o, data, f'option value {o!r} missing from streams JSON')

    def test_matric_streams_json_valid(self):
        from .streams import MATRIC_STREAMS
        self._assert_streams_json_valid('/matric/', MATRIC_STREAMS.keys())

    def test_inter_streams_json_valid(self):

        from .models import AcademicRecord
        AcademicRecord.objects.create(
            user=self.user, level='matric', stream='matric_cs',
            subjects_data={'English': {'obtained': 80, 'total': 100}})
        from .streams import INTER_STREAMS
        self._assert_streams_json_valid('/inter/', INTER_STREAMS.keys())


class FullJourneyTests(TestCase):

    @patch('career.views.send_otp_email', return_value=True)
    def test_full_user_journey(self, mock_send):
        c = Client()

        r = _register(c, email='j@test.com')
        self.assertEqual(r.url, '/verify/')
        otp = EmailOTP.objects.filter(email='j@test.com').latest('created_at')
        r = c.post('/verify/', {'code': otp.code})
        self.assertEqual(r.url, '/dashboard/')


        post = {'stream': 'matric_cs', 'board': 'bise_lahore'}
        subjects = ['English', 'Urdu', 'Islamiat', 'Pak Studies', 'Tarjuma-tul-Quran',
                    'Computer Science', 'Physics', 'Chemistry', 'Mathematics']
        for i in range(len(subjects)):
            post[f'obtained_{i}'] = '80'
            post[f'total_{i}'] = '100'
        r = c.post('/matric/', post)
        self.assertEqual(r.status_code, 302)


        post = {'stream': 'ics_physics', 'board': 'bise_lahore'}
        for i in range(7):
            post[f'obtained_{i}'] = '85'
            post[f'total_{i}'] = '100'
        r = c.post('/inter/', post)
        self.assertEqual(r.status_code, 302)


        r = c.post('/test/', {f'q{i}': '4' for i in range(1, 31)})
        self.assertEqual(r.status_code, 302)


        r = c.get('/results/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Computer Science')

    def test_results_requires_all_steps(self):
        user = User.objects.create_user(email='j2@test.com', password='Str0ng!Pass12',
                                        full_name='J Two')
        c = Client()
        c.force_login(user)
        r = c.get('/results/')

        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/matric/')


class ScanEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='scan@test.com', password='Str0ng!Pass12', full_name='Scan')
        self.client.force_login(self.user)

    def test_scan_without_file_returns_error_json(self):
        r = self.client.post('/scan/')
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content.decode())
        self.assertFalse(data['ok'])
        self.assertIn('error', data)

    def test_scan_requires_login(self):
        self.client.logout()
        r = self.client.post('/scan/')
        self.assertEqual(r.status_code, 302)


def _make_user(email='t@test.com', staff=False):
    user = User.objects.create_user(
        email=email, password='Str0ng!Pass12', full_name='Tester')
    user.is_staff = staff
    user.save(update_fields=['is_staff'])
    return user


def _make_matric(user, pct=80):
    from .models import AcademicRecord
    return AcademicRecord.objects.create(
        user=user, level='matric', stream='matric_cs',
        subjects_data={'English': {'obtained': pct, 'total': 100},
                       'Mathematics': {'obtained': pct, 'total': 100}})


def _make_inter(user, pct=85):
    from .models import AcademicRecord
    return AcademicRecord.objects.create(
        user=user, level='inter', stream='ics_physics',
        subjects_data={'Computer Science': {'obtained': pct, 'total': 100},
                       'Mathematics': {'obtained': pct, 'total': 100}})


def _make_psych(user):
    from .models import PsychResult
    return PsychResult.objects.create(
        user=user,
        answers={f'q{i}': 4 for i in range(1, 31)},
        scores={'R': 15, 'I': 21, 'A': 12, 'S': 14, 'E': 16, 'C': 18},
        dominant='I', completed=True)


class UniversitiesAccessTests(TestCase):

    def test_anonymous_redirected_to_login(self):
        r = Client().get('/universities/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login/', r.url)

    def test_normal_user_redirected_to_dashboard(self):
        c = Client()
        c.force_login(_make_user())
        r = c.get('/universities/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/dashboard/')

    def test_normal_user_navbar_hides_universities_link(self):
        c = Client()
        c.force_login(_make_user(email='nav@test.com'))
        html = c.get('/dashboard/').content.decode()
        self.assertNotIn('href="/universities/"', html)

    def test_staff_user_can_view_list(self):
        c = Client()
        c.force_login(_make_user(email='staff@test.com', staff=True))
        r = c.get('/universities/')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('href="/universities/"', html)


class FlowGuardTests(TestCase):

    def test_inter_locked_without_matric(self):
        c = Client()
        c.force_login(_make_user(email='g1@test.com'))
        r = c.get('/inter/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/matric/')

    def test_test_locked_without_matric(self):
        c = Client()
        c.force_login(_make_user(email='g2@test.com'))
        r = c.get('/test/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/matric/')

    def test_test_locked_without_inter(self):
        user = _make_user(email='g3@test.com')
        _make_matric(user)
        c = Client()
        c.force_login(user)
        r = c.get('/test/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/inter/')

    def test_results_locked_without_test(self):
        user = _make_user(email='g4@test.com')
        _make_matric(user)
        _make_inter(user)
        c = Client()
        c.force_login(user)
        r = c.get('/results/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/test/')

    def test_dashboard_shows_locked_steps(self):
        c = Client()
        c.force_login(_make_user(email='g5@test.com'))
        html = c.get('/dashboard/').content.decode()


        self.assertIn('Locked', html)
        self.assertIn('nav-step-locked', html)
        self.assertIn('nav-ico-locked', html)

        self.assertIn('nav-step-current', html)
        self.assertIn('href="/matric/"', html)

    def test_dashboard_unlocks_step_by_step(self):
        user = _make_user(email='g6@test.com')
        _make_matric(user)
        c = Client()
        c.force_login(user)
        html = c.get('/dashboard/').content.decode()
        self.assertIn('nav-ico-done', html)
        self.assertIn('nav-ico-current', html)
        self.assertIn('nav-ico-locked', html)

    def test_matric_always_accessible(self):
        c = Client()
        c.force_login(_make_user(email='g7@test.com'))
        self.assertEqual(c.get('/matric/').status_code, 200)


class OnetEnrichmentTests(TestCase):

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def _ok_response(self):
        m = patch('career.onet.requests.get').start()
        self.addCleanup(patch.stopall)
        return m

    @patch('career.onet.requests.get')
    def test_success_returns_official_data(self, mock_get):
        from career.onet import enrich_career
        resp = mock_get.return_value
        resp.status_code = 200
        resp.json.side_effect = [
            {'code': '15-1252.00', 'title': 'Software Developers',
             'description': 'Research, design, and develop software.'},
            {'interests': [{'element': {'name': 'Investigative'}},
                           {'element': {'name': 'Conventional'}}]},
        ]
        with self.settings(ONET_API_KEY='k'):
            data = enrich_career('cs')
        self.assertIsNotNone(data)
        self.assertEqual(data['title'], 'Software Developers')
        self.assertEqual(data['soc_code'], '15-1252.00')
        self.assertIn('software', data['description'].lower())
        self.assertIn('Investigative', data['interests'])

    @patch('career.onet.requests.get')
    def test_interests_v2_element_list_shape(self, mock_get):
        from career.onet import enrich_career
        resp = mock_get.return_value
        resp.status_code = 200
        resp.json.side_effect = [
            {'code': '15-1252.00', 'title': 'Software Developers',
             'description': 'Desc.'},
            {'element': [{'id': '1.B.1.b', 'name': 'Investigative'},
                         {'id': '1.B.1.f', 'name': 'Conventional'}]},
        ]
        with self.settings(ONET_API_KEY='k'):
            data = enrich_career('cs')
        self.assertIsNotNone(data)
        self.assertEqual(data['interests'], ['Investigative', 'Conventional'])

    @patch('career.onet.requests.get')
    def test_uses_v2_url_and_api_key_header(self, mock_get):
        from career.onet import enrich_career
        resp = mock_get.return_value
        resp.status_code = 200
        resp.json.side_effect = [
            {'code': '15-1252.00', 'title': 'Software Developers',
             'description': 'Desc.'},
            {'interests': []},
        ]
        with self.settings(ONET_API_KEY='secret-key'):
            enrich_career('cs')
        first_call = mock_get.call_args_list[0]
        url = first_call.args[0] if first_call.args else first_call.kwargs.get('url', '')
        headers = first_call.kwargs.get('headers', {})
        self.assertTrue(url.startswith('https://api-v2.onetcenter.org/online/occupations/15-1252.00'),
                        f'unexpected URL: {url}')
        self.assertEqual(headers.get('X-API-Key'), 'secret-key')

        self.assertNotIn('auth', first_call.kwargs)

    @patch('career.onet.requests.get')
    def test_401_falls_back_to_none(self, mock_get):
        from career.onet import enrich_career
        mock_get.return_value.status_code = 401
        with self.settings(ONET_API_KEY='bad-key'):
            self.assertIsNone(enrich_career('cs'))

    @patch('career.onet.requests.get')
    def test_500_falls_back_to_none(self, mock_get):
        from career.onet import enrich_career
        mock_get.return_value.status_code = 500
        with self.settings(ONET_API_KEY='k'):
            self.assertIsNone(enrich_career('cs'))

    @patch('career.onet.requests.get')
    def test_network_error_falls_back_to_none(self, mock_get):
        from career.onet import enrich_career
        import requests as rq
        mock_get.side_effect = rq.ConnectionError('down')
        with self.settings(ONET_API_KEY='k'):
            self.assertIsNone(enrich_career('cs'))

    def test_no_key_returns_none_without_request(self):
        from career.onet import enrich_career
        with self.settings(ONET_API_KEY=''):
            with patch('career.onet.requests.get') as mock_get:
                self.assertIsNone(enrich_career('cs'))
                mock_get.assert_not_called()

    def test_unknown_career_key_returns_none(self):
        from career.onet import enrich_career
        with self.settings(ONET_API_KEY='k'):
            with patch('career.onet.requests.get') as mock_get:
                self.assertIsNone(enrich_career('nope'))
                mock_get.assert_not_called()

    @patch('career.onet.requests.get')
    def test_success_is_cached(self, mock_get):
        from career.onet import enrich_career
        resp = mock_get.return_value
        resp.status_code = 200
        resp.json.side_effect = [
            {'code': '15-1252.00', 'title': 'Software Developers', 'description': 'Desc.'},
            {'interests': []},
        ]
        with self.settings(ONET_API_KEY='k'):
            enrich_career('cs')
            enrich_career('cs')
        self.assertEqual(mock_get.call_count, 2)


class ScanValidationTests(TestCase):
    def setUp(self):
        self.user = _make_user(email='scanv@test.com')
        self.client.force_login(self.user)

    def _upload(self, name, content, content_type):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return self.client.post('/scan/', {
            'marksheet': SimpleUploadedFile(name, content, content_type=content_type)})

    def test_non_image_rejected(self):
        r = self._upload('notes.txt', b'hello world', 'text/plain')
        data = json.loads(r.content.decode())
        self.assertFalse(data['ok'])
        self.assertIn('JPG', data['error'])

    def test_oversized_image_rejected(self):
        big = b'\xff' * (8 * 1024 * 1024 + 1)
        r = self._upload('big.jpg', big, 'image/jpeg')
        data = json.loads(r.content.decode())
        self.assertFalse(data['ok'])
        self.assertIn('8MB', data['error'])

    def test_unexpected_error_never_crashes(self):
        with patch('career.views.extract_marks', side_effect=RuntimeError('boom')):
            r = self._upload('m.jpg', b'\xff\xd8fake', 'image/jpeg')
        data = json.loads(r.content.decode())
        self.assertFalse(data['ok'])
        self.assertIn('manual entry', data['error'].lower())


class UniversityFormTests(TestCase):
    def test_duplicate_name_rejected_case_insensitive(self):
        from .models import University
        from .forms import UniversityForm
        University.objects.create(name='Test University', city='Lahore',
                                  programs='BS CS', career_category='cs')
        form = UniversityForm(data={'name': 'test university', 'city': 'Lahore',
                                    'programs': 'BS CS', 'career_category': 'cs'})
        self.assertFalse(form.is_valid())
        self.assertIn('already exists', form.errors['name'][0])

    def test_edit_same_instance_keeps_name(self):
        from .models import University
        from .forms import UniversityForm
        u = University.objects.create(name='Keep Name Uni', city='Lahore',
                                      programs='BS CS', career_category='cs')
        form = UniversityForm(instance=u,
                              data={'name': 'Keep Name Uni', 'city': 'Karachi',
                                    'programs': 'BS CS', 'career_category': 'cs'})
        self.assertTrue(form.is_valid())


class LoginRedirectTests(TestCase):
    def test_open_redirect_blocked(self):
        _make_user(email='lr@test.com')
        c = Client()
        r = c.post('/login/', {'username': 'lr@test.com',
                               'password': 'Str0ng!Pass12',
                               'next': 'https://evil.com/phish'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/dashboard/')

    def test_safe_relative_next_allowed(self):
        _make_user(email='lr2@test.com')
        c = Client()
        r = c.post('/login/', {'username': 'lr2@test.com',
                               'password': 'Str0ng!Pass12',
                               'next': '/manage/'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/manage/')


class MarksEdgeTests(TestCase):
    def setUp(self):
        self.user = _make_user(email='me@test.com')
        self.client.force_login(self.user)

    def _post_matric(self, subjects):
        post = {'stream': 'matric_cs', 'board': 'bise_lahore'}
        for i, (obt, tot) in enumerate(subjects):
            post[f'obtained_{i}'] = obt
            post[f'total_{i}'] = tot
        return self.client.post('/matric/', post)

    def test_empty_marks_rejected(self):
        r = self._post_matric([])
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'compulsory subjects')
        from .models import AcademicRecord
        self.assertFalse(
            AcademicRecord.objects.filter(user=self.user, level='matric').exists())

    def test_missing_compulsory_names_the_subject(self):

        pairs = [('80', '100')] * 9
        pairs[1] = ('', '')
        r = self._post_matric(pairs)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'compulsory subjects')
        self.assertContains(r, 'Urdu')

    def test_blank_obtained_with_prefilled_total_names_compulsory(self):


        pairs = [('80', '100')] * 9
        pairs[1] = ('', '150')
        r = self._post_matric(pairs)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'compulsory subjects')
        self.assertContains(r, 'Urdu')
        self.assertNotContains(r, 'invalid marks')

    def test_obtained_without_total_asks_for_total(self):

        pairs = [('80', '100')] * 9
        pairs[0] = ('80', '')
        r = self._post_matric(pairs)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Please enter the total marks for')
        self.assertContains(r, 'English')

    def test_only_one_elective_rejected(self):

        pairs = [('80', '100')] * 6 + [('', '')] * 3
        r = self._post_matric(pairs)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'at least 2 elective subjects')

    def test_all_zero_marks_rejected_in_matric(self):


        r = self._post_matric([('0', '100')] * 9)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'must pass every subject')
        from .models import AcademicRecord
        self.assertFalse(
            AcademicRecord.objects.filter(user=self.user, level='matric').exists())

    def test_obtained_greater_than_total_rejected(self):

        pairs = [('80', '100')] * 9
        pairs[0] = ('120', '100')
        r = self._post_matric(pairs)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'cannot be greater than the total')
        from .models import AcademicRecord
        self.assertFalse(
            AcademicRecord.objects.filter(user=self.user, level='matric').exists())

    def test_invalid_marksheet_type_rejected_on_save(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        post = {'stream': 'matric_cs', 'board': 'bise_lahore'}
        for i in range(7):
            post[f'obtained_{i}'] = '80'
            post[f'total_{i}'] = '100'
        post['marksheet'] = SimpleUploadedFile('x.txt', b'hi', content_type='text/plain')
        r = self.client.post('/matric/', post)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'JPG')


class MarksPersistenceTests(TestCase):
    def setUp(self):
        self.user = _make_user(email='persist@test.com')
        self.client.force_login(self.user)

    def test_matric_error_keeps_stream_board_and_marks(self):


        post = {'stream': 'matric_cs', 'board': 'bise_lahore'}
        for i, (obt, tot) in enumerate([('80', '100')] * 4 + [('', '')]
                                       + [('77', '100')] + [('', '')] * 3):
            post['obtained_%d' % i] = obt
            post['total_%d' % i] = tot
        r = self.client.post('/matric/', post)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'at least 2 elective subjects')

        self.assertContains(r, '<option value="matric_cs" selected>')

        self.assertContains(r, '<option value="bise_lahore" selected>')

        self.assertContains(r, 'id="posted-subjects"')
        self.assertContains(r, '"English": {"obtained": "80"')
        self.assertContains(r, '"Computer Science": {"obtained": "77"')

    def test_inter_error_keeps_stream_board_and_marks(self):
        _make_matric(self.user)

        post = {'stream': 'pre_medical', 'board': 'fbise'}
        for i, (obt, tot) in enumerate([('80', '100')] * 4
                                       + [('85', '100')] + [('', '')] * 2):
            post['obtained_%d' % i] = obt
            post['total_%d' % i] = tot
        r = self.client.post('/inter/', post)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'at least 2 elective subjects')
        self.assertContains(r, '<option value="pre_medical" selected>')
        self.assertContains(r, '<option value="fbise" selected>')
        self.assertContains(r, 'id="posted-subjects"')
        self.assertContains(r, '"Biology": {"obtained": "85"')


class PassingMarksTests(TestCase):

    def setUp(self):
        self.user = _make_user(email='pm@test.com')
        self.client.force_login(self.user)

    def _post(self, url, stream, pairs, board='bise_lahore'):
        post = {'stream': stream, 'board': board}
        for i, (obt, tot) in enumerate(pairs):
            post[f'obtained_{i}'] = obt
            post[f'total_{i}'] = tot
        return self.client.post(url, post, follow=True)

    def test_board_passing_pct_lookup(self):
        from .boards import passing_pct_for
        self.assertEqual(passing_pct_for('fbise'), 40)
        self.assertEqual(passing_pct_for('bise_karachi'), 40)
        self.assertEqual(passing_pct_for('bise_lahore'), 33)
        self.assertEqual(passing_pct_for('bise_quetta'), 33)
        self.assertEqual(passing_pct_for(''), 33)
        self.assertEqual(passing_pct_for('nope'), 33)

    def test_matric_below_passing_rejected(self):
        from .models import AcademicRecord
        pairs = [('80', '100')] * 9
        pairs[0] = ('30', '100')
        r = self._post('/matric/', 'matric_cs', pairs)
        self.assertContains(r, 'must pass every subject')
        self.assertContains(r, 'English')
        self.assertFalse(
            AcademicRecord.objects.filter(user=self.user, level='matric').exists())

    def test_matric_fbise_40pct_rule(self):
        pairs = [('80', '100')] * 9
        pairs[0] = ('35', '100')
        r = self._post('/matric/', 'matric_cs', pairs, board='fbise')
        self.assertContains(r, '40%')
        self.assertContains(r, 'Federal Board')

    def test_matric_lahore_33pct_allows_35(self):
        from .models import AcademicRecord
        pairs = [('80', '100')] * 9
        pairs[0] = ('35', '100')
        r = self._post('/matric/', 'matric_cs', pairs, board='bise_lahore')
        self.assertRedirects(r, '/inter/')
        rec = AcademicRecord.objects.get(user=self.user, level='matric')
        self.assertEqual(rec.board, 'bise_lahore')

    def test_matric_exactly_at_passing_ok(self):
        pairs = [('33', '100')] * 9
        r = self._post('/matric/', 'matric_cs', pairs)
        self.assertRedirects(r, '/inter/')

    def test_inter_below_passing_warns_but_saves(self):
        from .models import AcademicRecord
        _make_matric(self.user)
        pairs = [('80', '100')] * 7
        pairs[0] = ('25', '100')
        r = self._post('/inter/', 'ics_physics', pairs)
        self.assertRedirects(r, '/test/')
        rec = AcademicRecord.objects.get(user=self.user, level='inter')
        self.assertEqual(rec.subjects_data['English']['obtained'], 25)
        self.assertContains(r, 'Below passing marks')
        self.assertContains(r, 'English')

    def test_inter_clean_entry_no_warning(self):
        _make_matric(self.user)
        pairs = [('80', '100')] * 7
        r = self._post('/inter/', 'ics_physics', pairs)
        self.assertRedirects(r, '/test/')
        self.assertNotContains(r, 'Below passing marks')

    def test_board_is_required(self):
        pairs = [('80', '100')] * 9
        r = self._post('/matric/', 'matric_cs', pairs, board='')
        self.assertContains(r, 'Please select your board')
        from .models import AcademicRecord
        self.assertFalse(
            AcademicRecord.objects.filter(user=self.user, level='matric').exists())

    def test_unknown_board_is_rejected(self):
        pairs = [('80', '100')] * 9
        r = self._post('/matric/', 'matric_cs', pairs, board='nope')
        self.assertContains(r, 'Please select your board')


class ScanBoardCombineTests(SimpleTestCase):

    def _ocr_response(self, board, subjects):
        m = Mock()
        m.status_code = 200
        m.json.return_value = {
            'candidates': [{'content': {'parts': [
                {'text': json.dumps({'board': board, 'subjects': subjects})}]}}]}
        return m

    def _run_extract(self, board, subjects):
        from django.test import override_settings
        from . import marksheet_ocr as ocr_mod
        with override_settings(GEMINI_API_KEY='test-key'), \
             patch.object(ocr_mod.requests, 'post',
                          return_value=self._ocr_response(board, subjects)):
            return ocr_mod.extract_marks(b'fake-bytes', 'image/jpeg')

    def test_fbise_style_card_combined(self):
        result = self._run_extract('fbise', [
            {'subject': 'PHYSICS - I (THEORY)', 'obtained': 44, 'total': None},
            {'subject': 'PHYSICS - II (THEORY)', 'obtained': 51, 'total': None},
            {'subject': 'Physics Practical', 'obtained': 20, 'total': None},
            {'subject': 'ENGLISH - I (COMPULSORY)', 'obtained': 60, 'total': None},
            {'subject': 'ENGLISH - II (COMPULSORY)', 'obtained': 62, 'total': None},
            {'subject': 'PAKISTAN STUDIES - I', 'obtained': 38, 'total': None},
            {'subject': 'PAKISTAN STUDIES - II', 'obtained': 40, 'total': None},
        ])
        self.assertEqual(result['board'], 'fbise')
        by_name = {s['subject']: s for s in result['subjects']}
        self.assertEqual(by_name['Physics']['obtained'], 115)
        self.assertEqual(by_name['English']['obtained'], 122)
        self.assertEqual(by_name['Pak Studies']['obtained'], 78)
        self.assertEqual(len(result['subjects']), 3)

    def test_unknown_board_becomes_none(self):
        result = self._run_extract('not_a_board', [
            {'subject': 'English', 'obtained': 80, 'total': 100}])
        self.assertIsNone(result['board'])
        self.assertEqual(result['subjects'][0]['obtained'], 80)

    def test_already_combined_subjects_untouched(self):
        result = self._run_extract('fbise', [
            {'subject': 'Physics', 'obtained': 115, 'total': 150},
            {'subject': 'Chemistry', 'obtained': 119, 'total': 150},
        ])
        self.assertEqual(len(result['subjects']), 2)
        self.assertEqual(result['subjects'][0]['obtained'], 115)

    def _resp(self, status, board='fbise', subjects=None):
        m = Mock()
        m.status_code = status
        if subjects is not None:
            m.json.return_value = {
                'candidates': [{'content': {'parts': [
                    {'text': json.dumps({'board': board, 'subjects': subjects})}]}}]}
        return m

    def test_retry_on_503_then_succeeds(self):
        from django.test import override_settings
        from . import marksheet_ocr as ocr_mod
        from .marksheet_ocr import MarksheetScanError
        ok = self._resp(200, subjects=[{'subject': 'English', 'obtained': 80, 'total': 100}])
        with override_settings(GEMINI_API_KEY='test-key'), \
             patch.object(ocr_mod.requests, 'post',
                          side_effect=[self._resp(503), self._resp(503), ok]), \
             patch.object(ocr_mod.time, 'sleep'):
            result = ocr_mod.extract_marks(b'x', 'image/jpeg')
        self.assertEqual(result['subjects'][0]['subject'], 'English')

    def test_503_every_time_gives_busy_message(self):
        from django.test import override_settings
        from . import marksheet_ocr as ocr_mod
        from .marksheet_ocr import MarksheetScanError
        with override_settings(GEMINI_API_KEY='test-key'), \
             patch.object(ocr_mod.requests, 'post', return_value=self._resp(503)), \
             patch.object(ocr_mod.time, 'sleep'):
            with self.assertRaises(MarksheetScanError) as cm:
                ocr_mod.extract_marks(b'x', 'image/jpeg')
        self.assertIn('busy', str(cm.exception).lower())

    def test_connection_error_retried(self):
        from django.test import override_settings
        from . import marksheet_ocr as ocr_mod
        import requests as req_mod
        ok = self._resp(200, subjects=[{'subject': 'Urdu', 'obtained': 70, 'total': 100}])
        with override_settings(GEMINI_API_KEY='test-key'), \
             patch.object(ocr_mod.requests, 'post',
                          side_effect=[req_mod.ConnectionError('down'), ok]), \
             patch.object(ocr_mod.time, 'sleep'):
            result = ocr_mod.extract_marks(b'x', 'image/jpeg')
        self.assertEqual(result['subjects'][0]['subject'], 'Urdu')


class OnetItemsTests(SimpleTestCase):

    def test_thirty_items_five_per_type(self):
        from .questions import QUESTIONS
        self.assertEqual(len(QUESTIONS), 30)
        counts = {}
        for _, t in QUESTIONS:
            counts[t] = counts.get(t, 0) + 1
        self.assertEqual(counts, {'R': 5, 'I': 5, 'A': 5, 'S': 5, 'E': 5, 'C': 5})

    def test_official_order_and_wording_verbatim(self):
        from .questions import QUESTIONS

        self.assertEqual(QUESTIONS[0], ('Build kitchen cabinets', 'R'))
        self.assertEqual(QUESTIONS[1], ('Develop a new medicine', 'I'))
        self.assertEqual(QUESTIONS[5], ('Install software across computers on a large network', 'C'))
        self.assertEqual(QUESTIONS[29], ('Stamp, sort, and distribute mail for an organization', 'C'))

    def test_official_likert_labels(self):
        from .questions import LIKERT_LABELS
        self.assertEqual([l for _, l in LIKERT_LABELS],
                         ['Strongly Dislike', 'Dislike', 'Unsure', 'Like', 'Strongly Like'])

    def test_credit_line_present(self):
        from .questions import ONET_CREDIT
        self.assertIn('U.S. Department of Labor', ONET_CREDIT)
        self.assertIn('CC BY-ND 4.0', ONET_CREDIT)


class OnetCreditPageTests(TestCase):
    def test_test_page_shows_credit_and_instruction(self):
        user = _make_user(email='onetq@test.com')
        _make_matric(user)
        _make_inter(user)
        c = Client()
        c.force_login(user)
        r = c.get('/test/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Build kitchen cabinets')
        self.assertContains(r, 'Strongly Dislike')
        self.assertContains(r, 'U.S. Department of Labor')
        self.assertContains(r, 'how much you would enjoy doing it')


class ScanBoardViewTests(TestCase):
    def test_scan_returns_board_in_json(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        user = _make_user(email='scanb@test.com')
        c = Client()
        c.force_login(user)
        with patch('career.views.extract_marks', return_value={
                'subjects': [{'subject': 'Physics', 'obtained': 115, 'total': None}],
                'board': 'fbise'}):
            r = c.post('/scan/', {'marksheet': SimpleUploadedFile(
                'm.jpg', b'\xff\xd8fake', content_type='image/jpeg')})
        data = json.loads(r.content.decode())
        self.assertTrue(data['ok'])
        self.assertEqual(data['board'], 'fbise')
        self.assertEqual(data['subjects'][0]['subject'], 'Physics')


class NavStepsTests(TestCase):
    def _states(self, user):
        from career.context_processors import nav_steps
        from django.test import RequestFactory
        rf = RequestFactory()
        req = rf.get('/dashboard/')
        req.user = user
        return {s['key']: s['state'] for s in nav_steps(req)['nav_steps']}

    def test_fresh_user_sees_matric_current_rest_locked(self):
        states = self._states(_make_user(email='navsteps1@test.com'))
        self.assertEqual(states['matric'], 'current')
        self.assertEqual(states['inter'], 'locked')
        self.assertEqual(states['test'], 'locked')
        self.assertEqual(states['results'], 'locked')

    def test_progress_states_advance(self):
        from .models import AcademicRecord, PsychResult
        user = _make_user(email='navsteps2@test.com')
        AcademicRecord.objects.create(
            user=user, level='matric', stream='matric_cs',
            subjects_data={}, percentage=80)
        states = self._states(user)
        self.assertEqual(states['matric'], 'done')
        self.assertEqual(states['inter'], 'current')
        AcademicRecord.objects.create(
            user=user, level='inter', stream='pre_medical',
            subjects_data={}, percentage=75)
        PsychResult.objects.create(
            user=user, dominant='I', scores={'R': 10, 'I': 20, 'A': 12, 'S': 14, 'E': 11, 'C': 13})
        states = self._states(user)
        self.assertEqual(states['test'], 'done')
        self.assertEqual(states['results'], 'current')

    def test_navbar_renders_step_pills_with_dots(self):
        c = Client()
        c.force_login(_make_user(email='navsteps3@test.com'))
        html = c.get('/dashboard/').content.decode()
        self.assertIn('nav-pill', html)
        self.assertIn('nav-ico-current', html)
        self.assertIn('nav-ico-locked', html)


def _matric_post(obtained='80', total='100', **extra):
    post = {'stream': 'matric_cs', 'board': 'bise_lahore'}
    for i in range(9):
        post[f'obtained_{i}'] = obtained
        post[f'total_{i}'] = total
    post.update(extra)
    return post


class EditMarksUxTests(TestCase):


    def test_back_url_matric_points_to_dashboard(self):
        c = Client()
        c.force_login(_make_user(email='bu1@test.com'))
        r = c.get('/matric/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['back_url'], 'dashboard')
        self.assertIn('href="/dashboard/"', r.content.decode())

    def test_back_url_inter_points_to_matric(self):
        user = _make_user(email='bu2@test.com')
        _make_matric(user)
        c = Client()
        c.force_login(user)
        r = c.get('/inter/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['back_url'], 'matric_entry')
        self.assertIn('href="/matric/"', r.content.decode())


    def _completed_user(self, email):
        user = _make_user(email=email)
        _make_matric(user)
        _make_inter(user)
        _make_psych(user)
        return user

    def test_update_button_hidden_without_completed_result(self):
        user = _make_user(email='bu3@test.com')
        _make_matric(user)
        c = Client()
        c.force_login(user)
        html = c.get('/matric/').content.decode()
        self.assertNotIn('Update Result', html)
        html = c.get('/inter/').content.decode()
        self.assertNotIn('Update Result', html)

    def test_update_button_shown_with_completed_result(self):
        user = self._completed_user('bu4@test.com')
        c = Client()
        c.force_login(user)
        self.assertContains(c.get('/matric/'), 'Save &amp; Update Result')
        self.assertContains(c.get('/inter/'), 'Save &amp; Update Result')

    def test_update_result_redirects_to_results_and_updates_marks(self):
        from .models import AcademicRecord
        user = self._completed_user('bu5@test.com')
        c = Client()
        c.force_login(user)
        r = c.post('/matric/', _matric_post(obtained='90', action='update_result'))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/results/')
        record = AcademicRecord.objects.get(user=user, level='matric')
        self.assertEqual(record.percentage, 90.0)

        r = c.get('/results/')
        self.assertEqual(r.status_code, 200)

    def test_forged_update_action_without_result_falls_back(self):
        user = _make_user(email='bu6@test.com')
        _make_matric(user)
        c = Client()
        c.force_login(user)
        r = c.post('/matric/', _matric_post(action='update_result'))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/inter/')


    def test_delete_record_post_deletes_record(self):
        from .models import AcademicRecord
        user = _make_user(email='bu7@test.com')
        _make_matric(user)
        c = Client()
        c.force_login(user)
        r = c.post('/records/delete/matric/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/dashboard/')
        self.assertFalse(AcademicRecord.objects.filter(user=user, level='matric').exists())

    def test_delete_record_removes_marksheet_file(self):
        import os, tempfile
        from django.test import override_settings
        from django.core.files.base import ContentFile
        from .models import AcademicRecord
        user = _make_user(email='bu8@test.com')
        media = tempfile.mkdtemp()
        with override_settings(MEDIA_ROOT=media):
            rec = _make_matric(user)
            rec.marksheet.save('sheet.jpg', ContentFile(b'fake-image'), save=True)
            path = rec.marksheet.path
            self.assertTrue(os.path.exists(path))
            c = Client()
            c.force_login(user)
            r = c.post('/records/delete/matric/')
            self.assertEqual(r.status_code, 302)
            self.assertFalse(os.path.exists(path))
            self.assertFalse(AcademicRecord.objects.filter(user=user, level='matric').exists())

    def test_delete_record_get_rejected(self):
        user = _make_user(email='bu9@test.com')
        c = Client()
        c.force_login(user)
        r = c.get('/records/delete/matric/')
        self.assertEqual(r.status_code, 405)

    def test_delete_record_bad_level_404(self):
        user = _make_user(email='bu10@test.com')
        c = Client()
        c.force_login(user)
        r = c.post('/records/delete/xyz/')
        self.assertEqual(r.status_code, 404)

    def test_delete_record_requires_login(self):
        r = Client().post('/records/delete/matric/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login/', r.url)

    def test_delete_keeps_other_level(self):
        from .models import AcademicRecord
        user = self._completed_user('bu11@test.com')
        c = Client()
        c.force_login(user)
        c.post('/records/delete/matric/')
        self.assertFalse(AcademicRecord.objects.filter(user=user, level='matric').exists())
        self.assertTrue(AcademicRecord.objects.filter(user=user, level='inter').exists())

    def test_dashboard_shows_edit_and_delete_for_completed_steps(self):
        user = _make_user(email='bu12@test.com')
        _make_matric(user)
        c = Client()
        c.force_login(user)
        html = c.get('/dashboard/').content.decode()
        self.assertIn('Edit', html)
        self.assertIn('/records/delete/matric/', html)
        self.assertNotIn('/records/delete/inter/', html)


class OnetPersonalityMatchTests(SimpleTestCase):

    def test_levels_and_order_preserved(self):
        rows = onet_personality_match(
            ['Investigative', 'Conventional', 'Realistic'],
            {'I': 85, 'C': 65, 'R': 30})
        self.assertEqual([r['name'] for r in rows],
                         ['Investigative', 'Conventional', 'Realistic'])
        self.assertEqual([r['letter'] for r in rows], ['I', 'C', 'R'])
        self.assertEqual([r['level'] for r in rows],
                         ['Strong match', 'Moderate', 'Developing'])
        self.assertEqual(rows[0]['student_score'], 85)

    def test_level_boundaries(self):
        rows = onet_personality_match(
            ['Investigative', 'Conventional', 'Realistic', 'Social'],
            {'I': 70, 'C': 69.9, 'R': 40, 'S': 39.9})
        self.assertEqual([r['level'] for r in rows],
                         ['Strong match', 'Moderate', 'Moderate', 'Developing'])

    def test_unknown_names_skipped(self):
        rows = onet_personality_match(
            ['Investigative', 'NotATrait', '  ', 'Conventional'],
            {'I': 80, 'C': 80})
        self.assertEqual([r['name'] for r in rows],
                         ['Investigative', 'Conventional'])

    def test_empty_and_none_interests(self):
        self.assertEqual(onet_personality_match([], {'I': 80}), [])
        self.assertEqual(onet_personality_match(None, {'I': 80}), [])

    def test_missing_letter_defaults_to_zero_developing(self):
        rows = onet_personality_match(['Artistic'], {})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['student_score'], 0)
        self.assertEqual(rows[0]['level'], 'Developing')

    def test_scores_clamped_to_100(self):
        rows = onet_personality_match(['Enterprising'], {'E': 150})
        self.assertEqual(rows[0]['student_score'], 100)
        self.assertEqual(rows[0]['level'], 'Strong match')


class OnetMatchBlockTests(TestCase):

    def _full_user(self, email='m@test.com'):
        from .models import AcademicRecord, PsychResult
        user = User.objects.create_user(email=email, password='Str0ng!Pass12',
                                        full_name='M Tester')
        AcademicRecord.objects.create(
            user=user, level='matric', stream='matric_cs',
            subjects_data={'Mathematics': {'obtained': 90, 'total': 100}},
            total_obtained=90, total_possible=100, percentage=90)
        AcademicRecord.objects.create(
            user=user, level='inter', stream='ics_physics',
            subjects_data={'Mathematics': {'obtained': 85, 'total': 100}},
            total_obtained=85, total_possible=100, percentage=85)
        PsychResult.objects.create(
            user=user, answers={}, scores={'R': 15, 'I': 22, 'A': 12, 'S': 11, 'E': 13, 'C': 20},
            dominant='I', completed=True)
        return user

    def _fake_onet(self):
        return {'title': 'Software Developers', 'soc_code': '15-1252.00',
                'description': 'Research, design, and develop software.',
                'interests': ['Investigative', 'Conventional']}

    @patch('career.views.enrich_career')
    def test_block_renders_badge_and_comparison(self, mock_enrich):
        mock_enrich.return_value = self._fake_onet()
        user = self._full_user()
        c = Client()
        c.force_login(user)
        r = c.get('/results/')
        self.assertEqual(r.status_code, 200)

        self.assertContains(r, 'Verified by O*NET')
        self.assertContains(r, 'SOC 15-1252.00')
        self.assertNotContains(r, 'fit-pill">SOC')

        self.assertContains(r, 'Software Developers')
        self.assertContains(r, 'Research, design, and develop software.')

        self.assertContains(r, 'Your personality vs this occupation')
        self.assertContains(r, 'Investigative')
        self.assertContains(r, 'Conventional')
        self.assertContains(r, 'Strong match')

    @patch('career.views.enrich_career')
    def test_developing_level_shown_for_low_score(self, mock_enrich):
        fake = self._fake_onet()
        fake['interests'] = ['Investigative', 'Social']
        mock_enrich.return_value = fake
        user = self._full_user(email='m4@test.com')
        c = Client()
        c.force_login(user)
        r = c.get('/results/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Strong match')
        self.assertContains(r, 'Developing')

    @patch('career.views.enrich_career')
    def test_block_fallback_when_onet_none(self, mock_enrich):
        mock_enrich.return_value = None
        user = self._full_user(email='m2@test.com')
        c = Client()
        c.force_login(user)
        r = c.get('/results/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'currently unavailable')
        self.assertNotContains(r, 'Verified by O*NET')
        self.assertNotContains(r, 'Your personality vs this occupation')

    @patch('career.views.enrich_career')
    def test_cached_onet_dict_not_mutated(self, mock_enrich):
        shared = self._fake_onet()
        mock_enrich.return_value = shared
        user = self._full_user(email='m3@test.com')
        c = Client()
        c.force_login(user)
        r = c.get('/results/')
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('match_rows', shared)


class ResultsPdfTests(TestCase):

    def _full_user(self, email='pdf@test.com'):
        user = _make_user(email=email)
        m = _make_matric(user); m.recalc(); m.save()
        i = _make_inter(user); i.recalc(); i.save()
        _make_psych(user)
        return user

    @patch('career.views.enrich_career', return_value=None)
    def test_pdf_returns_pdf(self, _mock):
        c = Client()
        c.force_login(self._full_user())
        r = c.get('/results/download/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertIn('attachment', r['Content-Disposition'])
        self.assertIn('consilium_recommendations.pdf', r['Content-Disposition'])
        self.assertTrue(r.content.startswith(b'%PDF'))

    def test_pdf_requires_login(self):
        r = Client().get('/results/download/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login/', r.url)

    def test_pdf_guard_redirects_without_steps(self):
        c = Client()
        c.force_login(_make_user(email='pdf2@test.com'))
        r = c.get('/results/download/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/matric/')

    @patch('career.views.enrich_career', return_value=None)
    def test_results_page_has_pdf_button_and_toggles(self, _mock):
        c = Client()
        c.force_login(self._full_user(email='pdf3@test.com'))
        html = c.get('/results/').content.decode()

        self.assertIn('Download PDF', html)
        self.assertIn('/results/download/', html)

        self.assertIn('toggle-btn', html)
        self.assertIn('data-target="why-1"', html)
        self.assertIn('data-target="details-1"', html)
        self.assertIn('aria-expanded="false"', html)
        self.assertIn('id="why-1"', html)
        self.assertIn('id="details-1"', html)

        self.assertIn('desc-clamp', html)


class StreamCoverageTests(TestCase):

    def _user(self, email='stream@test.com'):
        user = User.objects.create_user(email=email, password='Str0ng!Pass12',
                                        full_name='Stream Tester')

        from .models import AcademicRecord
        AcademicRecord.objects.create(
            user=user, level='matric', stream='matric_cs', board='bise_lahore',
            subjects_data={'English': {'obtained': 80, 'total': 100}},
            percentage=80.0)
        c = Client()
        c.force_login(user)
        return c

    def test_matric_without_quran_succeeds(self):
        c = self._user()
        post = {'stream': 'science_bio', 'board': 'bise_lahore'}
        idx = 0
        for _ in ['English', 'Urdu', 'Islamiat', 'Pak Studies']:
            post[f'obtained_{idx}'] = '80'; post[f'total_{idx}'] = '100'; idx += 1
        idx += 1
        for _ in ['Biology', 'Physics', 'Chemistry', 'Mathematics']:
            post[f'obtained_{idx}'] = '80'; post[f'total_{idx}'] = '100'; idx += 1
        r = c.post('/matric/', post)
        self.assertEqual(r.status_code, 302)

    def test_matric_fashion_designing(self):
        c = self._user(email='fd@test.com')
        post = {'stream': 'fashion_design', 'board': 'bise_lahore'}
        subjects = ['English', 'Urdu', 'Islamiat', 'Pak Studies',
                    'Mathematics', 'General Science', 'Computer Science',
                    'Communication Skills', 'Fashion Designing']
        for i in range(len(subjects)):
            post[f'obtained_{i}'] = '75'
            post[f'total_{i}'] = '100'
        r = c.post('/matric/', post)
        self.assertEqual(r.status_code, 302)

    def test_inter_general_science(self):
        c = self._user(email='gs@test.com')
        post = {'stream': 'general_science', 'board': 'bise_lahore'}
        subjects = ['English', 'Urdu', 'Islamic Studies', 'Pak Studies',
                    'Mathematics', 'Statistics', 'Economics']
        for i in range(len(subjects)):
            post[f'obtained_{i}'] = '80'
            post[f'total_{i}'] = '100'
        r = c.post('/inter/', post)
        self.assertEqual(r.status_code, 302)

    def test_ics_with_economics(self):
        c = self._user(email='icseco@test.com')
        post = {'stream': 'ics_physics', 'board': 'bise_lahore'}
        subjects = ['English', 'Urdu', 'Islamic Studies', 'Pak Studies',
                    'Computer Science', 'Mathematics', 'Economics']
        for i in range(len(subjects)):
            post[f'obtained_{i}'] = '82'
            post[f'total_{i}'] = '100'
        r = c.post('/inter/', post)
        self.assertEqual(r.status_code, 302)

    def test_fa_valid_one_per_group(self):
        import json
        c = self._user(email='fa1@test.com')
        picked = ['English Literature', 'Psychology', 'Economics']
        post = {'stream': 'fa', 'board': 'bise_lahore',
                'fa_electives': json.dumps(picked)}
        subjects = ['English', 'Urdu', 'Islamic Studies', 'Pak Studies'] + picked
        for i in range(len(subjects)):
            post[f'obtained_{i}'] = '78'
            post[f'total_{i}'] = '100'
        r = c.post('/inter/', post)
        self.assertEqual(r.status_code, 302)

    def test_fa_two_from_same_group_rejected(self):
        import json
        c = self._user(email='fa2@test.com')
        picked = ['English Literature', 'Arabic', 'Economics']
        post = {'stream': 'fa', 'board': 'bise_lahore',
                'fa_electives': json.dumps(picked)}
        subjects = ['English', 'Urdu', 'Islamic Studies', 'Pak Studies'] + picked
        for i in range(len(subjects)):
            post[f'obtained_{i}'] = '78'
            post[f'total_{i}'] = '100'
        r = c.post('/inter/', post)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'one elective subject from each group')

    def test_fa_missing_group_rejected(self):
        import json
        c = self._user(email='fa3@test.com')
        picked = ['English Literature', 'Psychology']
        post = {'stream': 'fa', 'board': 'bise_lahore',
                'fa_electives': json.dumps(picked)}
        subjects = ['English', 'Urdu', 'Islamic Studies', 'Pak Studies'] + picked
        for i in range(len(subjects)):
            post[f'obtained_{i}'] = '78'
            post[f'total_{i}'] = '100'
        r = c.post('/inter/', post)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'one elective subject from each group')


class FeedbackTests(TestCase):

    def test_feedback_page_loads_anonymous(self):
        r = Client().get('/feedback/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Your Feedback', r.content.decode())

    def test_feedback_category_preselected_from_query(self):
        html = Client().get('/feedback/?category=results').content.decode()
        self.assertIn('value="results" selected', html)

    def test_feedback_invalid_category_falls_back(self):
        html = Client().get('/feedback/?category=nope').content.decode()
        self.assertIn('value="general" selected', html)

    def test_anonymous_can_submit_feedback(self):
        c = Client()
        r = c.post('/feedback/', {'category': 'registration', 'rating': '4',
                                  'message': 'Signup was smooth.'})
        self.assertEqual(r.status_code, 302)
        from career.models import Feedback
        fb = Feedback.objects.get()
        self.assertIsNone(fb.user)
        self.assertEqual(fb.category, 'registration')
        self.assertEqual(fb.rating, 4)

    def test_logged_in_feedback_links_user(self):
        c = Client()
        c.force_login(_make_user(email='fb@test.com'))
        c.post('/feedback/', {'category': 'results', 'rating': '5',
                              'message': 'Great recommendations!'})
        from career.models import Feedback
        fb = Feedback.objects.get()
        self.assertEqual(fb.user.email, 'fb@test.com')

    def test_empty_message_rejected(self):
        c = Client()
        r = c.post('/feedback/', {'category': 'general', 'rating': '3', 'message': '  '})
        self.assertEqual(r.status_code, 200)
        from career.models import Feedback
        self.assertEqual(Feedback.objects.count(), 0)

    def test_rating_clamped_to_1_5(self):
        c = Client()
        c.post('/feedback/', {'category': 'general', 'rating': '99', 'message': 'x'})
        from career.models import Feedback
        self.assertEqual(Feedback.objects.get().rating, 5)

    def test_staff_manage_page_shows_feedback(self):
        from career.models import Feedback
        Feedback.objects.create(category='marks', rating=2, message='Scan issue here.')
        c = Client()
        c.force_login(_make_user(email='staff@test.com', staff=True))
        html = c.get('/manage/').content.decode()
        self.assertIn('Scan issue here.', html)
        self.assertIn('User Feedback', html)


class GradeTests(SimpleTestCase):
    def test_bands(self):
        self.assertEqual(grade_for_percentage(95, 33), 'A+')
        self.assertEqual(grade_for_percentage(80, 33), 'A+')
        self.assertEqual(grade_for_percentage(79.9, 33), 'A')
        self.assertEqual(grade_for_percentage(70, 33), 'A')
        self.assertEqual(grade_for_percentage(69.9, 33), 'B')
        self.assertEqual(grade_for_percentage(60, 33), 'B')
        self.assertEqual(grade_for_percentage(59.9, 33), 'C')
        self.assertEqual(grade_for_percentage(50, 33), 'C')
        self.assertEqual(grade_for_percentage(49.9, 33), 'D')

    def test_follows_board_passing_marks(self):
        self.assertEqual(grade_for_percentage(33, 33), 'D')
        self.assertEqual(grade_for_percentage(32.9, 33), 'F')
        self.assertEqual(grade_for_percentage(40, 40), 'D')
        self.assertEqual(grade_for_percentage(39.9, 40), 'F')
        self.assertEqual(grade_for_percentage(35, 40), 'F')
        self.assertEqual(grade_for_percentage(None, 33), 'F')

class MatricGradeLineTests(TestCase):
    def test_matric_page_shows_grade_line_and_inter_does_not(self):
        c = Client()
        c.force_login(User.objects.create_user(email='g@test.com', password='Str0ng!Pass12',
                                               full_name='G Test'))
        self.assertIn('<div id="matric-grade-line"', c.get('/matric/').content.decode())
        self.assertNotIn('<div id="matric-grade-line"', c.get('/inter/').content.decode())


class PhoneFieldTests(TestCase):
    @patch('career.views.send_otp_email', return_value=True)
    def test_phone_saved_through_otp_verification(self, mock_send):
        c = Client()
        r = c.post('/register/', {
            'full_name': 'Phone User', 'email': 'ph@test.com', 'phone': '03201234567',
            'password1': 'Str0ng!Pass12', 'password2': 'Str0ng!Pass12',
        })
        self.assertEqual(r.url, '/verify/')
        otp = EmailOTP.objects.filter(email='ph@test.com').latest('created_at')
        c.post('/verify/', {'code': otp.code})
        self.assertEqual(User.objects.get(email='ph@test.com').phone, '03201234567')

    @patch('career.views.send_otp_email', return_value=True)
    def test_phone_optional(self, mock_send):
        c = Client()
        _register(c, email='noph@test.com')
        otp = EmailOTP.objects.filter(email='noph@test.com').latest('created_at')
        c.post('/verify/', {'code': otp.code})
        self.assertEqual(User.objects.get(email='noph@test.com').phone, '')

    def test_register_page_shows_phone_field(self):
        c = Client()
        self.assertContains(c.get('/register/'), 'name="phone"')
