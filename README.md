# Consilium: Smart Career Advisor

A career guidance web app for Inter (Part 1 / Part 2) students. It recommends
careers, bachelor degrees, and Pakistani universities from a student's academic
marks combined with a 30-question personality assessment, instead of marks
alone.

## How it works

- Students enter Matric and Inter marks manually, or scan a marksheet
  (OCR extracts the subjects and board).
- A 30-question personality test measures interests and work preferences.
- A scoring engine combines academic results with personality fit and
  recommends 3 careers, plus ranked bachelor degrees and universities
  for each career.

## Tech stack

- Python, Django (backend)
- PostgreSQL (database)
- HTML, CSS, JavaScript (frontend)

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in .env (see below), then:
python manage.py migrate
python manage.py seed_universities
python manage.py runserver
```

Environment variables (see `.env.example`): Django secret key, PostgreSQL
connection, Gemini API key (marksheet OCR), Brevo API key (email OTP).
Never commit a real `.env` file; it is gitignored.

## Tests

```bash
python manage.py test
```
