from django.urls import path
from . import views

urlpatterns = [
    # หน้าเว็บหลัก
    path('', views.home, name='home'),
    path('pre/', views.pre_page, name='pre'),
    path('teacher/', views.teacher_page, name='teacher'),
    path('activities/', views.activities_page, name='activities'),
    path('add/', views.add_info, name='add'),

    # APIs ที่มีอยู่แล้ว...
    path('api/test-program/', views.test_program_api, name='test_program_api'),
    path('api/schedule/generate/', views.generate_schedule_api, name='generate_schedule_api'),
    path('api/schedule/view/', views.view_schedule_api, name='view_schedule_api'),
    path('api/schedule/clear/', views.clear_schedule_api, name='clear_schedule_api'),
    path('api/schedule/download/', views.download_schedule, name='download_schedule'),
    path('api/schedule/delete-selected/', views.delete_selected_schedules_api, name='delete_selected_schedules_api'),
    
     # Pre-Schedule APIs
    path('api/pre/', views.get_pre, name='get_pre'),
    path('api/pre/add/', views.add_pre, name='add_pre'),
    path('api/pre/update/<int:id>/', views.update_pre, name='update_pre'),
    path('api/pre/delete/<int:id>/', views.delete_pre, name='delete_pre'),
    path('upload/pre-csv/', views.upload_pre_csv, name='upload_pre_csv'),

    # Teacher APIs
    path('api/teacher/', views.get_teachers, name='get_teachers'),
    path('api/teacher/add/', views.add_teacher, name='add_teacher'),
    path('api/teacher/bulk/', views.add_teacher_bulk, name='add_teacher_bulk'),
    path('api/teacher/update/<int:id>/', views.update_teacher, name='update_teacher'),
    path('api/teacher/delete/<int:id>/', views.delete_teacher, name='delete_teacher'),
    path('upload/teacher-csv/', views.upload_teacher_csv, name='upload_teacher_csv'),

    # Activities APIs
    path('api/activities/', views.get_activities, name='get_activities'),
    path('api/activities/add/', views.add_activities, name='add_activities'),
    path('api/activities/bulk/', views.add_activities_bulk, name='add_activities_bulk'),
    path('api/activities/update/<int:id>/', views.update_activities, name='update_activities'),
    path('api/activities/delete/<int:id>/', views.delete_activities, name='delete_activities'),
    path('upload/activities-csv/', views.upload_activities_csv, name='upload_activities_csv'),
]
