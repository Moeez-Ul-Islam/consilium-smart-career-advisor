import base64
import json
import logging
import re
import time

import requests
from django.conf import settings

from .boards import BOARDS


logger = logging.getLogger(__name__)


class MarksheetScanError(RuntimeError):
    pass


def _board_list_for_prompt():
    return ', '.join(f'{k}={v["name"]}' for k, v in BOARDS.items())


_PROMPT = (
    'You are a marksheet reader for Pakistani board results. '
    'Read the image carefully and return STRICT JSON only - no markdown, no code fences, no explanation.\n'
    'Exact format: {"board": "fbise", '
    '"subjects": [{"subject": "Physics", "obtained": 115, "total": 150}]}.\n'
    'BOARD: read the board name from the top/header of the result card and return its key from this list: '
    + _board_list_for_prompt() +
    '. If the board is not readable, use null.\n'
    'SUBJECTS - Pakistani cards split subjects across rows, so follow these rules:\n'
    '1. COMBINE split rows into ONE entry per subject and SUM the obtained marks. '
    'Example: "PHYSICS - I (THEORY)" 44 + "PHYSICS - II (THEORY)" 51 + the "PRACTICAL MARKS" column 20 '
    'becomes ONE entry {"subject": "Physics", "obtained": 115}. '
    'Similarly "ENGLISH - I (COMPULSORY)" 60 + "ENGLISH - II (COMPULSORY)" 62 becomes {"subject": "English", "obtained": 122}.\n'
    '2. Use exactly these subject names: English, Urdu, Mathematics, Physics, Chemistry, Biology, '
    'Computer Science, Economics, Statistics, Fashion Designing, Communication Skills, Islamiat, Islamic Studies, Pak Studies, Tarjuma-tul-Quran. '
    'Map "PAKISTAN STUDIES - I/II" to "Pak Studies". Strip suffixes like "- I (THEORY)", "- II (COMPULSORY)".\n'
    '3. TOTAL: if the card shows maximum marks per subject, use them (summed for combined subjects). '
    'If the card does not show totals, use null - never guess.\n'
    'If a value is unreadable, use null for it. Numbers only, no text.'
)


def _extract_json(text):
    if not text:
        raise MarksheetScanError('The AI did not return an answer. Please use manual entry.')
    text = text.strip()

    text = re.sub(r'^```(?:json)?', '', text).strip()
    text = re.sub(r'```$', '', text).strip()
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1 or end <= start:
        raise MarksheetScanError(
            'The AI could not understand the numbers. Please use manual entry.')
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        raise MarksheetScanError(
            'The AI response could not be understood. Please use manual entry.')


_SUBJECT_ALIASES = {
    'english': 'English',
    'urdu': 'Urdu',
    'mathematics': 'Mathematics', 'maths': 'Mathematics', 'math': 'Mathematics',
    'physics': 'Physics',
    'chemistry': 'Chemistry',
    'biology': 'Biology',
    'computer science': 'Computer Science', 'computer': 'Computer Science',
    'economics': 'Economics', 'statistics': 'Statistics', 'stats': 'Statistics',
    'fashion designing': 'Fashion Designing', 'fashion design': 'Fashion Designing',
    'communication skills': 'Communication Skills',
    'islamiat': 'Islamiat', 'islamiyat': 'Islamiat',
    'islamic studies': 'Islamic Studies',
    'pak studies': 'Pak Studies', 'pakistan studies': 'Pak Studies',
    'tarjuma-tul-quran': 'Tarjuma-tul-Quran', 'tarjumatulquran': 'Tarjuma-tul-Quran',
}


def _canon_subject(name):
    raw = str(name).strip()
    n = re.sub(r'\s+', ' ', raw.lower())
    n = re.sub(r'\s*\([^)]*\)', '', n)
    n = re.sub(r'\s*[-\u2013]\s*(i{1,3}|iv|v)$', '', n)
    n = re.sub(r'\bpracticals?\b', '', n)
    n = re.sub(r'\s+', ' ', n).strip(' -')
    if not n:
        return raw
    return _SUBJECT_ALIASES.get(n, raw)


def _combine_subjects(cleaned):
    grouped = {}
    order = []
    for item in cleaned:
        key = _canon_subject(item['subject']).lower()
        if key not in grouped:
            grouped[key] = {'subject': _canon_subject(item['subject']),
                            'obtained': None, 'total': None}
            order.append(key)
        g = grouped[key]
        if item['obtained'] is not None:
            g['obtained'] = (g['obtained'] or 0) + item['obtained']
        if item['total'] is not None:
            g['total'] = (g['total'] or 0) + item['total']
    return [grouped[k] for k in order]


def _post_with_retry(url, api_key, payload, attempts=3):
    resp = None
    for attempt in range(attempts):
        try:
            resp = requests.post(url, params={'key': api_key}, json=payload, timeout=60)
        except requests.RequestException:
            resp = None
            if attempt < attempts - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise
        if resp.status_code in (429, 503):
            logger.warning('Marksheet scan: HTTP %s on attempt %d/%d',
                           resp.status_code, attempt + 1, attempts)
            if attempt < attempts - 1:
                time.sleep(4 * (attempt + 1))
                continue
        break
    return resp


def extract_marks(image_bytes, mime_type='image/jpeg'):
    api_key = getattr(settings, 'GEMINI_API_KEY', '') or ''
    if not api_key:
        raise MarksheetScanError('The scanner is not configured. Please use manual entry.')

    b64 = base64.b64encode(image_bytes).decode('ascii')
    url = ('https://generativelanguage.googleapis.com/v1beta/'
           'models/gemini-3.5-flash:generateContent')
    payload = {
        'contents': [{
            'parts': [
                {'text': _PROMPT},
                {'inlineData': {'mimeType': mime_type, 'data': b64}},
            ]
        }],
        'generationConfig': {'temperature': 0.1, 'maxOutputTokens': 2048},
    }
    try:
        resp = _post_with_retry(url, api_key, payload)
    except requests.RequestException:
        raise MarksheetScanError(
            'Could not reach the AI service. Please check your internet connection and try again.')
    if resp.status_code == 429 or resp.status_code == 503:
        raise MarksheetScanError(
            'The AI service is busy right now. Please try again in a minute or use manual entry.')
    if resp.status_code != 200:
        logger.warning('Marksheet scan failed with HTTP %s', resp.status_code)
        raise MarksheetScanError(
            'The scan failed. Please use manual entry.')

    try:
        data = resp.json()
        text = data['candidates'][0]['content']['parts'][0]['text']
    except (KeyError, IndexError, ValueError):
        raise MarksheetScanError(
            'The AI response could not be understood. Please use manual entry.')

    parsed = _extract_json(text)
    subjects = parsed.get('subjects') if isinstance(parsed, dict) else None
    if not isinstance(subjects, list) or not subjects:
        raise MarksheetScanError(
            'The AI could not find any subjects in the marksheet. Please use manual entry.')

    cleaned = []
    for item in subjects:
        if not isinstance(item, dict):
            continue
        name = str(item.get('subject', '')).strip()
        if not name:
            continue

        def _num(v):
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        cleaned.append({
            'subject': name,
            'obtained': _num(item.get('obtained')),
            'total': _num(item.get('total')),
        })
    if not cleaned:
        raise MarksheetScanError(
            'The AI could not find any subjects in the marksheet. Please use manual entry.')

    board = parsed.get('board') if isinstance(parsed, dict) else None
    if board not in BOARDS:
        board = None
    return {'subjects': _combine_subjects(cleaned), 'board': board}
