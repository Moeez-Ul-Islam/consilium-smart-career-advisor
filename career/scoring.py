
from .careers_data import CAREERS
from .degrees_data import DEGREES

TRAIT_FULL_NAMES = {
    'R': 'Realistic',
    'I': 'Investigative',
    'A': 'Artistic',
    'S': 'Social',
    'E': 'Enterprising',
    'C': 'Conventional',
}


W_MATRIC, W_INTER, W_PSYCH = 0.30, 0.40, 0.30
W_SUBJECT_IN_ACADEMIC = 0.5
W_OVERALL_IN_ACADEMIC = 0.5
W_ACADEMIC_FINAL = 0.7
W_PSYCH_FINAL = 0.3
MISSING_SUBJECT_PENALTY = 0.7

HEC_MATH_NOTE = (
    "Admission note: you didn't study Mathematics at Inter level. HEC requires "
    "6 credit hours of Additional Mathematics in the first year for BS "
    "computing programs.")
PEC_MATH_NOTE = (
    "Admission note: you didn't study Mathematics at Inter level. PEC requires "
    "an 8-week condensed Mathematics program and 60% marks in HSSC for BS "
    "engineering programs.")


def normalize_riasec(raw_scores):
    norm = {}
    for t in 'RIASEC':
        raw = float(raw_scores.get(t, 15))
        norm[t] = round(max(0.0, min(100.0, (raw - 5) / 20 * 100)), 1)
    return norm


def subject_pct(subjects_data, name):
    vals = (subjects_data or {}).get(name)
    if not vals:
        return None
    try:
        total = float(vals.get('total') or 0)
        obtained = float(vals.get('obtained') or 0)
    except (TypeError, ValueError):
        return None
    if total <= 0:
        return None
    return obtained / total * 100


def weighted_subject_avg(subjects_data, weights):
    total, wsum = 0.0, 0.0
    for name, w in (weights or {}).items():
        pct = subject_pct(subjects_data, name)
        if pct is None:
            continue
        total += pct * w
        wsum += w
    if wsum <= 0:
        return None
    return total / wsum


def matched_subjects(matric_subjects, inter_subjects, weights):
    found = {}
    for level in (matric_subjects, inter_subjects):
        for name in (weights or {}):
            pct = subject_pct(level, name)
            if pct is not None:
                found.setdefault(name, []).append(pct)
    matched = [{'subject': name, 'pct': round(sum(pcts) / len(pcts), 1)}
               for name, pcts in found.items()]
    matched.sort(key=lambda m: m['pct'], reverse=True)
    return matched


def score_degree(degree, matric_subjects, inter_subjects,
                 matric_pct, inter_pct, norm_scores):
    overall = (matric_pct * W_MATRIC + inter_pct * W_INTER) / (W_MATRIC + W_INTER)
    overall = round(max(0.0, min(100.0, overall)), 1)

    notes = []
    bridge = False


    missing_required = [s for s in degree.get('required', [])
                        if subject_pct(inter_subjects, s) is None]
    if missing_required:
        bridge = True
        subject_fit = round(overall * MISSING_SUBJECT_PENALTY, 1)
        subject_avg = None
        notes.append(
            f"Note: {', '.join(missing_required)} is required for {degree['name']} "
            f"(FSc Pre-Medical). You'll need to study it before admission.")
    else:
        m_avg = weighted_subject_avg(matric_subjects, degree['subjects'])
        i_avg = weighted_subject_avg(inter_subjects, degree['subjects'])
        parts = []
        if m_avg is not None:
            parts.append((m_avg, W_MATRIC))
        if i_avg is not None:
            parts.append((i_avg, W_INTER))
        if not parts:
            bridge = True
            subject_fit = round(overall * MISSING_SUBJECT_PENALTY, 1)
            subject_avg = None
            notes.append(
                f"Note: you haven't studied the key subjects for {degree['name']} "
                f"yet - you'll need extra preparation (bridging) to enter this field.")
        else:
            combined = sum(a * w for a, w in parts) / sum(w for _, w in parts)
            subject_avg = round(combined, 1)
            ideal = degree['ideal']
            subject_fit = round(min(100.0, combined / ideal * 100) if ideal > 0 else 0.0, 1)

    academic = round(min(100.0, subject_fit * W_SUBJECT_IN_ACADEMIC
                         + overall * W_OVERALL_IN_ACADEMIC), 1)


    keys = degree['riasec']
    ideal = degree['ideal']
    breakdown, wsum, total_w = {}, 0.0, 0
    for t in 'RIASEC':
        target = ideal if t in keys else 50
        fit = max(0.0, 100.0 - abs(float(norm_scores.get(t, 50)) - target) * 1.25)
        w = 3 if t in keys else 1
        breakdown[t] = round(fit, 1)
        wsum += fit * w
        total_w += w
    psych = round(wsum / total_w, 1)


    final = round(min(100.0, academic * W_ACADEMIC_FINAL + psych * W_PSYCH_FINAL), 1)

    return {
        'key': degree['key'],
        'name': degree['name'],
        'career': degree['career'],
        'score': final,
        'academic_fit': academic,
        'psych_fit': psych,
        'subject_fit': subject_fit,
        'subject_avg': subject_avg,
        'overall_pct': overall,
        'matched': matched_subjects(matric_subjects, inter_subjects, degree['subjects']),
        'psych_breakdown': breakdown,
        'bridge': bridge,
        'notes': notes,
    }


def score_all_degrees(matric_pct, inter_pct, matric_subjects, inter_subjects,
                      norm_scores):
    results = [score_degree(d, matric_subjects, inter_subjects,
                            matric_pct, inter_pct, norm_scores)
               for d in DEGREES]
    results.sort(key=lambda r: r['score'], reverse=True)
    return results


def career_admission_note(career_key, inter_subjects):
    has_math = subject_pct(inter_subjects, 'Mathematics') is not None
    if has_math:
        return ''
    if career_key == 'cs':
        return HEC_MATH_NOTE
    if career_key == 'engineering':
        return PEC_MATH_NOTE
    return ''


def is_flat_profile(scores):
    vals = list((scores or {}).values())
    return len(vals) == 6 and len(set(vals)) == 1


def build_career_reasoning(career_name, degrees, norm_scores):
    top = degrees[0]
    if is_flat_profile(norm_scores):

        return (f"Your personality test didn't show a strong lean in any direction, "
                f"so this match is based mainly on your academics. "
                f"Top degree: {top['name']} ({top['score']}%).")
    bit = ''
    if top['matched']:
        best = top['matched'][0]
        bit = f"Your {best['pct']}% in {best['subject']}, "
    top_traits = sorted(norm_scores, key=lambda t: norm_scores[t], reverse=True)[:2]
    trait_str = ' and '.join(
        f"{TRAIT_FULL_NAMES[t]} ({norm_scores[t]}/100)" for t in top_traits)
    return (f"{bit}high {trait_str} in your personality - that's why {career_name} "
            f"is a strong match for you. Top degree: {top['name']} ({top['score']}%).")


def group_into_careers(degree_results, inter_subjects, norm_scores):
    careers = []
    for c in CAREERS:
        degs = sorted((d for d in degree_results if d['career'] == c['key']),
                      key=lambda d: d['score'], reverse=True)
        avg = round(sum(d['score'] for d in degs) / len(degs), 1) if degs else 0.0
        careers.append({
            'key': c['key'],
            'name': c['name'],
            'desc': c['desc'],
            'score': avg,
            'degrees': degs,
            'univ_category': c['univ_category'],
            'admission_note': career_admission_note(c['key'], inter_subjects),
            'reasoning': build_career_reasoning(c['name'], degs, norm_scores) if degs else '',
        })
    careers.sort(key=lambda c: c['score'], reverse=True)
    return careers


def onet_personality_match(interests, norm_scores):
    name_to_letter = {v: k for k, v in TRAIT_FULL_NAMES.items()}
    rows = []
    for name in interests or []:
        clean = str(name).strip()
        letter = name_to_letter.get(clean)
        if not letter:
            continue
        score = round(max(0.0, min(100.0, float(norm_scores.get(letter, 0)))), 1)
        if score >= 70:
            level = 'Strong match'
        elif score >= 40:
            level = 'Moderate'
        else:
            level = 'Developing'
        rows.append({'letter': letter, 'name': clean,
                     'student_score': score, 'level': level})
    return rows


def _get_record(user, level):
    from .models import AcademicRecord
    try:
        return AcademicRecord.objects.get(user=user, level=level)
    except AcademicRecord.DoesNotExist:
        return None


def score_user(user):
    from .models import PsychResult

    matric_rec = _get_record(user, 'matric')
    inter_rec = _get_record(user, 'inter')

    matric_pct = matric_rec.percentage if matric_rec else 0.0
    inter_pct = inter_rec.percentage if inter_rec else 0.0
    matric_subjects = matric_rec.subjects_data if matric_rec else {}
    inter_subjects = inter_rec.subjects_data if inter_rec else {}

    try:
        pr = PsychResult.objects.get(user=user, completed=True)
        norm_scores = normalize_riasec(pr.scores)
    except PsychResult.DoesNotExist:
        norm_scores = {t: 50.0 for t in 'RIASEC'}

    degree_results = score_all_degrees(matric_pct, inter_pct, matric_subjects,
                                       inter_subjects, norm_scores)
    return group_into_careers(degree_results, inter_subjects, norm_scores)


def get_top_careers(user, n=3):
    return score_user(user)[:n]


def score_careers(user):
    return score_user(user)


def run_validation():
    print('=== Scoring engine validation ===')
    passed, failed = 0, 0

    def check(name, condition, detail=''):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f'  PASS: {name}')
        else:
            failed += 1
            print(f'  FAIL: {name} {detail}')

    ics_matric = {
        'Computer Science': {'obtained': 90, 'total': 100},
        'Mathematics': {'obtained': 85, 'total': 100},
        'Physics': {'obtained': 80, 'total': 100},
        'English': {'obtained': 75, 'total': 100},
    }
    ics_inter = {
        'Computer Science': {'obtained': 92, 'total': 100},
        'Mathematics': {'obtained': 88, 'total': 100},
        'Physics': {'obtained': 82, 'total': 100},
        'English': {'obtained': 78, 'total': 100},
    }
    cs_norm = {'I': 85, 'C': 80, 'R': 60, 'E': 50, 'A': 45, 'S': 40}


    degs = score_all_degrees(85, 88, ics_matric, ics_inter, cs_norm)
    careers = group_into_careers(degs, ics_inter, cs_norm)
    check('ICS student -> 46 degrees scored', len(degs) == 46, f'got {len(degs)}')
    check('ICS student -> top career is Computer Science',
          careers[0]['key'] == 'cs', f"got {careers[0]['key']}")
    check('ICS student (high Conventional) -> [I,C] degrees lead CS',
          any(d['key'] in ('bs_it', 'bs_cyber', 'bs_ds')
              for d in careers[0]['degrees'][:3]),
          f"got {[d['key'] for d in careers[0]['degrees'][:3]]}")
    check('All scores within 0..100',
          all(0 <= d['score'] <= 100 for d in degs))
    check('Degree results carry the standard score fields',
          all(set(d) == {'key', 'name', 'career', 'score', 'academic_fit',
                         'psych_fit', 'subject_fit', 'subject_avg',
                         'overall_pct', 'matched', 'psych_breakdown',
                         'bridge', 'notes'} for d in degs))


    pre_matric = {
        'Biology': {'obtained': 92, 'total': 100},
        'Chemistry': {'obtained': 88, 'total': 100},
        'Physics': {'obtained': 85, 'total': 100},
        'Mathematics': {'obtained': 80, 'total': 100},
    }
    pre_inter = {
        'Biology': {'obtained': 94, 'total': 100},
        'Chemistry': {'obtained': 90, 'total': 100},
        'Physics': {'obtained': 86, 'total': 100},
    }
    med_norm = {'I': 80, 'S': 85, 'C': 60, 'R': 55, 'A': 50, 'E': 45}
    degs2 = score_all_degrees(90, 92, pre_matric, pre_inter, med_norm)
    careers2 = group_into_careers(degs2, pre_inter, med_norm)
    check('Pre-medical student -> Medicine in top 3',
          'medicine' in [cc['key'] for cc in careers2[:3]],
          f"got {[cc['key'] for cc in careers2[:3]]}")
    mbbs = next(d for d in degs2 if d['key'] == 'mbbs')
    check('Pre-medical student -> MBBS has no bridge', not mbbs['bridge'])
    check('Pre-medical student -> CS degrees carry the HEC math note',
          careers2 and any(c['key'] == 'cs' and 'Additional Mathematics' in c['admission_note']
                           for c in careers2))


    degs3 = score_all_degrees(85, 88, ics_matric, ics_inter, cs_norm)
    mbbs3 = next(d for d in degs3 if d['key'] == 'mbbs')
    check('ICS student -> MBBS gets bridge (Biology required)',
          mbbs3['bridge'] and any('Biology' in n for n in mbbs3['notes']))
    check('ICS student -> bridge penalty math (overall*0.7)',
          mbbs3['subject_fit'] == round(mbbs3['overall_pct'] * 0.7, 1))


    a = score_degree(next(d for d in DEGREES if d['key'] == 'bs_cs'),
                     ics_matric, ics_inter, 85, 88, cs_norm)
    check('final = academic*0.7 + psych*0.3 exactly',
          a['score'] == round(min(100, a['academic_fit'] * 0.7 + a['psych_fit'] * 0.3), 1))


    check('5 careers ranked desc',
          len(careers) == 5 and all(careers[i]['score'] >= careers[i + 1]['score']
                                   for i in range(4)))
    check('degrees ranked desc inside each career',
          all(all(c['degrees'][i]['score'] >= c['degrees'][i + 1]['score']
                    for i in range(len(c['degrees']) - 1)) for c in careers))


    perfect = score_degree(
        next(d for d in DEGREES if d['key'] == 'mbbs'),
        {'Biology': {'obtained': 100, 'total': 100},
         'Chemistry': {'obtained': 100, 'total': 100}},
        {'Biology': {'obtained': 100, 'total': 100},
         'Chemistry': {'obtained': 100, 'total': 100}},
        100, 100, {'R': 50, 'I': 95, 'A': 50, 'S': 95, 'E': 50, 'C': 50})
    check('Ideal MBBS profile -> psych fit is 100', perfect['psych_fit'] == 100,
          f"got {perfect['psych_fit']}")

    print(f'=== {passed} passed, {failed} failed ===')
    return failed == 0
