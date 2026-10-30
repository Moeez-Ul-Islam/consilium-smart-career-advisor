
BOARDS = {

    'fbise': {'name': 'FBISE (Federal Board)', 'passing_pct': 40},
    'bise_karachi': {'name': 'BISE Karachi', 'passing_pct': 40},
    'bise_hyderabad': {'name': 'BISE Hyderabad', 'passing_pct': 40},
    'bise_sukkur': {'name': 'BISE Sukkur', 'passing_pct': 40},
    'bise_larkana': {'name': 'BISE Larkana', 'passing_pct': 40},
    'bise_mirpurkhas': {'name': 'BISE Mirpurkhas', 'passing_pct': 40},
    'ajk_mirpur': {'name': 'AJK Board Mirpur', 'passing_pct': 40},
    'kiu': {'name': 'KIU Board Gilgit', 'passing_pct': 40},
    'aku_eb': {'name': 'Aga Khan Board', 'passing_pct': 40},
    'zueb': {'name': 'Ziauddin Board', 'passing_pct': 40},

    'bise_lahore': {'name': 'BISE Lahore', 'passing_pct': 33},
    'bise_gujranwala': {'name': 'BISE Gujranwala', 'passing_pct': 33},
    'bise_rawalpindi': {'name': 'BISE Rawalpindi', 'passing_pct': 33},
    'bise_faisalabad': {'name': 'BISE Faisalabad', 'passing_pct': 33},
    'bise_multan': {'name': 'BISE Multan', 'passing_pct': 33},
    'bise_bahawalpur': {'name': 'BISE Bahawalpur', 'passing_pct': 33},
    'bise_sargodha': {'name': 'BISE Sargodha', 'passing_pct': 33},
    'bise_dgkhan': {'name': 'BISE D.G. Khan', 'passing_pct': 33},
    'bise_sahiwal': {'name': 'BISE Sahiwal', 'passing_pct': 33},
    'bise_peshawar': {'name': 'BISE Peshawar', 'passing_pct': 33},
    'bise_mardan': {'name': 'BISE Mardan', 'passing_pct': 33},
    'bise_kohat': {'name': 'BISE Kohat', 'passing_pct': 33},
    'bise_bannu': {'name': 'BISE Bannu', 'passing_pct': 33},
    'bise_dikhan': {'name': 'BISE D.I. Khan', 'passing_pct': 33},
    'bise_abbottabad': {'name': 'BISE Abbottabad', 'passing_pct': 33},
    'bise_swat': {'name': 'BISE Swat', 'passing_pct': 33},
    'bise_malakand': {'name': 'BISE Malakand', 'passing_pct': 33},
    'bise_quetta': {'name': 'BISE Quetta', 'passing_pct': 33},
}

DEFAULT_PASSING_PCT = 33


def passing_pct_for(board_key):
    board = BOARDS.get(board_key or '')
    return board['passing_pct'] if board else DEFAULT_PASSING_PCT


def grade_for_percentage(pct, passing_pct):
    if pct is None or pct < passing_pct:
        return 'F'
    if pct >= 80:
        return 'A+'
    if pct >= 70:
        return 'A'
    if pct >= 60:
        return 'B'
    if pct >= 50:
        return 'C'
    return 'D'


def board_name(board_key):
    board = BOARDS.get(board_key or '')
    return board['name'] if board else ''


def board_choices():
    forty = [(k, v['name']) for k, v in BOARDS.items() if v['passing_pct'] == 40]
    thirtythree = [(k, v['name']) for k, v in BOARDS.items() if v['passing_pct'] == 33]
    return [('Passing marks 40%', forty), ('Passing marks 33%', thirtythree)]
