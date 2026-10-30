from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, University, AcademicRecord, PsychResult, EmailOTP


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'full_name', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('is_staff', 'is_active')
    search_fields = ('email', 'full_name')
    ordering = ('-date_joined',)
    fieldsets = (
        (None, {'fields': ('email', 'full_name', 'password')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser',
                                    'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {'fields': ('email', 'full_name', 'password1', 'password2',
                           'is_staff', 'is_active')}),
    )


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'career_category')
    list_filter = ('career_category', 'city')
    search_fields = ('name', 'city')


@admin.register(AcademicRecord)
class AcademicRecordAdmin(admin.ModelAdmin):
    list_display = ('user', 'level', 'stream', 'percentage', 'updated_at')
    list_filter = ('level', 'stream')


@admin.register(PsychResult)
class PsychResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'dominant', 'completed', 'updated_at')


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ('email', 'is_used', 'attempts', 'created_at', 'expires_at')
    list_filter = ('is_used',)
    search_fields = ('email',)
