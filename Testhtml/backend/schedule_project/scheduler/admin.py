from django.contrib import admin
from .models import (
    TeacherSchedule, RoomSchedule, StudentGroup, 
    ActivitySchedule, PreSchedule, ScheduleInfo
)

@admin.register(TeacherSchedule)
class TeacherScheduleAdmin(admin.ModelAdmin):
    list_display = ['teacher_name_teacher', 'subject_code_teacher', 'subject_name_teacher']
    search_fields = ['teacher_name_teacher', 'subject_code_teacher']

@admin.register(RoomSchedule)
class RoomScheduleAdmin(admin.ModelAdmin):
    list_display = ['room_name_room', 'room_type_room']
    search_fields = ['room_name_room']

@admin.register(StudentGroup)
class StudentGroupAdmin(admin.ModelAdmin):
    list_display = ['student_group', 'subject_code_stu', 'curriculum_type_stu']
    search_fields = ['student_group', 'subject_code_stu']

@admin.register(ActivitySchedule)
class ActivityScheduleAdmin(admin.ModelAdmin):
    list_display = ['act_name_activities', 'day_activities', 'start_time_activities']
    search_fields = ['act_name_activities']

@admin.register(PreSchedule)
class PreScheduleAdmin(admin.ModelAdmin):
    list_display = ['subject_code_pre', 'teacher_name_pre', 'day_pre']
    search_fields = ['subject_code_pre', 'teacher_name_pre']

@admin.register(ScheduleInfo)
class ScheduleInfoAdmin(admin.ModelAdmin):
    list_display = ['Course_Code', 'Subject_Name', 'Teacher', 'Room', 'Day', 'Hour']
    list_filter = ['Day', 'Type']
    search_fields = ['Course_Code', 'Subject_Name', 'Teacher']
