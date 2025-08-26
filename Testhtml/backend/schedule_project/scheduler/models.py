from django.db import models
from datetime import time

class TeacherSchedule(models.Model):
    teacher_name_teacher = models.CharField(max_length=100)
    subject_code_teacher = models.CharField(max_length=20)
    subject_name_teacher = models.CharField(max_length=100)
    curriculum_type_teacher = models.CharField(max_length=50, blank=True, null=True)
    room_type_teacher = models.CharField(max_length=50, blank=True)
    section_teacher = models.CharField(max_length=10)
    theory_slot_amount_teacher = models.IntegerField(default=0)
    lab_slot_amount_teacher = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.teacher_name_teacher} - {self.subject_name_teacher}"

class RoomSchedule(models.Model):
    room_name_room = models.CharField(max_length=50)
    room_type_room = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.room_name_room

class PreSchedule(models.Model):
    teacher_name_pre = models.CharField(max_length=100)
    subject_code_pre = models.CharField(max_length=20)
    subject_name_pre = models.CharField(max_length=100)
    curriculum_type_pre = models.CharField(max_length=50, blank=True, null=True)
    room_type_pre = models.CharField(max_length=50, blank=True, default='')
    type_pre = models.CharField(max_length=20)
    hours_pre = models.IntegerField(default=0)
    day_pre = models.CharField(max_length=20, blank=True, default='')
    start_time_pre = models.TimeField()
    stop_time_pre = models.TimeField()
    room_name_pre = models.CharField(max_length=50, blank=True, default='')
    def __str__(self):
        return f"{self.subject_name_pre} - {self.day_pre}"

class ActivitySchedule(models.Model):
    act_name_activities = models.CharField(max_length=100)
    day_activities = models.CharField(max_length=20, blank=True, default='')
    start_time_activities = models.TimeField()
    stop_time_activities = models.TimeField()

    def __str__(self):
        return f"{self.act_name_activities} - {self.day_activities}"

class StudentGroup(models.Model):
    student_group = models.CharField(max_length=100)
    subject_code_stu = models.CharField(max_length=20)
    curriculum_type_stu = models.CharField(max_length=50, blank=True, default='')

    def __str__(self):
        return f"{self.student_group} - {self.subject_code_stu}"

class ScheduleInfo(models.Model):
    
    Course_Code     = models.CharField(max_length=50)
    Subject_Name  = models.CharField(max_length=100, blank=True, default='')
    Teacher = models.CharField(max_length=100, blank=True, default='')
    Room = models.CharField(max_length=50,  blank=True, default='')
    Room_Type = models.CharField(max_length=50,  blank=True, default='')
    Type = models.CharField(max_length=20,  blank=True, default='')
    Curriculum_Type = models.CharField(max_length=20,  blank=True, default='')
    Day = models.CharField(max_length=20,  blank=True, default='')
    Hour = models.IntegerField(default=0)
    Time_Slot = models.CharField(max_length=20,  blank=True, default='')

    def __str__(self):
        return f"{self.Course_Code} - {self.Day} {self.Hour:02d}:00"

    class Meta:
        ordering = ['Day', 'Hour', 'Course_Code']

class Timedata(models.Model):
    day_of_week = models.CharField(max_length=20)
    start_time = models.CharField(max_length=20)
    stop_time = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.day_of_week}"
