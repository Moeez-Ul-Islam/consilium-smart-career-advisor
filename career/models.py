from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required.')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('full_name', extra_fields.get('full_name', 'Admin'))
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    username = None
    email = models.EmailField('Email', unique=True)
    full_name = models.CharField('Full Name', max_length=150)
    phone = models.CharField('Phone', max_length=20, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    objects = CustomUserManager()

    def __str__(self):
        return f'{self.full_name} <{self.email}>'


class EmailOTP(models.Model):
    email = models.EmailField(db_index=True)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'OTP for {self.email} (used={self.is_used})'

    def is_expired(self):
        return timezone.now() > self.expires_at

    @classmethod
    def latest_valid(cls, email):
        return cls.objects.filter(
            email__iexact=email, is_used=False
        ).order_by('-created_at').first()


class University(models.Model):
    CATEGORY_CHOICES = [
        ('cs', 'Computer Science'),
        ('medicine', 'Medicine'),
        ('engineering', 'Engineering'),
        ('business', 'Business & Commerce'),
        ('arts', 'Arts & Social Sciences'),
    ]
    name = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    programs = models.TextField(help_text='Programs offered, comma separated')
    career_category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    website = models.URLField(blank=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Universities'

    def __str__(self):
        return f'{self.name} ({self.city})'


class AcademicRecord(models.Model):
    LEVEL_CHOICES = [
        ('matric', 'Matric'),
        ('inter', 'Inter'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='academic_records')
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    stream = models.CharField(max_length=50)
    board = models.CharField(max_length=30, blank=True, default='',
                             help_text='Examination board key (see career/boards.py).')

    subjects_data = models.JSONField(default=dict)
    total_obtained = models.FloatField(default=0)
    total_possible = models.FloatField(default=0)
    percentage = models.FloatField(default=0)
    marksheet = models.ImageField(upload_to='marksheets/', blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'level')
        ordering = ['level']

    def __str__(self):
        return f'{self.user.email} - {self.level} ({self.percentage:.1f}%)'

    def recalc(self):
        obtained = sum(float(v.get('obtained', 0) or 0) for v in self.subjects_data.values())
        possible = sum(float(v.get('total', 0) or 0) for v in self.subjects_data.values())
        self.total_obtained = obtained
        self.total_possible = possible
        self.percentage = round((obtained / possible * 100) if possible > 0 else 0, 2)


class PsychResult(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='psych_result')

    answers = models.JSONField(default=dict)

    scores = models.JSONField(default=dict)
    dominant = models.CharField(max_length=1, default='')
    completed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.email} - Psych ({self.dominant})'


class Feedback(models.Model):
    CATEGORY_CHOICES = [
        ('registration', 'Registration / Login'),
        ('marks', 'Marks Entry'),
        ('test', 'Personality Test'),
        ('results', 'Results / Recommendations'),
        ('general', 'General'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name='feedbacks')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    rating = models.PositiveSmallIntegerField(default=5)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        who = self.user.email if self.user else 'Anonymous'
        return f'{who} - {self.category} ({self.rating}/5)'
