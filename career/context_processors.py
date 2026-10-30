

def nav_steps(request):
    steps = []
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {'nav_steps': steps}
    try:
        from .models import AcademicRecord, PsychResult
        matric_done = AcademicRecord.objects.filter(
            user=user, level='matric').exists()
        inter_done = AcademicRecord.objects.filter(
            user=user, level='inter').exists()
        test_done = PsychResult.objects.filter(user=user).exists()
    except Exception:

        return {'nav_steps': steps}

    def _state(done, unlocked):
        if done:
            return 'done'
        return 'current' if unlocked else 'locked'

    steps = [
        {'key': 'matric', 'label': 'Matric', 'url_name': 'matric_entry',
         'state': _state(matric_done, True)},
        {'key': 'inter', 'label': 'Inter', 'url_name': 'inter_entry',
         'state': _state(inter_done, matric_done or inter_done)},
        {'key': 'test', 'label': 'Test', 'url_name': 'psych_test',
         'state': _state(test_done, inter_done or test_done)},
        {'key': 'results', 'label': 'Results', 'url_name': 'results',
         'state': 'current' if test_done else 'locked'},
    ]
    return {'nav_steps': steps}
