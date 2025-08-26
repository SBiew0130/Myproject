import pandas as pd
import random
from collections import defaultdict
import json
import sys
import os
from datetime import datetime, time
import django
from django.conf import settings

# Configure Django settings if not already configured
from django.conf import settings
if not settings.configured:
    import os, django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schedule_project.settings')
    django.setup()

# Import Django models
from .models import (
    TeacherSchedule, RoomSchedule, PreSchedule,
    ActivitySchedule, Timedata, ScheduleInfo
)

# New global variable to store processed time slots from database
TIME_SLOTS_FROM_DB = defaultdict(set)

def get_valid_days_and_hours(curriculum_type):
  """
  ฟังก์ชันสำหรับกำหนดวันและเวลาที่ใช้ได้ตามประเภทหลักสูตร โดยดึงข้อมูลจาก TIME_SLOTS_FROM_DB
  
  Args:
      curriculum_type (str): ประเภทหลักสูตร ("ภาคปกติ" หรือ "ภาคพิเศษ")
  
  Returns:
      tuple: (รายการวันที่ใช้ได้, None)
  """
  all_days_from_db = list(TIME_SLOTS_FROM_DB.keys())
  
  # Define day types locally within the function
  weekdays = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์"]
  weekends = ["เสาร์", "อาทิตย์"]

  if curriculum_type == "ภาคปกติ":
      valid_days = [d for d in all_days_from_db if d in weekdays]
      return valid_days, None
  elif curriculum_type == "ภาคพิเศษ":
      valid_days = [d for d in all_days_from_db if d in (weekdays + weekends)]
      return valid_days, None
  else:
      # Default: use regular curriculum days if type is unknown
      valid_days = [d for d in all_days_from_db if d in weekdays]
      return valid_days, None

def get_hours_for_day(day, curriculum_type):
  """
  ฟังก์ชันสำหรับกำหนดชั่วโมงที่ใช้ได้ในแต่ละวันตามประเภทหลักสูตร โดยดึงข้อมูลจาก TIME_SLOTS_FROM_DB
  
  Args:
      day (str): วันในสัปดาห์
      curriculum_type (str): ประเภทหลักสูตร
  
  Returns:
      list: รายการชั่วโมงที่ใช้ได้ในวันนั้น
  """
  # Get all hours available for this day from the database data
  hours_from_db = list(TIME_SLOTS_FROM_DB.get(day, set()))
  
  # Define day types locally within the function
  weekdays = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์"]
  weekends = ["เสาร์", "อาทิตย์"]

  if curriculum_type == "ภาคปกติ":
      # Filter hours from database by the regular curriculum range (8:00-19:00)
      return sorted([h for h in hours_from_db if h in range(8, 20)])
  elif curriculum_type == "ภาคพิเศษ":
      if day in weekdays:
          # Filter hours from database by the special weekday curriculum range (17:00-19:00)
          return sorted([h for h in hours_from_db if h in range(17, 20)])
      elif day in weekends:
          # Filter hours from database by the special weekend curriculum range (8:00-19:00)
          return sorted([h for h in hours_from_db if h in range(8, 20)])
      else:
          return [] # Day not valid for special curriculum
  else:
      # Default to regular curriculum hours if type is unknown
      return sorted([h for h in hours_from_db if h in range(8, 20)])

def get_blocked_times_from_activities(locked_activity_df):
  """
  ฟังก์ชันสำหรับดึงเวลาที่ถูกบล็อกจากกิจกรรมที่ล็อกไว้
  
  Args:
      locked_activity_df (DataFrame): ข้อมูลกิจกรรมที่ล็อกไว้
  
  Returns:
      set: เซ็ตของเวลาที่ถูกบล็อก ในรูปแบบ "วัน_ชั่วโมง"
  """
  blocked_times = set()
  
  if locked_activity_df is not None and not locked_activity_df.empty:
      for _, row in locked_activity_df.iterrows():
          day = row["day"]  # วัน
          start_time = int(row["start_time"])  # เวลาเริ่ม
          stop_time = int(row["stop_time"])  # เวลาสิ้นสุด
          
          # เพิ่มทุกชั่วโมงในช่วงเวลานั้นเข้าไปในเซ็ตของเวลาที่ถูกบล็อก
          for hour in range(start_time, stop_time):
              blocked_times.add(f"{day}_{hour}")
  
  return blocked_times

def get_blocked_times_from_locked_courses(locked_df):
  """
  ฟังก์ชันสำหรับดึงเวลาที่ถูกบล็อกจากรายวิชาที่ล็อกไว้
  
  Args:
      locked_df (DataFrame): ข้อมูลรายวิชาที่ล็อกไว้
  
  Returns:
      set: เซ็ตของเวลาที่ถูกบล็อก ในรูปแบบ "วัน_ชั่วโมง"
      
      NOTE: This function is kept for consistency but its output is no longer
      directly unioned into 'all_blocked_times' to allow other courses
      to be scheduled if resources (teacher/room) are different.
  """
  blocked_times = set()
  
  if locked_df is not None and not locked_df.empty:
      for _, row in locked_df.iterrows():
          day = row["day"]  # วัน
          start_time = int(row["start_time"])  # เวลาเริ่ม
          stop_time = int(row["stop_time"])  # เวลาสิ้นสุด
          
          # เพิ่มทุกชั่วโมงในช่วงเวลานั้นเข้าไปในเซ็ตของเวลาที่ถูกบล็อก
          for hour in range(start_time, stop_time):
              blocked_times.add(f"{day}_{hour}")
  
  return blocked_times

def find_available_rooms(times, room_usage, valid_room_names):
  """
  ฟังก์ชันสำหรับหาห้องที่ว่างในช่วงเวลาที่กำหนด
  
  Args:
      times (list): รายการเวลาที่ต้องการใช้ห้อง
      room_usage (set): เซ็ตของการใช้ห้องที่มีอยู่แล้ว ในรูปแบบ (ห้อง, เวลา)
      valid_room_names (list): รายการชื่อห้องที่ใช้ได้
  
  Returns:
      list: รายการห้องที่ว่างในช่วงเวลาที่กำหนด
  """
  available_rooms = []
  
  # ตรวจสอบแต่ละห้องว่าว่างในทุกช่วงเวลาที่ต้องการหรือไม่
  for room in valid_room_names:
      is_available = True
      for t in times:
          if "NO_VALID_TIME" in t:
              continue
          # ถ้าห้องถูกใช้ในเวลานั้นแล้ว ห้องนี้ไม่ว่าง
          if (room, t) in room_usage:
              is_available = False
              break
      
      if is_available:
          available_rooms.append(room)
  
  return available_rooms

def get_consecutive_times(hours_needed, blocked_times, room_usage, valid_room_names, curriculum_type="ภาคปกติ"):
  """
  ฟังก์ชันสำหรับหาช่วงเวลาที่ต่อเนื่องกันตามข้อจำกัดของประเภทหลักสูตร
  
  Args:
      hours_needed (int): จำนวนชั่วโมงที่ต้องการ
      blocked_times (set): เวลาที่ถูกบล็อก (จากกิจกรรมเท่านั้น)
      room_usage (set): การใช้ห้องที่มีอยู่แล้ว (รวมถึงจาก locked_courses)
      valid_room_names (list): รายการห้องที่ใช้ได้
      curriculum_type (str): ประเภทหลักสูตร
  
  Returns:
      dict: ผลลัพธ์ที่มี "times" (รายการเวลา) และ "available_rooms" (ห้องที่ว่าง)
  """
  max_attempts = 100  # จำนวนครั้งสูงสุดที่จะลองหา
  
  valid_days, _ = get_valid_days_and_hours(curriculum_type) # Get valid days based on curriculum
  
  # Try to find suitable time slots
  for _ in range(max_attempts):
      if not valid_days:
          continue # No valid days for this curriculum type

      day = random.choice(valid_days)  # Randomly select a day
      valid_hours = get_hours_for_day(day, curriculum_type)  # Get valid hours for that day and curriculum
      
      # Check if there are enough hours on that day
      if not valid_hours or len(valid_hours) < hours_needed:
          continue
          
      # Find starting hours that can accommodate consecutive slots
      # Ensure all hours in the consecutive block are actually in valid_hours
      start_hour_options = [h for h in valid_hours if all(x in valid_hours for x in range(h, h + hours_needed))]
      if not start_hour_options:
          continue

      start_hour = random.choice(start_hour_options)  # Randomly select a starting hour
      
      # Create a list of consecutive hours
      consecutive_hours = list(range(start_hour, start_hour + hours_needed))
      
      # Create candidate times in "day_hour" format
      candidate_times = [f"{day}_{h}" for h in consecutive_hours]
      
      # Check if these times are blocked by activities (global block)
      if any(t in blocked_times for t in candidate_times):
          continue

      # Find available rooms for these times, considering existing room_usage (including locked courses)
      available_rooms = find_available_rooms(candidate_times, room_usage, valid_room_names)
      if available_rooms:
          return {
              "times": candidate_times,
              "available_rooms": available_rooms
          }

  # If no suitable time is found after max_attempts, return NO_VALID_TIME
  return {
      "times": [f"NO_VALID_TIME_{i}" for i in range(hours_needed)],
      "available_rooms": []
  }
      
def get_valid_rooms(room_type, room_df):
  """
  ฟังก์ชันสำหรับหาห้องที่ใช้ได้สำหรับประเภทห้องที่กำหนด
  
  Args:
      room_type (str): ประเภทห้อง
      room_df (DataFrame): ข้อมูลห้อง
  
  Returns:
      list: รายการชื่อห้องที่ใช้ได้
  """
  if room_df is not None and not room_df.empty:
      if 'room_type' in room_df.columns:
          # หาห้องที่ตรงกับประเภทที่ต้องการ
          valid_rooms = room_df[room_df["room_type"] == room_type]["room_name"].tolist()
          
          # ถ้าไม่มีห้องประเภทนั้น ให้ใช้ห้องทั้งหมด
          if not valid_rooms:
              valid_rooms = room_df["room_name"].tolist()
      else:
          # ถ้าไม่มีคอลัมน์ room_type ให้ใช้ห้องทั้งหมด
          valid_rooms = room_df["room_name"].tolist()
  else:
      # ถ้าไม่มีข้อมูลห้อง ให้ใช้ห้องเริ่มต้น
      valid_rooms = ["Room_001", "Room_002", "Room_003"]
  
  return valid_rooms

def extract_locked_schedule(locked_df):
  """
  ฟังก์ชันสำหรับแยกตารางเรียนที่ล็อกไว้จากข้อมูลรายวิชาที่ล็อก
  
  Args:
      locked_df (DataFrame): ข้อมูลรายวิชาที่ล็อกไว้
  
  Returns:
      list: รายการคลาสที่ล็อกไว้
  """
  locked_list = []
  
  if locked_df is not None and not locked_df.empty:
      for _, row in locked_df.iterrows():
          day = row["day"]  # วัน
          start_time = int(row["start_time"])  # เวลาเริ่ม
          stop_time = int(row["stop_time"])  # เวลาสิ้นสุด
          room_name = row["room_name"]  # ชื่อห้อง
          curriculum_type = row.get("curriculum_type", "ภาคปกติ")  # ประเภทหลักสูตร
          
          current_hour_for_slots = start_time  # ชั่วโมงปัจจุบันสำหรับจัดสล็อต
          
          # ถ้ามีสล็อตทฤษฎี
          if row["theory_slot"] > 0:
              times_theory = [f"{day}_{h}" for h in range(current_hour_for_slots, current_hour_for_slots + row["theory_slot"])]
              locked_list.append({
                  "course": row["subject_code"] + "_" + str(row["section"]),
                  "subject_name": row["subject_name"],
                  "teacher": row["teacher_name"],
                  "type": "theory",
                  "room_type": row["room_type"],
                  "room": room_name,
                  "time": times_theory,
                  "curriculum_type": curriculum_type
              })
              current_hour_for_slots += row["theory_slot"]  # เลื่อนชั่วโมงไปตามจำนวนสล็อตทฤษฎี
          
          # ถ้ามีสล็อตปฏิบัติ
          if row["lab_slot"] > 0:
              times_lab = [f"{day}_{h}" for h in range(current_hour_for_slots, current_hour_for_slots + row["lab_slot"])]
              locked_list.append({
                  "course": row["subject_code"] + "_" + str(row["section"]) + "_lab",
                  "subject_name": row["subject_name"],
                  "teacher": row["teacher_name"],
                  "type": "lab",
                  "room_type": row["room_type"],
                  "room": room_name,
                  "time": times_lab,
                  "curriculum_type": curriculum_type
              })
  
  return locked_list

def extract_locked_activities(locked_activity_df):
  """
  ฟังก์ชันสำหรับแยกกิจกรรมที่ล็อกไว้
  
  Args:
      locked_activity_df (DataFrame): ข้อมูลกิจกรรมที่ล็อกไว้
  
  Returns:
      list: รายการกิจกรรมที่ล็อกไว้
  """
  activity_list = []
  
  if locked_activity_df is not None and not locked_activity_df.empty:
      for _, row in locked_activity_df.iterrows():
          day = row["day"]  # วัน
          start_time = int(row["start_time"])  # เวลาเริ่ม
          stop_time = int(row["stop_time"])  # เวลาสิ้นสุด
          
          # สร้างรายการเวลาสำหรับกิจกรรม
          times = [f"{day}_{h}" for h in range(start_time, stop_time)]
          
          activity_list.append({
              "course": row["activity_name"],
              "subject_name": row["activity_name"],
              "teacher": None,  # กิจกรรมไม่มีอาจารย์
              "type": "activity",
              "room_type": None,  # กิจกรรมไม่ระบุประเภทห้อง
              "room": None,  # กิจกรรมไม่ระบุห้อง
              "time": times,
              "curriculum_type": "ภาคปกติ"  # กิจกรรมใช้ประเภทปกติเป็นค่าเริ่มต้น
          })
  
  return activity_list

def run_genetic_algorithm_from_db():
  """
  ฟังก์ชันหลักสำหรับรัน Genetic Algorithm เพื่อสร้างตารางเรียน
  
  Returns:
      dict: ผลลัพธ์การสร้างตารางเรียน
  """
  global TIME_SLOTS_FROM_DB # Declare global to modify it

  try:
      def load_data():
          """Load data from database instead of CSV files"""
          
          # Load course data from TeacherSchedule model
          teacher_schedules = TeacherSchedule.objects.all()
          course_data = []
          for ts in teacher_schedules:
              course_data.append({
                  'subject_code': ts.subject_code_teacher,
                  'subject_name': ts.subject_name_teacher,
                  'teacher_name': ts.teacher_name_teacher,
                  'curriculum_type': ts.curriculum_type_teacher or 'ภาคปกติ',
                  'room_type': ts.room_type_teacher or '',
                  'section_count': 1,  # Default to 1 section per teacher
                  'theory_slot': ts.theory_slot_amount_teacher,
                  'lab_slot': ts.lab_slot_amount_teacher
              })
          course_df = pd.DataFrame(course_data)
          
          # Load room data from RoomSchedule model
          room_schedules = RoomSchedule.objects.all()
          room_data = []
          for rs in room_schedules:
              room_data.append({
                  'room_name': rs.room_name_room,
                  'room_type': rs.room_type_room or ''
              })
          room_df = pd.DataFrame(room_data)
          
          # Load locked courses from PreSchedule model
          pre_schedules = PreSchedule.objects.all()
          locked_data = []
          for ps in pre_schedules:
              # Convert time objects to hours
              start_hour = ps.start_time_pre.hour if ps.start_time_pre else 8
              stop_hour = ps.stop_time_pre.hour if ps.stop_time_pre else 9
              
              locked_data.append({
                  'subject_code': ps.subject_code_pre,
                  'subject_name': ps.subject_name_pre,
                  'teacher_name': ps.teacher_name_pre,
                  'curriculum_type': ps.curriculum_type_pre or 'ภาคปกติ',
                  'room_type': ps.room_type_pre or '',
                  'section': ps.section_pre or '1',
                  'theory_slot': ps.theory_slot_amount_pre,
                  'lab_slot': ps.lab_slot_amount_pre,
                  'day': ps.day_pre or '',
                  'start_time': start_hour,
                  'stop_time': stop_hour,
                  'room_name': ps.room_name_pre or ''
              })
          locked_df = pd.DataFrame(locked_data)
          
          # Load locked activities from ActivitySchedule model
          activity_schedules = ActivitySchedule.objects.all()
          activity_data = []
          for acts in activity_schedules:
              # Convert time objects to hours
              start_hour = acts.start_time_activities.hour if acts.start_time_activities else 8
              stop_hour = acts.stop_time_activities.hour if acts.stop_time_activities else 9
              
              activity_data.append({
                  'activity_name': acts.act_name_activities,
                  'day': acts.day_activities or '',
                  'start_time': start_hour,
                  'stop_time': stop_hour
              })
          locked_activity_df = pd.DataFrame(activity_data)
          
          # Load time slot data from Timedata model
          time_data_records = Timedata.objects.all()
          time_slot_data = []
          for td in time_data_records:
              # Convert string time to integer hours
              try:
                  start_hour = int(td.start_time) if td.start_time.isdigit() else int(td.start_time.split(':')[0])
                  stop_hour = int(td.stop_time) if td.stop_time.isdigit() else int(td.stop_time.split(':')[0])
              except (ValueError, AttributeError):
                  start_hour = 8  # Default start hour
                  stop_hour = 17  # Default stop hour
                  
              time_slot_data.append({
                  'day_of_week': td.day_of_week,
                  'start_time': start_hour,
                  'stop_time': stop_hour
              })
          time_slot_df = pd.DataFrame(time_slot_data)
          
          return course_df, room_df, locked_df, locked_activity_df, time_slot_df

      # Load all data from database
      course_df, room_df, locked_df, locked_activity_df, time_slot_df = load_data()

      # Process time_slot_df into the global TIME_SLOTS_FROM_DB dictionary
      for _, row in time_slot_df.iterrows():
          day = row["day_of_week"]
          start = int(row["start_time"])
          stop = int(row["stop_time"])
          for hour in range(start, stop):
              TIME_SLOTS_FROM_DB[day].add(hour)

      # Update the global variable reference
      global TIME_SLOTS_FROM_CSV
      TIME_SLOTS_FROM_CSV = TIME_SLOTS_FROM_DB

      courses = []  # รายการรายวิชาที่จะจัดตาราง

      # สร้างรายการรายวิชาจากข้อมูล
      if not course_df.empty:
          subject_section_counter = defaultdict(int)  # ตัวนับ section สำหรับแต่ละวิชา
          
          for _, row in course_df.iterrows():
              curriculum_type = row.get("curriculum_type", "ภาคปกติ")  # ประเภทหลักสูตร
              
              # สร้าง section ตามจำนวนที่กำหนด
              for sec in range(1, int(row["section_count"]) + 1):
                  subject_section_counter[row["subject_code"]] += 1
                  current_section = subject_section_counter[row["subject_code"]]
                  section_suffix = f"_sec{current_section}"
                  
                  # เพิ่มสล็อตทฤษฎีถ้ามี
                  if row["theory_slot"] > 0:
                      courses.append({
                          "name": row["subject_code"] + section_suffix,
                          "subject_name": row["subject_name"],
                          "teacher": row["teacher_name"],
                          "type": "theory",
                          "room_type": row["room_type"],
                          "hours": row["theory_slot"],
                          "curriculum_type": curriculum_type
                      })
                  
                  # เพิ่มสล็อตปฏิบัติถ้ามี
                  if row["lab_slot"] > 0:
                      courses.append({
                          "name": row["subject_code"] + section_suffix + "_lab",
                          "subject_name": row["subject_name"],
                          "teacher": row["teacher_name"],
                          "type": "lab",
                          "room_type": row["room_type"],
                          "hours": row["lab_slot"],
                          "curriculum_type": curriculum_type
                      })
      
      # แยกข้อมูลที่ล็อกไว้
      locked_classes = extract_locked_schedule(locked_df)  # คลาสที่ล็อกไว้
      locked_activities = extract_locked_activities(locked_activity_df)  # กิจกรรมที่ล็อกไว้
      all_locked_items = locked_classes + locked_activities  # รวมทุกอย่างที่ล็อกไว้
      locked_names = {c["course"] for c in locked_classes}  # ชื่อคลาสที่ล็อกไว้

      # all_blocked_times ควรมาจาก locked_activities เท่านั้น เพื่อบล็อกเวลาทั้งหมด
      all_blocked_times = get_blocked_times_from_activities(locked_activity_df)

      def create_individual():
          """
          ฟังก์ชันสำหรับสร้างตัวอย่างตารางเรียน (Individual) สำหรับ Genetic Algorithm
          
          Returns:
              list: รายการคลาสในตารางเรียน
          """
          # เริ่มต้นด้วยรายการที่ล็อกไว้
          individual = list(all_locked_items)
          used_times = set()  # เวลาที่ใช้แล้ว (สำหรับทรัพยากร: อาจารย์, ห้อง)
          room_usage = set()  # การใช้ห้องที่มีแล้ว (สำหรับห้อง)
          teacher_usage = set() # การใช้อาจารย์ที่มีแล้ว (สำหรับอาจารย์)
          
          # เพิ่มเวลาและห้องที่ใช้โดยรายการที่ล็อกไว้
          for item in individual:
              for t in item["time"]:
                  # Add to general used_times (for any resource)
                  used_times.add(t) 
                  if item["room"] and item["room"] != "NO_VALID_ROOM":
                      room_usage.add((item["room"], t))
                  if item["teacher"]:
                      teacher_usage.add((item["teacher"], t))
          
          # blocked_times_for_individual คือเวลาที่ถูกบล็อกโดยกิจกรรม + เวลาที่ถูกใช้โดยทรัพยากรที่ล็อกไว้
          # นี่คือการรวมกันของเวลาที่ห้ามใช้เด็ดขาด (จากกิจกรรม) และเวลาที่ทรัพยากรถูกใช้ไปแล้ว
          blocked_times_for_individual = all_blocked_times.union(used_times)
          
          # จัดตารางสำหรับรายวิชาที่ยังไม่ได้ล็อก
          for c in courses:
              if c["name"] in locked_names:
                  continue  # ข้ามรายวิชาที่ล็อกไว้แล้ว

              valid_room_names = get_valid_rooms(c["room_type"], room_df)  # หาห้องที่ใช้ได้
              curriculum_type = c.get("curriculum_type", "ภาคปกติ")  # ประเภทหลักสูตร
              
              # หาช่วงเวลาที่เหมาะสม
              # blocked_times ในที่นี้คือ all_blocked_times (จากกิจกรรม)
              # room_usage ในที่นี้คือการใช้ห้องที่เกิดขึ้นแล้ว (รวมถึงจาก locked_courses)
              result = get_consecutive_times(c["hours"], all_blocked_times, room_usage, valid_room_names, curriculum_type)
              times = result["times"]
              available_rooms = result["available_rooms"]
              
              # เลือกห้องแบบสุ่ม
              selected_room = random.choice(available_rooms) if available_rooms else "NO_VALID_ROOM"
              
              # อัปเดตเวลาและห้องที่ใช้
              for t in times:
                  if "NO_VALID_TIME" not in t:
                      # Add to general used_times (for any resource)
                      used_times.add(t) 
                      if selected_room != "NO_VALID_ROOM":
                          room_usage.add((selected_room, t))
                      if c["teacher"]:
                          teacher_usage.add((c["teacher"], t))
              
              # สร้างคลาส
              cls = {
                  "course": c["name"],
                  "subject_name": c.get("subject_name", c["name"]),
                  "teacher": c["teacher"],
                  "type": c["type"],
                  "room_type": c["room_type"],
                  "room": selected_room,
                  "time": times,
                  "curriculum_type": curriculum_type
              }

              individual.append(cls)
              
          return individual

      def fitness(individual):
          """
          ฟังก์ชันสำหรับคำนวณคะแนนความเหมาะสม (Fitness) ของตารางเรียน
          พร้อมการตรวจสอบข้อจำกัดของประเภทหลักสูตร
          
          Args:
              individual (list): ตารางเรียน
          
          Returns:
              int: คะแนนความเหมาะสม (ยิ่งสูงยิ่งดี)
          """
          score = 0
          used = {"teacher_time": set(), "room_time": set()}  # ติดตามการใช้อาจารย์และห้อง
          room_usage_count = {}  # การใช้ห้องแต่ละห้อง
          teacher_usage_count = {} # การใช้อาจารย์แต่ละคน

          # Prepare room usage counts
          if room_df is not None and not room_df.empty:
              room_usage_count = {room: 0 for room in room_df["room_name"]}

          for cls in individual:
              curriculum_type = cls.get("curriculum_type", "ภาคปกติ")
              
              for t in cls["time"]:
                  # ลงโทษถ้าไม่มีเวลาที่ใช้ได้
                  if "NO_VALID_TIME" in t:
                      score -= 200
                      continue

                  # ลงโทษถ้าใช้เวลาที่ถูกบล็อกโดยกิจกรรม (global block)
                  if t in all_blocked_times:
                      score -= 150

                  # ตรวจสอบว่าเวลานี้เหมาะสมกับประเภทหลักสูตรหรือไม่
                  day, hour_str = t.split("_")
                  hour = int(hour_str)
                  valid_hours = get_hours_for_day(day, curriculum_type)
                  
                  # ลงโทษถ้าใช้เวลาที่ไม่เหมาะสมกับประเภทหลักสูตร
                  if hour not in valid_hours:
                      score -= 50
                      continue

                  # ตรวจสอบความขัดแย้งของอาจารย์
                  if cls["teacher"]:
                      if (cls["teacher"], t) in used["teacher_time"]:
                          score -= 100  # ลงโทษถ้าอาจารย์สอนซ้ำในเวลาเดียวกัน
                      else:
                          used["teacher_time"].add((cls["teacher"], t))
                          score += 30  # ให้คะแนนถ้าไม่มีความขัดแย้ง
                          teacher_usage_count[cls["teacher"]] = teacher_usage_count.get(cls["teacher"], 0) + 1

                  # ตรวจสอบความขัดแย้งของห้อง
                  if cls["room"] and cls["room"] != "NO_VALID_ROOM":
                      if (cls["room"], t) in used["room_time"]:
                          score -= 100  # ลงโทษถ้าห้องถูกใช้ซ้ำในเวลาเดียวกัน
                      else:
                          used["room_time"].add((cls["room"], t))
                          score += 30  # ให้คะแนนถ้าไม่มีความขัดแย้ง
                          if cls["room"] in room_usage_count:
                              room_usage_count[cls["room"]] += 1

              # ให้คะแนนพิเศษสำหรับเวลาที่ต่อเนื่องกันในวันเดียวกัน
              valid_times = [t for t in cls["time"] if "NO_VALID_TIME" not in t]
              if valid_times:
                  times = sorted(valid_times, key=lambda x: int(x.split("_")[1]) if "_" in x and x.split("_")[1].isdigit() else 0)
                  days = set(t.split("_")[0] for t in times if "_" in t)
                  hours = [int(t.split("_")[1]) for t in times if "_" in t and t.split("_")[1].isdigit()]

                  # ถ้าเป็นวันเดียวกันและเวลาต่อเนื่องกัน ให้คะแนนพิเศษ
                  if len(days) == 1 and len(hours) > 1 and all(hours[i+1] == hours[i] + 1 for i in range(len(hours)-1)):
                        score += 40

          # ลงโทษถ้าการใช้ห้องไม่สมดุล
          if room_usage_count and any(room_usage_count.values()):
              max_usage = max(room_usage_count.values())
              min_usage = min(room_usage_count.values())
              room_balance_score = max_usage - min_usage
              score -= room_balance_score * 2
          
          # ลงโทษถ้าการใช้อาจารย์ไม่สมดุล (ถ้ามีอาจารย์)
          if teacher_usage_count and any(teacher_usage_count.values()):
              max_usage_teacher = max(teacher_usage_count.values())
              min_usage_teacher = min(teacher_usage_count.values())
              teacher_balance_score = max_usage_teacher - min_usage_teacher
              score -= teacher_balance_score * 1 # Penalty for teacher imbalance

          return score

      def crossover(p1, p2):
          """
          ฟังก์ชันสำหรับการผสมพันธุ์ (Crossover) ใน Genetic Algorithm
          
          Args:
              p1, p2 (list): ตารางเรียนพ่อแม่ 2 ตัว
          
          Returns:
              list: ตารางเรียนลูก
          """
          # คัดลอกรายการที่ล็อกไว้จาก p1
          locked_p1 = [cls.copy() for cls in p1 if cls["course"] in locked_names or cls["type"] == "activity"]

          # แยกรายการที่ไม่ได้ล็อกจากทั้งสองพ่อแม่
          unlocked_p1 = [cls.copy() for cls in p1 if cls["course"] not in locked_names and cls["type"] != "activity"]
          unlocked_p2 = [cls.copy() for cls in p2 if cls["course"] not in locked_names and cls["type"] != "activity"]

          # ผสมพันธุ์โดยการตัดและต่อ
          if len(unlocked_p1) > 1:
              point = random.randint(1, len(unlocked_p1)-1)  # จุดตัด
              child_unlocked = unlocked_p1[:point] + unlocked_p2[point:]  # ตัดและต่อ
          else:
              child_unlocked = unlocked_p1

          return locked_p1 + child_unlocked

      def mutate(individual, rate=0.2):
          """
          ฟังก์ชันสำหรับการกลายพันธุ์ (Mutation) ใน Genetic Algorithm
          
          Args:
              individual (list): ตารางเรียนที่จะกลายพันธุ์
              rate (float): อัตราการกลายพันธุ์
          
          Returns:
              list: ตารางเรียนที่กลายพันธุ์แล้ว
          """
          # แยกรายการที่ล็อกและไม่ล็อก
          locked_items = [cls.copy() for cls in individual if cls["course"] in locked_names or cls["type"] == "activity"]
          unlocked_items = [cls.copy() for cls in individual if cls["course"] not in locked_names and cls["type"] != "activity"]

          # ติดตามการใช้เวลาและห้อง
          used_times = set()
          room_usage = set()
          teacher_usage = set()

          # เพิ่มเวลาและห้องที่ใช้โดยรายการที่ล็อก
          for item in locked_items:
              for t in item["time"]:
                  used_times.add(t)
                  if item["room"] and item["room"] != "NO_VALID_ROOM":
                      room_usage.add((item["room"], t))
                  if item["teacher"]:
                      teacher_usage.add((item["teacher"], t))

          # blocked_times ใน mutate ควรเป็น all_blocked_times (จากกิจกรรม)
          # และ room_usage/teacher_usage จะถูกใช้เพื่อตรวจสอบความขัดแย้งของทรัพยากร
          
          # กลายพันธุ์รายการที่ไม่ล็อก
          for cls in unlocked_items:
              if random.random() < rate:  # ตรวจสอบอัตราการกลายพันธุ์
                  valid_room_names = get_valid_rooms(cls["room_type"], room_df)
                  curriculum_type = cls.get("curriculum_type", "ภาคปกติ")

                  # หาข้อมูลรายวิชาเดิม
                  original_course_info = next((c for c in courses if c["name"] == cls["course"]), None)
                  if original_course_info:
                      hours_needed = original_course_info["hours"]
                  else:
                      hours_needed = len(cls["time"])

                  # ลบเวลาและห้องเดิมออกจากการติดตาม (ก่อนจะหาเวลาใหม่)
                  for t in cls["time"]:
                      if "NO_VALID_TIME" not in t:
                          # used_times.discard(t) # No need to discard from global used_times here, it's re-calculated
                          if cls["room"] != "NO_VALID_ROOM":
                              room_usage.discard((cls["room"], t))
                          if cls["teacher"]:
                              teacher_usage.discard((cls["teacher"], t))

                  # หาเวลาและห้องใหม่
                  # ส่ง all_blocked_times (จากกิจกรรม) และ room_usage ปัจจุบันเข้าไป
                  result = get_consecutive_times(hours_needed, all_blocked_times, room_usage, valid_room_names, curriculum_type)
                  cls["time"] = result["times"]
                  available_rooms = result["available_rooms"]

                  cls["room"] = random.choice(available_rooms) if available_rooms else "NO_VALID_ROOM"

                  # เพิ่มเวลาและห้องใหม่เข้าไปในการติดตาม
                  for t in cls["time"]:
                      if "NO_VALID_TIME" not in t:
                          # used_times.add(t) # No need to add to global used_times here
                          if cls["room"] != "NO_VALID_ROOM":
                              room_usage.add((cls["room"], t))
                          if cls["teacher"]:
                              teacher_usage.add((cls["teacher"], t))

          return locked_items + unlocked_items

      def genetic_algorithm(pop_size, generations):
          """
          ฟังก์ชันหลักของ Genetic Algorithm
          
          Args:
              pop_size (int): ขนาดประชากร
              generations (int): จำนวนรุ่น
          
          Returns:
              list: ตารางเรียนที่ดีที่สุด
          """
          # สร้างประชากรเริ่มต้น
          population = [create_individual() for _ in range(pop_size)]
          
          best_fitness_overall = float('-inf')  # คะแนนดีที่สุดโดยรวม
          best_individual_overall = None  # ตารางเรียนดีที่สุดโดยรวม

          # วนลูปตามจำนวนรุ่น
          for gen in range(generations):
              # เรียงประชากรตามคะแนนความเหมาะสม
              population.sort(key=fitness, reverse=True)
              best = population[0]  # ตัวที่ดีที่สุดในรุ่นนี้
              best_fitness = fitness(best)
              print(f"Gen: {gen} | Fitness: {best_fitness}")
              # อัปเดตตัวดีที่สุดโดยรวม
              if best_fitness > best_fitness_overall:
                  best_fitness_overall = best_fitness
                  best_individual_overall = best.copy()

              # สร้างรุ่นถัดไป
              next_gen = population[:5]  # เก็บ 5 ตัวที่ดีที่สุด
              while len(next_gen) < pop_size:
                  # เลือกพ่อแม่จาก 10 ตัวแรก
                  p1, p2 = random.sample(population[:6], 2)
                  child = crossover(p1, p2)  # ผสมพันธุ์
                  next_gen.append(mutate(child))  # กลายพันธุ์
              population = next_gen
              
          return best_individual_overall if best_individual_overall else population[0]

      def save_schedule(schedule):
          """
          ฟังก์ชันสำหรับบันทึกตารางเรียนลงฐานข้อมูล
          
          Args:
              schedule (list): ตารางเรียน
          
          Returns:
              DataFrame: ข้อมูลตารางเรียนในรูปแบบ DataFrame
          """
          schedule_data = []

          ScheduleInfo.objects.all().delete()

          # แปลงข้อมูลตารางเรียนเป็นรูปแบบที่เหมาะสมสำหรับฐานข้อมูล
          for cls in schedule:
              for t in cls["time"]:
                  if "NO_VALID_TIME" not in t:
                      day, hour = t.split("_")
                      
                      schedule_info = ScheduleInfo.objects.create(
                          Course_Code=cls["course"],
                          Subject_Name=cls.get("subject_name", "N/A"),
                          Teacher=cls["teacher"] if cls["teacher"] else "N/A",
                          Room=cls["room"] if cls["room"] and cls["room"] != "NO_VALID_ROOM" else "N/A",
                          Room_Type=cls["room_type"] if cls["room_type"] else "N/A",
                          Type=cls["type"],
                          Curriculum_Type=cls.get("curriculum_type", "ภาคปกติ"),
                          Day=day,
                          Hour=int(hour),
                          Time_Slot=t
                      )
                      
                      schedule_data.append({
                          "Course_Code": cls["course"],
                          "Subject_Name": cls.get("subject_name", "N/A"),
                          "Teacher": cls["teacher"] if cls["teacher"] else "N/A",
                          "Room": cls["room"] if cls["room"] and cls["room"] != "NO_VALID_ROOM" else "N/A",
                          "Room_Type": cls["room_type"] if cls["room_type"] else "N/A",
                          "Type": cls["type"],
                          "Curriculum_Type": cls.get("curriculum_type", "ภาคปกติ"),
                          "Day": day,
                          "Hour": hour,
                          "Time_Slot": t
                      })
          
          # เรียงข้อมูลตามรหัสวิชา
          schedule_data.sort(key=lambda x: x["Course_Code"])
          
          schedule_df = pd.DataFrame(schedule_data)
          schedule_df.to_csv("schedule.csv", index=False, encoding='utf-8-sig')
          print("✅ บันทึกตารางสอนลงฐานข้อมูลและไฟล์ schedule.csv แล้ว")
          
          return schedule_df
      
      best_schedules = []

      for i in range(3):
          print(f"🔁 Round {i+1}/3")
          
          # เรียกใช้ Genetic Algorithm
          best = genetic_algorithm(pop_size=50, generations=100)
          
          # คำนวณ fitness จาก best schedule
          fitnessii = fitness(best)  
          
          # เก็บข้อมูล
          best_schedules.append({
              "round": i + 1,
              "best_schedule": best,
              "fitness": fitnessii
          })

      #เรียงลำดับจาก fitness มาก → น้อย
      best_schedules.sort(key=lambda x: x["fitness"], reverse=True)
      
      #ดึงตัวที่ดีที่สุด
      best_schedule = best_schedules[0]["best_schedule"]

      #ส่งไปยัง save_schedule
      final_schedule = save_schedule(best_schedule)
     
      # คืนผลลัพธ์
      return {
          "status": "success",
          "message": "ตารางสอนถูกสร้างสำเร็จและบันทึกลงฐานข้อมูลแล้ว",
          "file_path": "schedule.csv",
          "total_entries": len(final_schedule),
          "database_entries": len(final_schedule),
          "fitness_score": fitness(best_schedule)
      }

  except Exception as e:
      # คืนข้อผิดพลาดถ้ามี
      return {
          "status": "error",
          "message": f"เกิดข้อผิดพลาด: {str(e)}"
      }

# ฟังก์ชันหลักที่จะรันเมื่อไฟล์ถูกเรียกใช้โดยตรง
if __name__ == "__main__":
  try:
      result = run_genetic_algorithm_from_db()
      print(json.dumps(result, ensure_ascii=False))
  except Exception as e:
      print(json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False))
      sys.exit(1)
