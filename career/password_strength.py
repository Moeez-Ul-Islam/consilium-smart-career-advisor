

def password_strength(password):
    pw = password or ''
    score = 0
    if len(pw) >= 8:
        score += 1
    if len(pw) >= 12:
        score += 1
    if any(c.islower() for c in pw):
        score += 1
    if any(c.isupper() for c in pw):
        score += 1
    if any(c.isdigit() for c in pw):
        score += 1
    if any(not c.isalnum() for c in pw):
        score += 1
    if score <= 2:
        level = 'weak'
    elif score <= 4:
        level = 'moderate'
    else:
        level = 'strong'
    return level, score


def is_acceptable(password):
    level, _ = password_strength(password)
    return level in ('moderate', 'strong')
