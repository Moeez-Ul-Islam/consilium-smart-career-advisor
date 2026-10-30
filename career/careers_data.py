
CAREERS = [
    {
        'key': 'cs',
        'name': 'Computer Science',
        'desc': 'The world of software development, AI, data science, and IT. '
                'If you enjoy logical problem-solving and technology, this field is the best fit for you.',
        'degrees': ['BS Computer Science', 'BS Software Engineering',
                   'BS Artificial Intelligence', 'BS Cyber Security',
                   'BS Data Science', 'BS Information Technology',
                   'BS Robotics & Intelligent Systems',
                   'BS Computer Games Development'],
        'riasec': {'I': 3, 'R': 2, 'C': 2, 'E': 1, 'A': 1, 'S': 0},
        'univ_category': 'cs',
    },
    {
        'key': 'medicine',
        'name': 'Medicine & Health',
        'desc': 'Become a doctor, dentist, or pharmacist. One of the most rewarding '
                'career paths for students strong in Biology.',
        'degrees': ['MBBS', 'BDS (Dentistry)', 'Pharm-D',
                   'DPT (Doctor of Physical Therapy)', 'BS Nursing',
                   'BS Medical Lab Technology'],
        'riasec': {'I': 3, 'S': 2, 'R': 1, 'C': 1, 'E': 0, 'A': 0},
        'univ_category': 'medicine',
    },
    {
        'key': 'engineering',
        'name': 'Engineering',
        'desc': 'Electrical, Mechanical, or Civil engineering. A practical, high-demand '
                'field for students good at Physics and Mathematics.',
        'degrees': ['BS Electrical Engineering', 'BS Mechanical Engineering',
                   'BS Civil Engineering', 'BS Mechatronics Engineering',
                   'BS Biomedical Engineering', 'BS Avionics Engineering'],
        'riasec': {'R': 3, 'I': 2, 'C': 1, 'E': 1, 'A': 0, 'S': 0},
        'univ_category': 'engineering',
    },
    {
        'key': 'business',
        'name': 'Business & Commerce',
        'desc': 'Business management, accounting, and finance. Ideal for those with '
                'leadership qualities and an interest in numbers.',
        'degrees': ['BBA', 'BS Accounting & Finance', 'ACCA / CA',
                   'BBIT (Business & IT)', 'BS Financial Technology'],
        'riasec': {'E': 3, 'C': 2, 'S': 1, 'I': 1, 'R': 0, 'A': 0},
        'univ_category': 'business',
    },
    {
        'key': 'arts',
        'name': 'Arts & Social Sciences',
        'desc': 'Psychology, media, education, or law. Meaningful career options '
                'for creative and social personalities.',
        'degrees': ['BS Psychology', 'BS Mass Communication', 'LLB (Law)',
                   'BS English', 'BS International Relations',
                   'BS Islamic Studies', 'BS Arabic', 'BS Urdu',
                   'BS History', 'BS Education'],
        'riasec': {'A': 3, 'S': 2, 'E': 1, 'I': 1, 'C': 0, 'R': 0},
        'univ_category': 'arts',
    },
]

TYPE_NAMES = {
    'R': 'Realistic (Practical / Doer)',
    'I': 'Investigative (Analytical / Thinker)',
    'A': 'Artistic (Creative / Creator)',
    'S': 'Social (Helpful / Helper)',
    'E': 'Enterprising (Leader / Persuader)',
    'C': 'Conventional (Organized / Organizer)',
}
