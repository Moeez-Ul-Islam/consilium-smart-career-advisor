import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db import IntegrityError
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import RegisterForm, LoginForm, OTPForm, UniversityForm, ForgotPasswordForm, ResetCodeForm, SetNewPasswordForm
from .models import University, AcademicRecord, PsychResult, EmailOTP
from .streams import (MATRIC_STREAMS, INTER_STREAMS,
                        DEFAULT_TOTALS_MATRIC, DEFAULT_TOTALS_INTER,
                        FA_ELECTIVE_GROUPS, FA_GROUPS_COUNT)
from .questions import QUESTIONS, LIKERT_LABELS, TEST_INSTRUCTION, ONET_CREDIT
from .scoring import get_top_careers, normalize_riasec, onet_personality_match, is_flat_profile
from .careers_data import TYPE_NAMES
from .brevo import send_otp_email, send_password_reset_email, EmailSendError
from .marksheet_ocr import extract_marks, MarksheetScanError
from .onet import enrich_career

User = get_user_model()

PENDING_SESSION_KEY = 'pending_registration'


def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'career/home.html')


def _make_otp(email):
    EmailOTP.objects.filter(email__iexact=email, is_used=False).update(is_used=True)
    code = '%06d' % secrets.randbelow(1_000_000)
    return EmailOTP.objects.create(
        email=email,
        code=code,
        expires_at=timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES),
    )


def check_email_view(request):
    email = (request.GET.get('email') or '').strip().lower()
    if not email or '@' not in email:
        return JsonResponse({'exists': False})
    exists = User.objects.filter(email__iexact=email).exists()
    return JsonResponse({'exists': exists})


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            full_name = form.cleaned_data['full_name']
            phone = form.cleaned_data.get('phone', '')
            password = form.cleaned_data['password1']
            otp = _make_otp(email)
            try:
                send_otp_email(email, otp.code, full_name)
            except EmailSendError as e:
                otp.delete()
                messages.error(request, str(e))
                return render(request, 'career/register.html', {'form': form})
            from django.contrib.auth.hashers import make_password
            request.session[PENDING_SESSION_KEY] = {
                'full_name': full_name,
                'email': email,
                'phone': phone,
                'password_hash': make_password(password),
            }
            messages.info(request,
                'A verification code has been sent to your email. Please enter the code.')
            return redirect('verify_otp')
        messages.error(request, 'There are some errors in the form. Please check below.')
    else:
        form = RegisterForm()
    return render(request, 'career/register.html', {'form': form})


def verify_otp_view(request):
    pending = request.session.get(PENDING_SESSION_KEY)
    if not pending:
        messages.warning(request, 'Please fill in the registration form first.')
        return redirect('register')
    email = pending['email']

    if request.method == 'POST':
        form = OTPForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            otp = EmailOTP.latest_valid(email)
            if otp is None or otp.is_expired():
                messages.error(request,
                    'The code has expired. Click "resend code" below.')
            elif otp.attempts >= settings.OTP_MAX_ATTEMPTS:
                messages.error(request,
                    'Too many wrong attempts. Please request a new code.')
            elif otp.code != code:
                otp.attempts += 1
                otp.save(update_fields=['attempts'])
                messages.error(request, 'Incorrect code. Please try again.')
            else:


                if User.objects.filter(email__iexact=email).exists():
                    messages.error(request,
                        'An account with this email already exists. Please log in.')
                    del request.session[PENDING_SESSION_KEY]
                    return redirect('login')
                otp.is_used = True
                otp.save(update_fields=['is_used'])
                user = User(email=email, full_name=pending['full_name'],
                            phone=pending.get('phone', ''))
                user.password = pending['password_hash']
                try:
                    user.save()
                except IntegrityError:
                    messages.error(request,
                        'An account with this email already exists. Please log in.')
                    del request.session[PENDING_SESSION_KEY]
                    return redirect('login')
                del request.session[PENDING_SESSION_KEY]
                login(request, user)
                messages.success(request,
                    'Email verified! Welcome, %s.' % user.full_name)
                return redirect('dashboard')
        else:
            messages.error(request, 'Please enter the code in the correct format (6 digits).')
    else:
        form = OTPForm()
    return render(request, 'career/verify_otp.html', {'form': form, 'email': email})


OTP_RESEND_LIMIT = 3
OTP_RESEND_WINDOW_MINUTES = 10


def _resend_count_recent(email):
    window_start = timezone.now() - timedelta(minutes=OTP_RESEND_WINDOW_MINUTES)
    return EmailOTP.objects.filter(
        email__iexact=email, created_at__gte=window_start).count()


@require_POST
def resend_otp_view(request):
    pending = request.session.get(PENDING_SESSION_KEY)
    if not pending:
        messages.warning(request, 'Please fill in the registration form first.')
        return redirect('register')
    email = pending['email']
    if _resend_count_recent(email) >= OTP_RESEND_LIMIT:
        messages.error(request,
            'Too many resend requests. Please wait 10 minutes and try again.')
        return redirect('verify_otp')
    otp = _make_otp(email)
    try:
        send_otp_email(email, otp.code, pending['full_name'])
    except EmailSendError as e:
        otp.delete()
        messages.error(request, str(e))
        return redirect('verify_otp')
    messages.info(request, 'A new code has been sent. Please check your inbox.')
    return redirect('verify_otp')


RESET_SESSION_KEY = 'pending_password_reset'
RESET_VERIFIED_KEY = 'password_reset_verified'


def forgot_password_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            user = User.objects.filter(email__iexact=email).first()

            if user:
                otp = _make_otp(email)
                try:
                    send_password_reset_email(email, otp.code, user.full_name)
                except EmailSendError as e:
                    otp.delete()
                    messages.error(request, str(e))
                    return render(request, 'career/forgot_password.html', {'form': form})
                request.session[RESET_SESSION_KEY] = {'email': email}
                messages.info(request,
                    'A reset code has been sent to your email. Please enter the code.')
                return redirect('reset_password')
            messages.info(request,
                'If an account exists for this email, a reset code has been sent.')
            return redirect('login')
    else:
        form = ForgotPasswordForm()
    return render(request, 'career/forgot_password.html', {'form': form})


def reset_password_view(request):
    pending = request.session.get(RESET_SESSION_KEY)
    if not pending:
        messages.warning(request, 'Please request a reset code first.')
        return redirect('forgot_password')
    email = pending['email']
    verified = request.session.get(RESET_VERIFIED_KEY) == email

    if request.method == 'POST':
        if not verified:

            form = ResetCodeForm(request.POST)
            if form.is_valid():
                code = form.cleaned_data['code']
                otp = EmailOTP.latest_valid(email)
                if otp is None or otp.is_expired():
                    messages.error(request,
                        'The code has expired. Please request a new one.')
                    return redirect('forgot_password')
                elif otp.attempts >= settings.OTP_MAX_ATTEMPTS:
                    messages.error(request,
                        'Too many wrong attempts. Please request a new code.')
                    return redirect('forgot_password')
                elif otp.code != code:
                    otp.attempts += 1
                    otp.save(update_fields=['attempts'])
                    messages.error(request, 'Incorrect code. Please try again.')
                else:
                    request.session[RESET_VERIFIED_KEY] = email
                    messages.success(request,
                        'Code verified. Now choose a new password.')
                    return redirect('reset_password')
            else:
                messages.error(request, 'Please fix the errors below.')
            return render(request, 'career/reset_password.html',
                          {'form': form, 'email': email, 'step': 1})
        else:

            form = SetNewPasswordForm(request.POST)
            if form.is_valid():
                otp = EmailOTP.latest_valid(email)
                if otp is None or otp.is_expired():
                    messages.error(request,
                        'The code has expired. Please request a new one.')
                    return redirect('forgot_password')
                otp.is_used = True
                otp.save(update_fields=['is_used'])
                user = User.objects.filter(email__iexact=email).first()
                if user:
                    user.set_password(form.cleaned_data['new_password1'])
                    user.save(update_fields=['password'])
                del request.session[RESET_SESSION_KEY]
                request.session.pop(RESET_VERIFIED_KEY, None)
                messages.success(request,
                    'Your password has been reset. Please log in with your new password.')
                return redirect('login')
            else:
                messages.error(request, 'Please fix the errors below.')
            return render(request, 'career/reset_password.html',
                          {'form': form, 'email': email, 'step': 2})
    else:
        if verified:
            form = SetNewPasswordForm()
            step = 2
        else:
            form = ResetCodeForm()
            step = 1
    return render(request, 'career/reset_password.html',
                  {'form': form, 'email': email, 'step': step})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, 'Welcome back, %s!' % (user.full_name or user.email))
            next_url = request.POST.get('next') or request.GET.get('next')

            if next_url and url_has_allowed_host_and_scheme(
                    next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
            return redirect('dashboard')
        messages.error(request, 'Login failed. Please check your details.')
    else:
        form = LoginForm(request)
    return render(request, 'career/login.html', {'form': form})


def universities_view(request):


    if not request.user.is_authenticated:
        from django.urls import reverse
        return redirect('%s?next=%s' % (reverse('login'), request.path))
    if not request.user.is_staff:
        messages.info(request,
            'The full universities list is managed by staff. '
            'Your recommended universities are shown on your results page.')
        return redirect('dashboard')
    universities = University.objects.all()
    grouped = {}
    for u in universities:
        grouped.setdefault(u.get_career_category_display(), []).append(u)
    return render(request, 'career/universities.html', {'grouped': grouped})


def _progress(user):
    matric_done = AcademicRecord.objects.filter(user=user, level='matric').exists()
    inter_done = AcademicRecord.objects.filter(user=user, level='inter').exists()
    test_done = PsychResult.objects.filter(user=user, completed=True).exists()
    return {'matric_done': matric_done, 'inter_done': inter_done, 'test_done': test_done}


def _first_missing_step(user):
    progress = _progress(user)
    if not progress['matric_done'] and not progress['inter_done'] and not progress['test_done']:
        return 'matric'
    if not progress['inter_done'] and not progress['test_done']:
        return 'inter'
    if not progress['test_done']:
        return 'test'
    return None


_STEP_URLS = {'matric': 'matric_entry', 'inter': 'inter_entry', 'test': 'psych_test'}


def _require_step(request, step):
    order = ['matric', 'inter', 'test', 'results']
    missing = _first_missing_step(request.user)
    if missing is None:
        return None
    if order.index(missing) < order.index(step):
        messages.info(request,
            'Please complete the %s step first to unlock this page.'
            % {'matric': 'Matric result', 'inter': 'Inter result',
               'test': 'personality test'}[missing])
        return redirect(_STEP_URLS[missing])
    return None


@login_required
def dashboard(request):
    progress = _progress(request.user)
    matric = AcademicRecord.objects.filter(user=request.user, level='matric').first()
    inter = AcademicRecord.objects.filter(user=request.user, level='inter').first()
    psych = PsychResult.objects.filter(user=request.user, completed=True).first()
    return render(request, 'career/dashboard.html', {
        'progress': progress,
        'matric': matric,
        'inter': inter,
        'psych': psych,
        'next_step': _first_missing_step(request.user),
    })


def _save_marks(request, level, streams):
    from .boards import passing_pct_for, board_name, BOARDS
    stream_key = request.POST.get('stream', '').strip()
    if stream_key not in streams:
        return None, 'Please select your stream.', []
    board_key = request.POST.get('board', '').strip()
    if board_key not in BOARDS:
        return None, 'Please select your board.', []
    passing_pct = passing_pct_for(board_key)
    stream = streams[stream_key]
    compulsory = stream['compulsory']
    optional = stream.get('optional', [])
    elective = stream['elective']

    if stream_key == 'fa':
        import json as _json
        try:
            picked = _json.loads(request.POST.get('fa_electives', '[]'))
        except (ValueError, TypeError):
            picked = []
        picked = [p for p in picked if p in elective]

        group_of = {}
        for gname, subjects in FA_ELECTIVE_GROUPS.items():
            for s in subjects:
                group_of[s] = gname
        picked_groups = [group_of.get(p) for p in picked]
        if len(picked) != FA_GROUPS_COUNT or len(set(picked_groups)) != FA_GROUPS_COUNT:
            return None, ('Please select exactly one elective subject from each '
                          'group (Group-I, Group-II, Group-III).'), []
        elective = picked
    subjects = compulsory + optional + elective

    subjects_data = {}


    max_idx = len(subjects) + 10
    for i in range(max_idx):
        subj_post = request.POST.get(f'subject_{i}', '').strip()
        if subj_post:

            if subj_post not in subjects:
                continue
            subj = subj_post
        elif f'obtained_{i}' in request.POST or f'total_{i}' in request.POST:

            if i >= len(subjects):
                continue
            subj = subjects[i]
        else:
            continue
        obt_raw = request.POST.get(f'obtained_{i}', '').strip()
        tot_raw = request.POST.get(f'total_{i}', '').strip()
        if obt_raw == '':


            continue
        if tot_raw == '':
            return None, f'Please enter the total marks for "{subj}".', []
        try:
            obtained = float(obt_raw)
            total = float(tot_raw)
        except ValueError:
            return None, f'"{subj}" has invalid marks. Please enter digits only.', []
        if obtained != int(obtained) or total != int(total):
            return None, f'"{subj}" has invalid marks. Whole numbers only, no decimals.', []
        obtained, total = int(obtained), int(total)
        if obtained < 0 or total <= 0:
            return None, f'"{subj}" has invalid marks. The total must be greater than 0.', []
        if total > 250:
            return None, f'Total marks for "{subj}" cannot be more than 250.', []
        if obtained > total:
            return None, f'Obtained marks for "{subj}" cannot be greater than the total.', []
        subjects_data[subj] = {'obtained': obtained, 'total': total}


    missing_comp = [s for s in compulsory if s not in subjects_data]
    if missing_comp:
        return None, ('Please enter marks for these compulsory subjects: %s.'
                      % ', '.join(missing_comp)), []

    elective_done = [s for s in elective if s in subjects_data]
    if len(elective_done) < 2:
        return None, ('Please enter marks for at least 2 elective subjects '
                      'for an accurate recommendation.'), []

    if not subjects_data:
        return None, 'Please enter marks for at least one subject.', []


    failed = [s for s, v in subjects_data.items()
              if v['obtained'] / v['total'] * 100 < passing_pct]
    warnings = []
    if failed:
        names = ', '.join('"%s"' % s for s in failed)
        if level == 'matric':

            return None, (
                'In Matric you must pass every subject to reach Inter. '
                f'{names} is below the passing marks ({passing_pct}%)'
                + (f' for {board_name(board_key)}' if board_key else '')
                + '. Please check your entry.'), []
        warnings.append(
            f'Below passing marks ({passing_pct}%) in {names} - please '
            f'double-check your entry. You can still submit (supply / '
            f'grace-marks cases).')

    record, _ = AcademicRecord.objects.get_or_create(
        user=request.user, level=level,
        defaults={'stream': stream_key})
    record.stream = stream_key
    record.board = board_key
    record.subjects_data = subjects_data
    uploaded = request.FILES.get('marksheet')
    if uploaded:
        ctype = (uploaded.content_type or '').split(';')[0].strip().lower()
        if uploaded.size > 8 * 1024 * 1024:
            return None, 'The marksheet image must be smaller than 8MB.', []
        if ctype not in ALLOWED_MARKSHEET_TYPES:
            return None, 'Please upload a JPG, PNG or WebP image of your marksheet.', []
        record.marksheet = uploaded
    record.recalc()
    record.save()
    return record, None, warnings


ALLOWED_MARKSHEET_TYPES = ('image/jpeg', 'image/png', 'image/webp')


def _posted_form_data(request, streams):
    stream_key = request.POST.get('stream', '').strip()
    board_key = request.POST.get('board', '').strip()
    stream = streams.get(stream_key)
    names = (stream['compulsory'] + stream.get('optional', [])
             + stream['elective']) if stream else []
    subjects = {}
    for i in range(len(names) + 10):
        subj_post = request.POST.get('subject_%d' % i, '').strip()
        if subj_post and subj_post in names:
            subj = subj_post
        elif 'obtained_%d' % i in request.POST or 'total_%d' % i in request.POST:
            if i >= len(names):
                continue
            subj = names[i]
        else:
            continue
        obt = request.POST.get('obtained_%d' % i, '').strip()
        tot = request.POST.get('total_%d' % i, '').strip()
        if obt == '' and tot == '':
            continue


        subjects[subj] = {'obtained': obt, 'total': tot}
    return {'stream': stream_key, 'board': board_key,
            'subjects': subjects,
            'fa_electives': request.POST.get('fa_electives', '')}


def _normalize_stream(stream_key):
    key = (stream_key or '').strip()
    if key == 'ics':
        return 'ics_physics'
    return key


def _posted_context(request, streams, record):
    posted = _posted_form_data(request, streams)
    return {
        'selected_stream': (_normalize_stream(posted['stream']) or
                            (_normalize_stream(record.stream) if record else '')),
        'selected_board': ((posted['board'] or '').strip() or
                           ((record.board or '').strip() if record else '')),
        'posted_subjects': (posted['subjects'] or None),
        'posted_fa_electives': posted['fa_electives'],
    }


@login_required
@require_POST
def scan_marksheet(request):
    f = request.FILES.get('marksheet')
    if not f:
        return JsonResponse({'ok': False, 'error': 'Please select a marksheet image first.'})
    if f.size > 8 * 1024 * 1024:
        return JsonResponse({'ok': False, 'error': 'The image must be smaller than 8MB.'})
    content_type = (f.content_type or '').split(';')[0].strip().lower()
    if content_type not in ALLOWED_MARKSHEET_TYPES:
        return JsonResponse({'ok': False,
            'error': 'Please upload a JPG, PNG or WebP image of your marksheet.'})
    try:
        result = extract_marks(f.read(), content_type or 'image/jpeg')
    except MarksheetScanError as e:
        return JsonResponse({'ok': False, 'error': str(e)})
    except Exception:

        return JsonResponse({'ok': False,
            'error': 'The scan failed unexpectedly. Please use manual entry.'})
    return JsonResponse({'ok': True, 'subjects': result['subjects'],
                         'board': result['board']})


def _has_completed_result(user):
    return PsychResult.objects.filter(user=user, completed=True).exists()


def _after_save_redirect(request, label, record, next_url_name):
    wants_update = request.POST.get('action') == 'update_result'
    if wants_update and _has_completed_result(request.user):
        messages.success(request,
            '%s result updated! (%.1f%%)' % (label, record.percentage))
        return redirect('results')
    messages.success(request, '%s result saved! (%.1f%%)' % (label, record.percentage))
    return redirect(next_url_name)


@login_required
def matric_entry(request):
    from .boards import board_choices, BOARDS
    existing = AcademicRecord.objects.filter(user=request.user, level='matric').first()
    if request.method == 'POST':
        record, err, _warnings = _save_marks(request, 'matric', MATRIC_STREAMS)
        if err:
            messages.error(request, err)
        else:
            return _after_save_redirect(request, 'Matric', record, 'inter_entry')
    else:
        record = existing
    context = {
        'streams': MATRIC_STREAMS,
        'record': record,
        'level': 'matric',
        'level_name': 'Matric',
        'next_url': 'inter_entry',
        'back_url': 'dashboard',
        'has_result': _has_completed_result(request.user),
        'default_totals': DEFAULT_TOTALS_MATRIC,
        'board_groups': board_choices(),
        'boards_json': BOARDS,
    }
    if request.method == 'POST':


        context.update(_posted_context(request, MATRIC_STREAMS, record))
    else:

        context['selected_stream'] = _normalize_stream(record.stream) if record else ''
        context['selected_board'] = (record.board or '').strip() if record else ''
        context['posted_subjects'] = None
        context['posted_fa_electives'] = ''
    return render(request, 'career/marks_entry.html', context)


@login_required
def inter_entry(request):
    from .boards import board_choices, BOARDS
    guard = _require_step(request, 'inter')
    if guard:
        return guard
    existing = AcademicRecord.objects.filter(user=request.user, level='inter').first()
    if request.method == 'POST':
        record, err, warnings = _save_marks(request, 'inter', INTER_STREAMS)
        if err:
            messages.error(request, err)
        else:
            for w in warnings:
                messages.warning(request, w)
            label = 'Inter'
            return _after_save_redirect(request, label, record, 'psych_test')
    else:
        record = existing
    context = {
        'streams': INTER_STREAMS,
        'record': record,
        'level': 'inter',
        'level_name': 'Inter',
        'next_url': 'psych_test',
        'back_url': 'matric_entry',
        'has_result': _has_completed_result(request.user),
        'default_totals': DEFAULT_TOTALS_INTER,
        'board_groups': board_choices(),
        'boards_json': BOARDS,
        'fa_groups': FA_ELECTIVE_GROUPS,
        'fa_groups_count': FA_GROUPS_COUNT,
    }
    if request.method == 'POST':


        context.update(_posted_context(request, INTER_STREAMS, record))
    else:

        context['selected_stream'] = _normalize_stream(record.stream) if record else ''
        context['selected_board'] = (record.board or '').strip() if record else ''
        context['posted_subjects'] = None
        context['posted_fa_electives'] = ''
    return render(request, 'career/marks_entry.html', context)


@login_required
@require_POST
def delete_record(request, level):
    if level not in ('matric', 'inter'):
        raise Http404('No such result.')
    record = AcademicRecord.objects.filter(user=request.user, level=level).first()
    if record is None:
        messages.info(request, 'No %s result to delete.' % level.capitalize())
    else:
        if record.marksheet:
            record.marksheet.delete(save=False)
        record.delete()
        messages.success(request,
            '%s result deleted. You can enter it again any time.' % level.capitalize())
    return redirect('dashboard')


@login_required
def psych_test(request):
    guard = _require_step(request, 'test')
    if guard:
        return guard
    existing = PsychResult.objects.filter(user=request.user).first()
    if request.method == 'POST':
        answers = {}
        for i in range(1, len(QUESTIONS) + 1):
            raw = request.POST.get(f'q{i}', '').strip()
            try:
                val = int(raw)
            except ValueError:
                val = 0
            if val < 1 or val > 5:
                messages.error(request, f'Please answer question #{i} (1-5).')
                return render(request, 'career/psych_test.html',
                              {'questions': list(enumerate(QUESTIONS, start=1)),
                               'likert': LIKERT_LABELS,
                               'instruction': TEST_INSTRUCTION,
                               'onet_credit': ONET_CREDIT})
            answers[f'q{i}'] = val

        scores = {t: 0 for t in 'RIASEC'}
        for i, (_, t) in enumerate(QUESTIONS, start=1):
            scores[t] += answers[f'q{i}']
        dominant = max(scores, key=lambda k: scores[k])

        pr, _ = PsychResult.objects.get_or_create(user=request.user)
        pr.answers = answers
        pr.scores = scores
        pr.dominant = dominant
        pr.completed = True
        pr.save()
        if is_flat_profile(scores):
            messages.success(request, 'Test complete! No strong personality type emerged '
                                      '(same answer to every question) - your recommendations '
                                      'will lean on your academics.')
        else:
            messages.success(request, 'Test complete! Your personality type: %s' % TYPE_NAMES[dominant])
        return redirect('results')

    return render(request, 'career/psych_test.html',
                  {'questions': list(enumerate(QUESTIONS, start=1)),
                   'likert': LIKERT_LABELS,
                   'instruction': TEST_INSTRUCTION,
                   'onet_credit': ONET_CREDIT,
                   'existing': existing})


def _results_data(user):
    top3 = get_top_careers(user, 3)
    pr = PsychResult.objects.get(user=user)
    norm_scores = normalize_riasec(pr.scores)
    for c in top3:
        c['universities'] = list(University.objects.filter(career_category=c['univ_category'])[:4])
        onet = enrich_career(c.get('key'))
        if onet:
            onet = dict(onet)
            if onet.get('interests'):
                onet['match_rows'] = onet_personality_match(onet['interests'], norm_scores)
        c['onet'] = onet

    matric = AcademicRecord.objects.get(user=user, level='matric')
    inter = AcademicRecord.objects.get(user=user, level='inter')

    return {
        'top3': top3,
        'scores': pr.scores,
        'scores_named': [(TYPE_NAMES.get(k, k), v) for k, v in pr.scores.items()],
        'dominant': pr.dominant,
        'dominant_name': 'No clear type' if is_flat_profile(pr.scores) else TYPE_NAMES[pr.dominant],
        'norm_scores': norm_scores,
        'matric': matric,
        'inter': inter,
    }


@login_required
def results(request):
    guard = _require_step(request, 'results')
    if guard:
        return guard


    progress = _progress(request.user)
    if not progress['matric_done'] or not progress['inter_done'] or not progress['test_done']:
        missing = 'matric' if not progress['matric_done'] else ('inter' if not progress['inter_done'] else 'test')
        messages.info(request,
            'Please complete the %s step first to see your results.'
            % {'matric': 'Matric result', 'inter': 'Inter result',
               'test': 'personality test'}[missing])
        return redirect(_STEP_URLS[missing])

    data = _results_data(request.user)
    context = dict(data)
    context['type_names'] = TYPE_NAMES
    return render(request, 'career/results.html', context)


@login_required
def results_pdf(request):
    guard = _require_step(request, 'results')
    if guard:
        return guard

    data = _results_data(request.user)
    pdf_bytes = _build_results_pdf(request.user, data)
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = 'attachment; filename="consilium_recommendations.pdf"'
    return resp


def _build_results_pdf(user, data):
    import io
    from xml.sax.saxutils import escape
    from datetime import date
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph,
                                    HRFlowable, ListFlowable, ListItem)

    TEAL = HexColor('#38a3a5')
    NAVY = HexColor('#22577a')
    INK = HexColor('#1e2a32')
    MUTED = HexColor('#5c6f78')

    base = ParagraphStyle('base', fontName='Helvetica', fontSize=10,
                          leading=14, textColor=INK, alignment=TA_LEFT)
    h1 = ParagraphStyle('h1', parent=base, fontName='Helvetica-Bold',
                        fontSize=18, leading=22, textColor=NAVY, spaceAfter=4)
    h2 = ParagraphStyle('h2', parent=base, fontName='Helvetica-Bold',
                        fontSize=13, leading=16, textColor=TEAL, spaceBefore=12,
                        spaceAfter=6)
    h3 = ParagraphStyle('h3', parent=base, fontName='Helvetica-Bold',
                        fontSize=11, leading=14, textColor=NAVY, spaceBefore=8,
                        spaceAfter=4)
    small = ParagraphStyle('small', parent=base, fontSize=9, leading=12,
                           textColor=MUTED)
    def p(text, style=base):
        return Paragraph(escape(text), style)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title='Consilium Career Recommendations')
    story = []
    name = getattr(user, 'full_name', '') or user.email

    story.append(p('Consilium - Smart Career Advisor', h1))
    story.append(p('Your Career Recommendations', h2))
    story.append(p('Prepared for %s on %s' % (name, date.today().isoformat()), small))
    story.append(HRFlowable(width='100%', thickness=1, color=TEAL, spaceAfter=8))


    story.append(p('Your Profile', h2))
    story.append(p('Personality Type: %s' % data['dominant_name']))
    prof_lines = ['%s: %s/25' % (n, s) for n, s in data['scores_named']]
    story.append(p('RIASEC scores - ' + ', '.join(prof_lines)))
    story.append(p('Matric: %s%%   |   Inter: %s%%'
                   % (data['matric'].percentage, data['inter'].percentage)))
    story.append(p('Scoring formula: Matric 30% + Inter 40% + Personality fit 30%.',
                   small))


    for i, c in enumerate(data['top3'], start=1):
        story.append(p('#%d - %s (%s%%)' % (i, c['name'], c['score']), h2))
        story.append(p(c['desc']))
        story.append(p('Why this fits you: ' + c['reasoning']))
        if c.get('admission_note'):
            story.append(p(c['admission_note'], small))

        story.append(p('Recommended Bachelor Degrees (ranked)', h3))
        story.append(ListFlowable(
            [ListItem(p('%s - %s%%%s' % (
                d['name'], d['score'],
                ' [bridging required]' if d['bridge'] else '')), leftIndent=14)
             for d in c['degrees']],
            bulletType='bullet', start='\u2022'))

        story.append(p('Top Universities in Pakistan', h3))
        unis = data['top3'][i - 1]['universities']
        if unis:
            story.append(ListFlowable(
                [ListItem(p('%s, %s' % (u.name, u.city)), leftIndent=14)
                 for u in unis],
                bulletType='bullet', start='\u2022'))
        else:
            story.append(p('Universities will be added soon.', small))

        onet = c.get('onet')
        if onet:
            story.append(p('O*NET Official Data (U.S. Dept. of Labor)', h3))
            story.append(p('%s (SOC %s)' % (onet.get('title', ''),
                                            onet.get('soc_code', '')), small))
            if onet.get('description'):
                story.append(p(onet['description']))
        story.append(HRFlowable(width='100%', thickness=0.5, color=MUTED,
                                spaceBefore=6, spaceAfter=4))

    story.append(p('Generated by Consilium - Smart Career Advisor. '
                   'O*NET data: U.S. Department of Labor, Employment and '
                   'Training Administration.', small))
    doc.build(story)
    return buf.getvalue()


def feedback_view(request):
    from .models import Feedback as FB
    valid_cats = [k for k, _ in FB.CATEGORY_CHOICES]
    if request.method == 'POST':
        category = request.POST.get('category', 'general')
        if category not in valid_cats:
            category = 'general'
        try:
            rating = int(request.POST.get('rating', 5))
        except (TypeError, ValueError):
            rating = 5
        rating = max(1, min(5, rating))
        message = request.POST.get('message', '').strip()
        if not message:
            messages.error(request, 'Please write your feedback message.')
        elif len(message) > 2000:
            messages.error(request, 'Feedback message is too long (max 2000 characters).')
        else:
            FB.objects.create(
                user=request.user if request.user.is_authenticated else None,
                category=category, rating=rating, message=message)
            messages.success(request, 'Thank you for your feedback!')
            return redirect('feedback')
    initial = request.GET.get('category', 'general')
    if initial not in valid_cats:
        initial = 'general'
    return render(request, 'career/feedback.html',
                  {'categories': FB.CATEGORY_CHOICES, 'initial': initial})


@staff_member_required
def manage_universities(request):
    from .models import Feedback as FB
    universities = University.objects.all()
    users = User.objects.all().order_by('-date_joined')
    feedbacks = FB.objects.select_related('user').order_by('-created_at')[:50]
    return render(request, 'career/manage_universities.html',
                  {'universities': universities, 'users': users,
                   'feedbacks': feedbacks})


@staff_member_required
def university_add(request):
    if request.method == 'POST':
        form = UniversityForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'University added.')
            return redirect('manage_universities')
        messages.error(request, 'There is an error in the form, please check it.')
    else:
        form = UniversityForm()
    return render(request, 'career/university_form.html', {'form': form, 'title': 'Add University'})


@staff_member_required
def university_edit(request, pk):
    uni = get_object_or_404(University, pk=pk)
    if request.method == 'POST':
        form = UniversityForm(request.POST, instance=uni)
        if form.is_valid():
            form.save()
            messages.success(request, 'University updated.')
            return redirect('manage_universities')
        messages.error(request, 'There is an error in the form, please check it.')
    else:
        form = UniversityForm(instance=uni)
    return render(request, 'career/university_form.html',
                  {'form': form, 'title': 'Edit University'})


@staff_member_required
def university_delete(request, pk):
    uni = get_object_or_404(University, pk=pk)
    if request.method == 'POST':
        uni.delete()
        messages.success(request, 'University deleted.')
        return redirect('manage_universities')
    return render(request, 'career/university_confirm_delete.html', {'uni': uni})
