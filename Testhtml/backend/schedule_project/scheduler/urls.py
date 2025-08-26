from django.urls import path
from . import views

urlpatterns = [
    # หน้าเว็บหลัก
    path('', views.home, name='home'),
    path('teacher/', views.teacher_page, name='teacher'),
    path('room/', views.room_page, name='room'),
    path('activities/', views.activities_page, name='activities'),
    path('student/', views.student_page, name='student'),
    path('pre/', views.pre_page, name='pre'),

    # APIs ที่มีอยู่แล้ว...
    path('api/test-program/', views.test_program_api, name='test_program_api'),
    path('api/schedule/generate/', views.generate_schedule_api, name='generate_schedule_api'),
    path('api/schedule/view/', views.view_schedule_api, name='view_schedule_api'),
    path('api/schedule/clear/', views.clear_schedule_api, name='clear_schedule_api'),
    path('api/schedule/download/', views.download_schedule, name='download_schedule'),
    path('api/schedule/delete-selected/', views.delete_selected_schedules_api, name='delete_selected_schedules_api'),

    # Teacher APIs
    path('api/teacher/', views.get_teachers, name='get_teachers'),
    path('api/teacher/add/', views.add_teacher, name='add_teacher'),
    path('api/teacher/bulk/', views.add_teacher_bulk, name='add_teacher_bulk'),
    path('api/teacher/update/<int:id>/', views.update_teacher, name='update_teacher'),
    path('api/teacher/delete/<int:id>/', views.delete_teacher, name='delete_teacher'),
    path('upload/teacher-csv/', views.upload_teacher_csv, name='upload_teacher_csv'),

    # Room APIs
    path('api/room/', views.get_rooms, name='get_rooms'),
    path('api/room/add/', views.add_room, name='add_room'),
    path('api/room/bulk/', views.add_room_bulk, name='add_room_bulk'),
    path('api/room/update/<int:id>/', views.update_room, name='update_room'),
    path('api/room/delete/<int:id>/', views.delete_room, name='delete_room'),
    path('upload/room-csv/', views.upload_room_csv, name='upload_room_csv'),

    # Student APIs
    path('api/student/', views.get_students, name='get_students'),
    path('api/student/add/', views.add_student, name='add_student'),
    path('api/student/bulk/', views.add_student_bulk, name='add_student_bulk'),
    path('api/student/update/<int:id>/', views.update_student, name='update_student'),
    path('api/student/delete/<int:id>/', views.delete_student, name='delete_student'),
    path('upload/student-csv/', views.upload_student_csv, name='upload_student_csv'),

    # Pre-Schedule APIs
    path('api/pre/', views.get_pre, name='get_pre'),
    path('api/pre/add/', views.add_pre, name='add_pre'),
    path('api/pre/update/<int:id>/', views.update_pre, name='update_pre'),
    path('api/pre/delete/<int:id>/', views.delete_pre, name='delete_pre'),
    path('upload/pre-csv/', views.upload_pre_csv, name='upload_pre_csv'),

    # Activities APIs
    path('api/activities/', views.get_activities, name='get_activities'),
    path('api/activities/add/', views.add_activities, name='add_activities'),
    path('api/activities/bulk/', views.add_activities_bulk, name='add_activities_bulk'),
    path('api/activities/update/<int:id>/', views.update_activities, name='update_activities'),
    path('api/activities/delete/<int:id>/', views.delete_activities, name='delete_activities'),
    path('upload/activities-csv/', views.upload_activities_csv, name='upload_activities_csv'),
]
