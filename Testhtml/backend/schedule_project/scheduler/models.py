from django.db import models

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

class Subject(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} {self.name}"


class Teacher(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class GroupType(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class StudentGroup(models.Model):
    name = models.CharField(max_length=100, unique=True)
    group_type = models.ForeignKey(
        GroupType, on_delete=models.PROTECT, related_name="student_groups"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


DAY_CHOICES = [
    ("Mon","จันทร์"), ("Tue","อังคาร"), ("Wed","พุธ"),
    ("Thu","พฤหัสบดี"), ("Fri","ศุกร์"), ("Sat","เสาร์"), ("Sun","อาทิตย์"),
]

class TimeSlot(models.Model):
    day_of_week = models.CharField(max_length=3, choices=DAY_CHOICES)
    start_time = models.TimeField()
    stop_time = models.TimeField()

    class Meta:
        unique_together = ("day_of_week", "start_time", "stop_time")
        ordering = ["day_of_week", "start_time"]

    def __str__(self):
        return f"{self.day_of_week} {self.start_time}-{self.stop_time}"


class GroupAllow(models.Model):
    group_type = models.ForeignKey(
        GroupType, on_delete=models.CASCADE, related_name="allowed_slots"
    )
    slot = models.ForeignKey(
        TimeSlot, on_delete=models.CASCADE, related_name="group_type_allows"
    )

    class Meta:
        unique_together = ("group_type", "slot")
        ordering = ["group_type__name", "slot__day_of_week", "slot__start_time"]

    def __str__(self):
        return f"{self.group_type} -> {self.slot}"


class RoomType(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Room(models.Model):
    name = models.CharField(max_length=50, unique=True)
    room_type = models.ForeignKey(
        RoomType, on_delete=models.PROTECT, related_name="rooms"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class WeekActivity(models.Model):
    name = models.CharField(max_length=100)
    slot = models.ForeignKey(
        TimeSlot, on_delete=models.CASCADE, related_name="activities"
    )

    class Meta:
        ordering = ["slot__day_of_week", "slot__start_time", "name"]

    def __str__(self):
        return f"{self.name} @ {self.slot}"
