"""
URL configuration for feedbackas project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, register_converter
from django.contrib.auth import views as auth_views
from .converters import HashIdConverter

register_converter(HashIdConverter, 'hashid')
from django.contrib.auth import views as auth_views
from . import views
from users import views as user_views
from django.views.generic.base import RedirectView, TemplateView
from django.contrib.staticfiles.storage import staticfiles_storage
from django.contrib.sitemaps.views import sitemap
from .sitemaps import StaticViewSitemap

sitemaps = {
    'static': StaticViewSitemap,
}

urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
    path('favicon.ico', RedirectView.as_view(url=staticfiles_storage.url('images/fav.png'))),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('orbigrow-admin-panel/', admin.site.urls),
    path('', views.index, name='index'),
    path('apie-mus/', views.apie_mus, name='apie_mus'),
    path('saugumas/', views.security_page, name='saugumas'),
    path('privatumo-politika/', views.privacy_policy, name='privatumo_politika'),
    path('home/', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('no-company/', views.no_company, name='no_company'),
    path('logout/', views.logout_view, name='logout'),
    path('get_team_members/', views.get_team_members, name='get_team_members'),
    path('request_feedback/', views.request_feedback, name='request_feedback'),
    path('send_feedback/<hashid:user_id>/', views.send_feedback, name='send_feedback'),
    path('feedback/fill/<hashid:request_id>/', views.fill_feedback, name='fill_feedback'),
    path('team/', views.team_members_list, name='team_members_list'),
    path('tasks/dashboard/', views.my_tasks_list, name='my_tasks_list'),
    path('request/<hashid:request_id>/cancel/', views.cancel_feedback_request, name='cancel_feedback_request'),
    path('request/<hashid:request_id>/reject/', views.reject_feedback_request, name='reject_feedback_request'),
    path('request/<hashid:request_id>/edit/', views.edit_feedback_request, name='edit_feedback_request'),
    path('results/', views.results, name='results'),
    path('api/competency_trend/<str:competency_name>/', views.get_competency_trend, name='competency_trend'),
    path('team-statistics/', views.team_statistics, name='team_statistics'),
    path('team-statistics/member/<hashid:user_id>/', views.team_member_detail, name='team_member_detail'),
    path('generate_ai_feedback/', views.generate_ai_feedback, name='generate_ai_feedback'),
    path('check_ai_task_status/', views.check_ai_task_status, name='check_ai_task_status'),
    path('all_feedback/', views.all_feedback_list, name='all_feedback_list'),
    path('get_feedback_data/', views.get_feedback_data, name='get_feedback_data'),
    path('management/', views.company_management, name='company_management'),
    path('management/assign/', views.assign_to_department, name='assign_to_department'),
    path('management/department/<hashid:department_id>/edit/', views.company_edit_department, name='company_edit_department'),
    path('management/department/<hashid:department_id>/delete/', views.company_delete_department, name='company_delete_department'),
    path('superadmin/', views.superadmin_dashboard, name='superadmin_dashboard'),
    path('superadmin/statistics/', views.superadmin_statistics, name='superadmin_statistics'),
    path('superadmin/audit-logs/', views.superadmin_audit_logs, name='superadmin_audit_logs'),
    path('superadmin/audit-logs/export/', views.superadmin_export_audit_logs, name='superadmin_export_audit_logs'),
    path('superadmin/companies/', views.superadmin_companies_list, name='superadmin_companies_list'),
    path('superadmin/ai-analytics/', views.superadmin_ai_analytics, name='superadmin_ai_analytics'),
    path('superadmin/companies/create/', views.superadmin_create_company, name='superadmin_create_company'),
    path('superadmin/companies/create/template/', views.superadmin_download_employee_template, name='superadmin_download_employee_template'),
    path('superadmin/companies/<hashid:company_id>/toggle-status/', views.superadmin_toggle_company, name='superadmin_toggle_company'),
    path('superadmin/companies/<hashid:company_id>/delete/', views.superadmin_delete_company, name='superadmin_delete_company'),
    path('superadmin/companies/<hashid:company_id>/', views.superadmin_company_detail, name='superadmin_company_detail'),
    path('superadmin/companies/<hashid:company_id>/hierarchy/', views.superadmin_edit_hierarchy, name='superadmin_edit_hierarchy'),
    path('superadmin/companies/<hashid:company_id>/hierarchy/edit/<hashid:department_id>/', views.superadmin_edit_department, name='superadmin_edit_department'),
    path('superadmin/companies/<hashid:company_id>/employees/', views.superadmin_edit_employees, name='superadmin_edit_employees'),
    path('superadmin/companies/<hashid:company_id>/employees/add/', views.superadmin_add_employee, name='superadmin_add_employee'),
    path('superadmin/companies/<hashid:company_id>/employees/import/', views.superadmin_import_employees, name='superadmin_import_employees'),
    path('superadmin/companies/<hashid:company_id>/employees/remove/<hashid:user_id>/', views.superadmin_remove_employee, name='superadmin_remove_employee'),
    path('superadmin/companies/<hashid:company_id>/hierarchy/delete/<hashid:department_id>/', views.superadmin_delete_department, name='superadmin_delete_department'),
    path('superadmin/impersonate/<hashid:user_id>/', views.superadmin_impersonate_user, name='superadmin_impersonate_user'),
    path('superadmin/companies/<hashid:company_id>/toggle-admin/<hashid:user_id>/', views.superadmin_toggle_admin, name='superadmin_toggle_admin'),
    path('superadmin/companies/<hashid:company_id>/billing/', views.superadmin_company_billing, name='superadmin_company_billing'),
    path('superadmin/billing/', views.superadmin_billing_overview, name='superadmin_billing_overview'),
    path('stop-impersonation/', views.stop_impersonation, name='stop_impersonation'),
    path('profile/', user_views.profile, name='profile'),
    path('questionnaires/', views.questionnaires_list, name='questionnaires_list'),
    path('questionnaires/create/', views.create_questionnaire, name='create_questionnaire'),
    path('questionnaires/team/create/', views.create_team_questionnaire, name='create_team_questionnaire'),
    path('questionnaires/<hashid:questionnaire_id>/edit/', views.edit_questionnaire, name='edit_questionnaire'),
    path('questionnaires/delete/<hashid:questionnaire_id>/', views.delete_questionnaire, name='delete_questionnaire'),
    path('questionnaires/send/', views.send_questionnaire, name='send_questionnaire'),
    path('questionnaires/<hashid:questionnaire_id>/statistics/', views.questionnaire_statistics, name='questionnaire_statistics'),
    
    # Superusers management
    path('superadmin/features/', views.superadmin_features, name='superadmin_features'),
    path('superadmin/superusers/', views.superadmin_superusers_list, name='superadmin_superusers_list'),
    path('superadmin/superusers/create/', views.superadmin_create_superuser, name='superadmin_create_superuser'),
    path('superadmin/superusers/<hashid:user_id>/edit/', views.superadmin_edit_superuser, name='superadmin_edit_superuser'),
    path('superadmin/superusers/<hashid:user_id>/delete/', views.superadmin_delete_superuser, name='superadmin_delete_superuser'),
    path('superadmin/users/', views.superadmin_users_list, name='superadmin_users_list'),
    path('superadmin/users/<hashid:user_id>/delete/', views.superadmin_delete_user, name='superadmin_delete_user'),
    path('superadmin/descriptions/', views.superadmin_descriptions, name='superadmin_descriptions'),

    # Email templates
    path('superadmin/emails/new-survey/', views.superadmin_email_new_survey, name='superadmin_email_new_survey'),
    path('superadmin/emails/survey-request/', views.superadmin_email_survey_request, name='superadmin_email_survey_request'),
    path('superadmin/emails/feedback-received/', views.superadmin_email_feedback_received, name='superadmin_email_feedback_received'),

    # Django Allauth (Microsoft Entra ID)
    path('accounts/', include('allauth.urls')),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
