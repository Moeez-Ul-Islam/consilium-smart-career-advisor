import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


OCCUPATION_CODES = {
    'cs': '15-1252.00',
    'medicine': '29-1229.00',
    'engineering': '17-2141.00',
    'business': '11-1021.00',
    'arts': '27-1011.00',
}

_BASE = 'https://api-v2.onetcenter.org'
_TIMEOUT = 5
_CACHE_TTL_OK = 60 * 60 * 24 * 7
_CACHE_TTL_FAIL = 60 * 60


def _headers():
    api_key = getattr(settings, 'ONET_API_KEY', '') or ''
    if not api_key:
        return None
    return {
        'X-API-Key': api_key,
        'User-Agent': 'python-OnetWebService/2.00 (bot)',
        'Accept': 'application/json',
    }


def _get(path):
    headers = _headers()
    if headers is None:
        return None
    try:
        resp = requests.get(f'{_BASE}/{path}', headers=headers, timeout=_TIMEOUT)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    try:
        return resp.json()
    except ValueError:
        return None


def _parse_occupation(code, data):
    if not isinstance(data, dict):
        return None

    occupation = data.get('occupation') if isinstance(data.get('occupation'), dict) else {}
    title = data.get('title') or occupation.get('title')
    description = data.get('description') or occupation.get('description')
    soc_code = data.get('code') or occupation.get('code') or code
    if not title and not description:
        return None
    return {
        'title': title,
        'soc_code': soc_code,
        'description': description,
    }


def _parse_interests(data):
    codes = []
    if not isinstance(data, dict):
        return codes
    items = data.get('element')
    if not isinstance(items, list):
        items = data.get('interests') or []
    for item in items:
        if not isinstance(item, dict):
            continue
        element = item.get('element') or {}
        name = item.get('name') or element.get('name')
        if name:
            codes.append(str(name))
    return codes[:6]


def enrich_career(career_key):
    code = OCCUPATION_CODES.get(career_key)
    if not code:
        return None

    cache_key = f'onet:career:{career_key}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached or None

    result = None
    try:
        parsed = _parse_occupation(code, _get(f'online/occupations/{code}'))
        if parsed:
            parsed['interests'] = _parse_interests(
                _get(f'online/occupations/{code}/details/interests'))
            result = parsed
    except Exception:
        logger.exception('O*NET enrichment failed unexpectedly')
        result = None


    cache.set(cache_key, result if result is not None else False,
              _CACHE_TTL_OK if result else _CACHE_TTL_FAIL)
    return result
