from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from .models import University
from .password_strength import password_strength

User = get_user_model()


class RegisterForm(forms.Form):
    full_name = forms.CharField(
        max_length=150, label='Full Name',
        widget=forms.TextInput(attrs={'placeholder': 'Your full name', 'class': 'input'}),
    )
    phone = forms.CharField(
        max_length=20, required=False, label='Phone Number',
        widget=forms.TextInput(attrs={'placeholder': 'Phone number (optional)', 'class': 'input'}),
    )
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'placeholder': 'Email address', 'class': 'input', 'id': 'email'}),
    )
    password1 = forms.CharField(
        label='Password', widget=forms.PasswordInput(
            attrs={'placeholder': 'Password', 'class': 'input', 'id': 'id_password1'}),
    )
    password2 = forms.CharField(
        label='Password confirmation', widget=forms.PasswordInput(
            attrs={'placeholder': 'Confirm password', 'class': 'input'}),
    )

    def clean_full_name(self):
        name = self.cleaned_data['full_name'].strip()
        if len(name) < 2:
            raise forms.ValidationError('Please enter your full name.')
        return name

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if '@' not in email:
            raise forms.ValidationError('Email must contain @.')
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                'An account with this email already exists. Please log in.')
        return email

    def clean_password1(self):
        pw = self.cleaned_data.get('password1', '')
        level, _ = password_strength(pw)
        if level == 'weak':
            raise forms.ValidationError(
                'Password is weak - it must be at least Moderate. '
                'Use 8+ characters with upper/lowercase letters, a digit or a symbol.')
        return pw

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'Both passwords must match.')


class OTPForm(forms.Form):
    code = forms.CharField(
        max_length=6, min_length=6, label='Verification Code',
        widget=forms.TextInput(attrs={
            'placeholder': '6-digit code', 'class': 'input',
            'inputmode': 'numeric', 'maxlength': '6', 'autocomplete': 'one-time-code',
        }),
    )

    def clean_code(self):
        code = self.cleaned_data['code'].strip()
        if not code.isdigit():
            raise forms.ValidationError('The code must be exactly 6 digits.')
        return code


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'placeholder': 'Your registered email', 'class': 'input'}),
    )

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()


class ResetCodeForm(forms.Form):
    code = forms.CharField(
        max_length=6, min_length=6, label='Reset Code',
        widget=forms.TextInput(attrs={
            'placeholder': '6-digit code', 'class': 'input',
            'inputmode': 'numeric', 'maxlength': '6', 'autocomplete': 'one-time-code',
        }),
    )

    def clean_code(self):
        code = self.cleaned_data['code'].strip()
        if not code.isdigit():
            raise forms.ValidationError('The code must be exactly 6 digits.')
        return code


class SetNewPasswordForm(forms.Form):
    new_password1 = forms.CharField(
        label='New password', widget=forms.PasswordInput(
            attrs={'placeholder': 'New password', 'class': 'input'}),
    )
    new_password2 = forms.CharField(
        label='Confirm new password', widget=forms.PasswordInput(
            attrs={'placeholder': 'Confirm new password', 'class': 'input'}),
    )

    def clean_new_password1(self):
        pw = self.cleaned_data.get('new_password1', '')
        level, _ = password_strength(pw)
        if level == 'weak':
            raise forms.ValidationError(
                'Password is weak - it must be at least Moderate. '
                'Use 8+ characters with upper/lowercase letters, a digit or a symbol.')
        return pw

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('new_password1')
        p2 = cleaned.get('new_password2')
        if p1 and p2 and p1 != p2:
            self.add_error('new_password2', 'Both passwords must match.')


class LoginForm(AuthenticationForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Email'
        self.fields['username'].widget.attrs.update(
            {'placeholder': 'Email address', 'class': 'input'})
        self.fields['password'].widget.attrs.update(
            {'placeholder': 'Password', 'class': 'input'})
        self.error_messages['invalid_login'] = (
            'Incorrect email or password. Please try again.'
        )


class UniversityForm(forms.ModelForm):
    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        qs = University.objects.filter(name__iexact=name)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                'A university with this name already exists.')
        return name

    class Meta:
        model = University
        fields = ('name', 'city', 'programs', 'career_category', 'website')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input', 'placeholder': 'University name'}),
            'city': forms.TextInput(attrs={'class': 'input', 'placeholder': 'City'}),
            'programs': forms.Textarea(attrs={'class': 'input', 'rows': 2,
                'placeholder': 'Programs offered, comma separated'}),
            'career_category': forms.Select(attrs={'class': 'input'}),
            'website': forms.URLInput(attrs={'class': 'input', 'placeholder': 'https://... (optional)'}),
        }
