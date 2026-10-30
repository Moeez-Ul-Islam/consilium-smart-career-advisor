from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register_view, name='register'),
    path('check-email/', views.check_email_view, name='check_email'),
    path('verify/', views.verify_otp_view, name='verify_otp'),
    path('resend/', views.resend_otp_view, name='resend_otp'),
    path('login/', views.login_view, name='login'),
    path('forgot/', views.forgot_password_view, name='forgot_password'),
    path('reset/', views.reset_password_view, name='reset_password'),
    path('logout/', LogoutView.as_view(next_page='home'), name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('matric/', views.matric_entry, name='matric_entry'),
    path('inter/', views.inter_entry, name='inter_entry'),
    path('scan/', views.scan_marksheet, name='scan_marksheet'),
    path('test/', views.psych_test, name='psych_test'),
    path('results/', views.results, name='results'),
    path('results/download/', views.results_pdf, name='results_pdf'),
    path('records/delete/<str:level>/', views.delete_record, name='delete_record'),
    path('universities/', views.universities_view, name='universities'),
    path('feedback/', views.feedback_view, name='feedback'),

    path('manage/', views.manage_universities, name='manage_universities'),
    path('manage/add/', views.university_add, name='university_add'),
    path('manage/<int:pk>/edit/', views.university_edit, name='university_edit'),
    path('manage/<int:pk>/delete/', views.university_delete, name='university_delete'),
]
