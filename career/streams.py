
MATRIC_STREAMS = {
    'science_bio': {
        'name': 'Natural Sciences (Science - Biology)',
        'compulsory': ['English', 'Urdu', 'Islamiat', 'Pak Studies'],
        'optional': ['Tarjuma-tul-Quran'],
        'elective': ['Biology', 'Physics', 'Chemistry', 'Mathematics'],
    },
    'matric_cs': {
        'name': 'Computer Science (Matric CS)',
        'compulsory': ['English', 'Urdu', 'Islamiat', 'Pak Studies'],
        'optional': ['Tarjuma-tul-Quran'],
        'elective': ['Computer Science', 'Physics', 'Chemistry', 'Mathematics'],
    },
    'health_science': {
        'name': 'Health Science',
        'compulsory': ['English', 'Urdu', 'Islamiat', 'Pak Studies'],
        'optional': ['Tarjuma-tul-Quran'],
        'elective': ['Biology', 'Physics', 'Chemistry', 'Health Science'],
    },
    'agriculture': {
        'name': 'Agriculture',
        'compulsory': ['English', 'Urdu', 'Islamiat', 'Pak Studies'],
        'optional': ['Tarjuma-tul-Quran'],
        'elective': ['Biology', 'Physics', 'Chemistry', 'Agricultural Science'],
    },
    'arts': {
        'name': 'Arts / Humanities',
        'compulsory': ['English', 'Urdu', 'Islamiat', 'Pak Studies'],
        'optional': ['Tarjuma-tul-Quran'],
        'elective': ['General Mathematics', 'General Science', 'Education', 'Civics'],
    },
    'fashion_design': {
        'name': 'Fashion Designing',
        'compulsory': ['English', 'Urdu', 'Islamiat', 'Pak Studies'],
        'optional': ['Tarjuma-tul-Quran'],
        'elective': ['Mathematics', 'General Science', 'Computer Science', 'Communication Skills', 'Fashion Designing'],
    },
    'commerce': {
        'name': 'Commerce',
        'compulsory': ['English', 'Urdu', 'Islamiat', 'Pak Studies'],
        'elective': ['Principles of Accounting', 'Business Studies', 'Economics'],
    },
}

"""Default total marks per subject (researched from Punjab/FBISE schemes).

Matric (combined 9th+10th): languages 150, Islamiat/Pak Studies/Quran 100,
science subjects 150. Inter (per part): English/Urdu 100, Islamiat/Pak Studies
50, electives 100. Totals are prefilled in the form and remain editable, since
different boards may vary.
"""

DEFAULT_TOTALS_MATRIC = {
    'English': 150, 'Urdu': 150, 'Islamiat': 100,
    'Pak Studies': 100, 'Tarjuma-tul-Quran': 100,
    'Mathematics': 150, 'Physics': 150, 'Chemistry': 150, 'Biology': 150,
    'Computer Science': 150, 'Health Science': 100, 'Agricultural Science': 100,
    'General Mathematics': 150, 'General Science': 150, 'Education': 150,
    'Civics': 150, 'Communication Skills': 100, 'Fashion Designing': 100,
    'Principles of Accounting': 100, 'Business Studies': 100, 'Economics': 100,
}

"""FA elective subjects in official board groups (Group-I/II/III).
Rule: exactly ONE subject must be chosen from EACH group (3 electives total).
Based on Punjab board college schemes (GCWG) and BIE Karachi humanities scheme."""
FA_ELECTIVE_GROUPS = {
    'Group-I': [
        'Advance Urdu', 'English Literature', 'Arabic', 'Persian', 'French',
        'Punjabi', 'Sindhi', 'Kashmiryat', 'History', 'Islamic History',
        'World History', 'History of Pakistan', 'Philosophy', 'Geography',
    ],
    'Group-II': [
        'Psychology', 'Sociology', 'Civics', 'Political Science', 'Education',
        'Journalism', 'Computer Science', 'Fine Arts', 'Home Economics', 'Music',
    ],
    'Group-III': [
        'Economics', 'Mathematics', 'Statistics',
        'Islamiyat Elective', 'Physical Education', 'Agriculture',
    ],
}

"""Flat list of all 30 FA electives."""
FA_ELECTIVES_ALL = [s for group in FA_ELECTIVE_GROUPS.values() for s in group]

"""FA rule: exactly one elective from each of the 3 groups."""
FA_GROUPS_COUNT = 3

DEFAULT_TOTALS_INTER = {
    'English': 100, 'Urdu': 100, 'Islamic Studies': 50, 'Pak Studies': 50,
    'Mathematics': 100, 'Physics': 100, 'Chemistry': 100, 'Biology': 100,
    'Computer Science': 100, 'Economics': 100, 'Statistics': 100,
    'Principles of Accounting': 100, 'Principles of Commerce': 100,
    'Business Mathematics': 100, 'Business Statistics': 100,
    'Principles of Economics': 100,
    'Psychology': 100, 'Sociology': 100, 'Education': 100, 'Civics': 100,
    'English Literature': 100, 'History': 100, 'Geography': 100,
    'Islamiyat Elective': 100,
    'Advance Urdu': 100, 'Arabic': 100, 'Persian': 100, 'French': 100,
    'Punjabi': 100, 'Sindhi': 100, 'Kashmiryat': 100,
    'Political Science': 100, 'Islamic History': 100, 'World History': 100,
    'History of Pakistan': 100, 'Philosophy': 100, 'Journalism': 100,
    'Fine Arts': 100, 'Home Economics': 100, 'Music': 100,
    'Physical Education': 100, 'Agriculture': 100,
}


INTER_STREAMS = {
    'pre_medical': {
        'name': 'FSc Pre-Medical',
        'compulsory': ['English', 'Urdu', 'Islamic Studies', 'Pak Studies'],
        'elective': ['Biology', 'Physics', 'Chemistry'],
    },
    'pre_engineering': {
        'name': 'FSc Pre-Engineering',
        'compulsory': ['English', 'Urdu', 'Islamic Studies', 'Pak Studies'],
        'elective': ['Mathematics', 'Physics', 'Chemistry'],
    },
    'ics_physics': {
        'name': 'ICS with Physics',
        'compulsory': ['English', 'Urdu', 'Islamic Studies', 'Pak Studies'],
        'elective': ['Computer Science', 'Mathematics', 'Physics'],
    },
    'ics_stats': {
        'name': 'ICS with Statistics',
        'compulsory': ['English', 'Urdu', 'Islamic Studies', 'Pak Studies'],
        'elective': ['Computer Science', 'Mathematics', 'Statistics'],
    },
    'ics_economics': {
        'name': 'ICS with Economics',
        'compulsory': ['English', 'Urdu', 'Islamic Studies', 'Pak Studies'],
        'elective': ['Computer Science', 'Mathematics', 'Economics'],
    },
    'icom': {
        'name': 'ICom (Commerce)',
        'compulsory': ['English', 'Urdu', 'Islamic Studies', 'Pak Studies'],
        'elective': ['Principles of Accounting', 'Principles of Commerce',
                     'Business Mathematics', 'Principles of Economics'],
    },
    'fa': {
        'name': 'FA (Arts)',
        'compulsory': ['English', 'Urdu', 'Islamic Studies', 'Pak Studies'],
        'elective': FA_ELECTIVES_ALL,
    },
    'general_science': {
        'name': 'General Science (Inter)',
        'compulsory': ['English', 'Urdu', 'Islamic Studies', 'Pak Studies'],
        'elective': ['Mathematics', 'Statistics', 'Economics'],
    },
}
