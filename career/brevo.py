import requests
from django.conf import settings

BREVO_URL = 'https://api.brevo.com/v3/smtp/email'


class EmailSendError(RuntimeError):
    pass


def send_otp_email(to_email, code, name=''):
    api_key = getattr(settings, 'BREVO_API_KEY', '') or ''
    sender_email = getattr(settings, 'BREVO_SENDER_EMAIL', '') or ''
    if not api_key or not sender_email:
        raise EmailSendError(
            'The email service is not configured. Please contact the admin.')

    payload = {
        'sender': {'name': 'Consilium', 'email': sender_email},
        'to': [{'email': to_email, 'name': name or to_email}],
        'subject': 'Consilium - your verification code',
        'htmlContent': (
            f'<p>Hello {name or "Student"},</p>'
            f'<p>Your verification code to register for '
            f'Consilium - Smart Career Advisor:</p>'
            f'<h2 style="letter-spacing:6px;">{code}</h2>'
            f'<p>This code will expire in <strong>10 minutes</strong>.</p>'
            f'<p>If you did not make this request, please ignore this email.</p>'
        ),
    }
    try:
        resp = requests.post(
            BREVO_URL,
            json=payload,
            headers={'api-key': api_key,
                     'Content-Type': 'application/json',
                     'Accept': 'application/json'},
            timeout=15,
        )
    except requests.RequestException:
        raise EmailSendError(
            'There was a problem sending the email. Please check your connection and try again.')
    if resp.status_code not in (200, 201):
        raise EmailSendError(
            'The code could not be sent via the email service. Please try again later.')
    return True


def send_password_reset_email(to_email, code, name=''):
    api_key = getattr(settings, 'BREVO_API_KEY', '') or ''
    sender_email = getattr(settings, 'BREVO_SENDER_EMAIL', '') or ''
    if not api_key or not sender_email:
        raise EmailSendError(
            'The email service is not configured. Please contact the admin.')

    payload = {
        'sender': {'name': 'Consilium', 'email': sender_email},
        'to': [{'email': to_email, 'name': name or to_email}],
        'subject': 'Consilium - password reset code',
        'htmlContent': (
            f'<p>Hello {name or "Student"},</p>'
            f'<p>Your password reset code for '
            f'Consilium - Smart Career Advisor:</p>'
            f'<h2 style="letter-spacing:6px;">{code}</h2>'
            f'<p>This code will expire in <strong>10 minutes</strong>.</p>'
            f'<p>If you did not request a password reset, please ignore this email.</p>'
        ),
    }
    try:
        resp = requests.post(
            BREVO_URL,
            json=payload,
            headers={'api-key': api_key,
                     'Content-Type': 'application/json',
                     'Accept': 'application/json'},
            timeout=15,
        )
    except requests.RequestException:
        raise EmailSendError(
            'There was a problem sending the email. Please check your connection and try again.')
    if resp.status_code not in (200, 201):
        raise EmailSendError(
            'The code could not be sent via the email service. Please try again later.')
    return True
