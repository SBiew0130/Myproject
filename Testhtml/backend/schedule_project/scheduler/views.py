import csv
import json
import logging
import os
from datetime import datetime, time
from io import StringIO
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings

from django.db.models import Case, When, Value, IntegerField

from .models import (
    ActivitySchedule, PreSchedule, RoomSchedule,
    StudentGroup, TeacherSchedule, ScheduleInfo
)

logger = logging.getLogger(__name__)

def norm(s: str) -> str:
    return (s or "").strip()

def norm_code(s: str) -> str:
    return norm(s).upper()

def to_int(v, default=0) -> int:
    try:
        return int(str(v).strip())
    except Exception:
        return default

DAY_ORDER = Case(
    When(Day__in=['จันทร์', 'Mon'], then=Value(1)),
    When(Day__in=['อังคาร', 'Tue'], then=Value(2)),
    When(Day__in=['พุธ', 'Wed'], then=Value(3)),
    When(Day__in=['พฤหัสบดี', 'Thu'], then=Value(4)),
    When(Day__in=['ศุกร์', 'Fri'], then=Value(5)),
    When(Day__in=['เสาร์', 'Sat'], then=Value(6)),
    When(Day__in=['อาทิตย์', 'Sun'], then=Value(7)),
    default=Value(99), output_field=IntegerField()
)

# ========== หน้าเว็บ (Page Views) ==========

def home(request):
    """หน้าแรกของระบบ"""
    context = {
        'title': 'ระบบจัดการสอน',
        'total_teachers': TeacherSchedule.objects.values('teacher_name_teacher').distinct().count(),
        'total_subjects': TeacherSchedule.objects.values('subject_code_teacher').distinct().count(),
        'total_rooms': RoomSchedule.objects.count(),
        'total_activities': ActivitySchedule.objects.count(),
    }
    return render(request, 'index.html', context)

def teacher_page(request):
    """หน้าจัดการข้อมูลอาจารย์"""
    teachers = TeacherSchedule.objects.all()
    context = {
        'title': 'จัดการข้อมูลอาจารย์',
        'teachers': teachers,
    }
    return render(request, 'teacher.html', context)

def room_page(request):
    """หน้าจัดการห้องเรียน"""
    rooms = RoomSchedule.objects.all()
    context = {
        'title': 'จัดการห้องเรียน',
        'rooms': rooms,
    }
    return render(request, 'room.html', context)

def activities_page(request):
    """หน้าจัดการกิจกรรม"""
    activities = ActivitySchedule.objects.all()
    context = {
        'title': 'จัดการกิจกรรม',
        'activities': activities,
    }
    return render(request, 'activities.html', context)

def student_page(request):
    """หน้าจัดการกลุ่มนักศึกษา"""
    students = StudentGroup.objects.all()
    context = {
        'title': 'จัดการกลุ่มนักศึกษา',
        'students': students,
    }
    return render(request, 'student.html', context)

def pre_page(request):
    """หน้าจัดการตารางล่วงหน้า"""
    pre_schedules = PreSchedule.objects.all()
    context = {
        'title': 'จัดการตารางล่วงหน้า',
        'pre_schedules': pre_schedules,
    }
    return render(request, 'pre.html', context)

# Hard-coded slot mapping แทนการใช้ SlotIdSchedule
SLOT_TIME_MAPPING = {
    1: {'start': time(8, 0), 'stop': time(9, 0)},
    2: {'start': time(9, 0), 'stop': time(10, 0)},
    3: {'start': time(10, 0), 'stop': time(11, 0)},
    4: {'start': time(11, 0), 'stop': time(12, 0)},
    5: {'start': time(12, 0), 'stop': time(13, 0)},
    6: {'start': time(13, 0), 'stop': time(14, 0)},
    7: {'start': time(14, 0), 'stop': time(15, 0)},
    8: {'start': time(15, 0), 'stop': time(16, 0)},
    9: {'start': time(16, 0), 'stop': time(17, 0)},
    10: {'start': time(17, 0), 'stop': time(18, 0)},
    11: {'start': time(18, 0), 'stop': time(19, 0)},
    12: {'start': time(19, 0), 'stop': time(20, 0)},
}

# ========== Generate Schedule API ==========

@csrf_exempt
@require_http_methods(["POST"])
def generate_schedule_api(request):
    """API สำหรับเรียกใช้ genetic algorithm โดยใช้ main function"""
    try:
        from .main import run_genetic_algorithm_from_db
        
        # เรียกใช้ genetic algorithm จาก main.py
        result = run_genetic_algorithm_from_db()
        
        # ตรวจสอบผลลัพธ์
        if result.get('status') == 'success':
            try:
                # สร้างไฟล์ CSV และบันทึกลงเซิร์ฟเวอร์
                csv_result = create_schedule_csv_file()
                if csv_result.get('status') == 'success':
                    result['csv_file'] = csv_result['file_path']
                    result['message'] += f" และสร้างไฟล์ CSV: {csv_result['file_path']}"
                else:
                    result['message'] += " (แต่ไม่สามารถสร้างไฟล์ CSV ได้)"
            except Exception as csv_error:
                logger.error(f"Error creating CSV file: {csv_error}")
                result['message'] += " (แต่เกิดข้อผิดพลาดในการสร้างไฟล์ CSV)"
            
            return JsonResponse(result, json_dumps_params={'ensure_ascii': False})
        else:
            return JsonResponse(result, status=400, json_dumps_params={'ensure_ascii': False})
            
    except ImportError as e:
        logger.error(f"Import error: {e}")
        return JsonResponse({
            'status': 'error',
            'message': 'ไม่สามารถโหลดโมดูล main ได้ กรุณาตรวจสอบไฟล์ main.py'
        }, status=500, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Unexpected error in generate_schedule_api: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'เกิดข้อผิดพลาดในการสร้างตารางสอน: {str(e)}'
        }, status=500, json_dumps_params={'ensure_ascii': False})

def create_schedule_csv_file():
    """สร้างไฟล์ CSV จากตารางสอนในฐานข้อมูลและบันทึกลงเซิร์ฟเวอร์"""
    try:
        
        schedules = ScheduleInfo.objects.order_by('id')
        
        if not schedules.exists():
            return {
                'status': 'error',
                'message': 'ไม่พบตารางสอนในระบบ'
            }
        
        # สร้างชื่อไฟล์ที่มี timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"schedule_{timestamp}.csv"
        
        # สร้างโฟลเดอร์ media/schedules หากยังไม่มี
        media_root = getattr(settings, 'MEDIA_ROOT', 'media')
        schedule_dir = os.path.join(media_root, 'schedules')
        os.makedirs(schedule_dir, exist_ok=True)
        
        # เส้นทางไฟล์เต็ม
        file_path = os.path.join(schedule_dir, filename)
        
        # เขียนไฟล์ CSV
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            
            # เขียน header
            writer.writerow([
                'รหัสวิชา', 'ชื่อวิชา', 'อาจารย์', 'ห้อง', 
                'ประเภท', 'วัน', 'ชั่วโมง'
            ])
            
            # เขียนข้อมูล
            for schedule in schedules:
                writer.writerow([
                    schedule.Course_Code,
                    schedule.Subject_Name,
                    schedule.Teacher,
                    schedule.Room,
                    schedule.Type,
                    schedule.Day,
                    schedule.Hour,
                ])
        
        return {
            'status': 'success',
            'message': f'สร้างไฟล์ CSV สำเร็จ: {filename}',
            'file_path': filename,
            'full_path': file_path,
            'total_records': schedules.count()
        }
        
    except Exception as e:
        logger.error(f"Error creating CSV file: {e}")
        return {
            'status': 'error',
            'message': f'เกิดข้อผิดพลาดในการสร้างไฟล์ CSV: {str(e)}'
        }

# ========== Test Program API ==========

@csrf_exempt
@require_http_methods(["POST"])
def test_program_api(request):
    """API สำหรับทดสอบโปรแกรม"""
    try:
        # ทดสอบการเชื่อมต่อฐานข้อมูล
        teacher_count = TeacherSchedule.objects.count()
        room_count = RoomSchedule.objects.count()
        
        return JsonResponse({
            'status': 'success',
            'message': 'ระบบทำงานปกติ',
            'data': {
                'teachers': teacher_count,
                'rooms': room_count,
                'timestamp': datetime.now().isoformat()
            }
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Test program error: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["GET"])
def view_schedule_api(request):
    """API ดูตารางสอน"""
    try:
        # order: id | day | hour | course
        # dir: asc | desc
        order = (request.GET.get('order') or 'id').lower().strip()
        direction = (request.GET.get('dir') or 'asc').lower().strip()

        qs = ScheduleInfo.objects.all()

        def apply_dir(fields):
            return [f if direction == 'asc' else f'-{f}' for f in fields]

        if order == 'day':
            qs = qs.annotate(day_order=DAY_ORDER) \
                   .order_by(*apply_dir(['day_order', 'Hour', 'Course_Code', 'id']))
        elif order == 'hour':
            qs = qs.annotate(day_order=DAY_ORDER) \
                   .order_by(*apply_dir(['day_order', 'Hour', 'id']))
        elif order == 'course':
            qs = qs.order_by(*apply_dir(['Course_Code', 'id']))
        else:  # 'id' หรือค่าอื่น ๆ -> fallback เป็น id
            qs = qs.order_by(*apply_dir(['id']))

        schedules = [{
            'id': s.id,
            'Course_Code': s.Course_Code,
            'Subject_Name': s.Subject_Name,
            'Teacher': s.Teacher,
            'Room': s.Room,
            'Room_Type': s.Room_Type,
            'Type': s.Type,
            'Day': s.Day,
            'Hour': s.Hour,   # << ใช้ Hour
            # ไม่ส่ง Time_Slot
        } for s in qs]

        return JsonResponse({
            'status': 'success',
            'total_entries': len(schedules),
            'schedules': schedules
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        logger.error(f"Error getting schedule from database: {e}")
        return JsonResponse(
            {'status': 'error', 'message': str(e)},
            status=500, json_dumps_params={'ensure_ascii': False}
        )

# ========== Clear Schedule API ==========

@csrf_exempt
@require_http_methods(["POST"])
def clear_schedule_api(request):
    """API สำหรับลบตารางสอนทั้งหมดในฐานข้อมูล"""
    try:
        deleted_count = ScheduleInfo.objects.count()
        ScheduleInfo.objects.all().delete()
        
        return JsonResponse({
            'status': 'success',
            'message': f'ลบตารางสอนทั้งหมดสำเร็จ ({deleted_count} รายการ)',
            'deleted_count': deleted_count
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error clearing schedule: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'เกิดข้อผิดพลาดในการลบตารางสอน: {str(e)}'
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["POST"])
def delete_selected_schedules_api(request):
    """API สำหรับลบตารางสอนที่เลือกในฐานข้อมูล"""
    try:

        data = json.loads(request.body)
        schedule_ids = data.get('schedule_ids', [])
        
        if not schedule_ids:
            return JsonResponse({
                'status': 'error',
                'message': 'ไม่พบรายการที่ต้องการลบ'
            }, status=400, json_dumps_params={'ensure_ascii': False})
        
        # Convert string IDs to integers
        try:
            schedule_ids = [int(id) for id in schedule_ids]
        except ValueError:
            return JsonResponse({
                'status': 'error',
                'message': 'รูปแบบ ID ไม่ถูกต้อง'
            }, status=400, json_dumps_params={'ensure_ascii': False})
        
        # Delete selected schedules
        deleted_count, _ = ScheduleInfo.objects.filter(id__in=schedule_ids).delete()
        
        return JsonResponse({
            'status': 'success',
            'message': f'ลบรายการที่เลือกสำเร็จ ({deleted_count} รายการ)',
            'deleted_count': deleted_count
        }, json_dumps_params={'ensure_ascii': False})
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'รูปแบบข้อมูลไม่ถูกต้อง'
        }, status=400, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error deleting selected schedules: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'เกิดข้อผิดพลาดในการลบรายการที่เลือก: {str(e)}'
        }, status=500, json_dumps_params={'ensure_ascii': False})

# ========== TEACHER APIs ==========

@csrf_exempt
def get_teachers(request):
    """API สำหรับดึงข้อมูลอาจารย์ทั้งหมด"""
    try:
        teachers = TeacherSchedule.objects.all()
        teachers_data = []
        
        for teacher in teachers:
            teachers_data.append({
                'id': teacher.id,
                'teacher_name_teacher': teacher.teacher_name_teacher,
                'subject_code_teacher': teacher.subject_code_teacher,
                'subject_name_teacher': teacher.subject_name_teacher,
                'curriculum_type_teacher': teacher.curriculum_type_teacher,
                'room_type_teacher': teacher.room_type_teacher,
                'section_teacher': teacher.section_teacher,
                'theory_slot_amount_teacher': teacher.theory_slot_amount_teacher,
                'lab_slot_amount_teacher': teacher.lab_slot_amount_teacher,
            })
        
        return JsonResponse({
            'status': 'success',
            'teachers': teachers_data
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error getting teachers: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["POST"])
def add_teacher(request):
    """API สำหรับเพิ่มอาจารย์"""
    try:
        data = json.loads(request.body)
        
        teacher = TeacherSchedule.objects.create(
            teacher_name_teacher=data.get('teacher_name_teacher'),
            subject_code_teacher=data.get('subject_code_teacher'),
            subject_name_teacher=data.get('subject_name_teacher'),
            curriculum_type_teacher=data.get('curriculum_type_teacher', ''),
            room_type_teacher=data.get('room_type_teacher', ''),
            section_teacher=data.get('section_teacher'),
            theory_slot_amount_teacher=data.get('theory_slot_amount_teacher', 0),
            lab_slot_amount_teacher=data.get('lab_slot_amount_teacher', 0),
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'เพิ่มข้อมูลอาจารย์สำเร็จ',
            'teacher_id': teacher.id
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error adding teacher: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["POST"])
def add_teacher_bulk(request):
    """API สำหรับเพิ่มอาจารย์หลายคนพร้อมกัน"""
    try:
        data = json.loads(request.body)
        teachers_data = data.get('teachers', [])
        
        created_teachers = []
        for teacher_data in teachers_data:
            teacher = TeacherSchedule.objects.create(
                teacher_name_teacher=teacher_data.get('teacher_name_teacher'),
                subject_code_teacher=teacher_data.get('subject_code_teacher'),
                subject_name_teacher=teacher_data.get('subject_name_teacher'),
                curriculum_type_teacher=teacher_data.get('curriculum_type_teacher', ''),
                room_type_teacher=teacher_data.get('room_type_teacher', ''),
                section_teacher=teacher_data.get('section_teacher'),
                theory_slot_amount_teacher=teacher_data.get('theory_slot_amount_teacher', 0),
                lab_slot_amount_teacher=teacher_data.get('lab_slot_amount_teacher', 0),
            )
            created_teachers.append(teacher.id)
        
        return JsonResponse({
            'status': 'success',
            'message': f'เพิ่มข้อมูลอาจารย์ {len(created_teachers)} คนสำเร็จ',
            'created_ids': created_teachers
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error adding teachers bulk: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["PUT"])
def update_teacher(request, id):
    """API สำหรับแก้ไขข้อมูลอาจารย์"""
    try:
        teacher = TeacherSchedule.objects.get(id=id)
        data = json.loads(request.body)
        
        teacher.teacher_name_teacher = data.get('teacher_name_teacher', teacher.teacher_name_teacher)
        teacher.subject_code_teacher = data.get('subject_code_teacher', teacher.subject_code_teacher)
        teacher.subject_name_teacher = data.get('subject_name_teacher', teacher.subject_name_teacher)
        teacher.curriculum_type_teacher = data.get('curriculum_type_teacher', teacher.curriculum_type_teacher)
        teacher.room_type_teacher = data.get('room_type_teacher', teacher.room_type_teacher)
        teacher.section_teacher = data.get('section_teacher', teacher.section_teacher)
        teacher.theory_slot_amount_teacher = data.get('theory_slot_amount_teacher', teacher.theory_slot_amount_teacher)
        teacher.lab_slot_amount_teacher = data.get('lab_slot_amount_teacher', teacher.lab_slot_amount_teacher)
        
        teacher.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'แก้ไขข้อมูลอาจารย์สำเร็จ'
        }, json_dumps_params={'ensure_ascii': False})
    except TeacherSchedule.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'ไม่พบข้อมูลอาจารย์'
        }, status=404, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error updating teacher: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["DELETE"])
def delete_teacher(request, id):
    """API สำหรับลบข้อมูลอาจารย์"""
    try:
        teacher = TeacherSchedule.objects.get(id=id)
        teacher.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': 'ลบข้อมูลอาจารย์สำเร็จ'
        }, json_dumps_params={'ensure_ascii': False})
    except TeacherSchedule.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'ไม่พบข้อมูลอาจารย์'
        }, status=404, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error deleting teacher: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["POST"])
def upload_teacher_csv(request):
    """API สำหรับอัปโหลดไฟล์ CSV ข้อมูลอาจารย์"""
    try:
        if 'file' not in request.FILES:
            return JsonResponse({
                'status': 'error',
                'message': 'ไม่พบไฟล์ที่อัปโหลด'
            }, status=400, json_dumps_params={'ensure_ascii': False})
        
        csv_file = request.FILES['file']
        
        if not csv_file.name.endswith('.csv'):
            return JsonResponse({
                'status': 'error',
                'message': 'กรุณาอัปโหลดไฟล์ CSV เท่านั้น'
            }, status=400, json_dumps_params={'ensure_ascii': False})
        
        # อ่านไฟล์ CSV พร้อมจัดการ encoding
        try:
            decoded_file = csv_file.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            for enc in ('utf-8', 'cp874', 'tis-620', 'cp1252'):
                try:
                    csv_file.seek(0)
                    decoded_file = csv_file.read().decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
        
        csv_data = StringIO(decoded_file)
        reader = csv.DictReader(csv_data)
        
        created_count = 0
        errors = []
        
        for row_num, row in enumerate(reader, start=2):
            try:
                TeacherSchedule.objects.create(
                    teacher_name_teacher=norm(row.get('teacher_name_teacher', '')),
                    subject_code_teacher=norm_code(row.get('subject_code_teacher', '')),
                    subject_name_teacher=norm(row.get('subject_name_teacher', '')),
                    curriculum_type_teacher=norm(row.get('curriculum_type_teacher', '')),
                    room_type_teacher=norm(row.get('room_type_teacher', '')),
                    section_teacher=norm(row.get('section_teacher', '')),
                    theory_slot_amount_teacher=to_int(row.get('theory_slot_amount_teacher', 0)),
                    lab_slot_amount_teacher=to_int(row.get('lab_slot_amount_teacher', 0)),
                )
                created_count += 1
            except Exception as e:
                errors.append(f'แถว {row_num}: {str(e)}')
        
        if errors:
            return JsonResponse({
                'status': 'partial_success',
                'message': f'อัปโหลดสำเร็จ {created_count} รายการ แต่มีข้อผิดพลาด {len(errors)} รายการ',
                'created_count': created_count,
                'errors': errors[:10]  # แสดงแค่ 10 ข้อผิดพลาดแรก
            }, json_dumps_params={'ensure_ascii': False})
        
        return JsonResponse({
            'status': 'success',
            'message': f'อัปโหลดข้อมูลอาจารย์สำเร็จ {created_count} รายการ',
            'created_count': created_count
        }, json_dumps_params={'ensure_ascii': False})
        
    except Exception as e:
        logger.error(f"Error uploading teacher CSV: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'เกิดข้อผิดพลาดในการอัปโหลด: {str(e)}'
        }, status=500, json_dumps_params={'ensure_ascii': False})

# ========== ROOM APIs ==========

@csrf_exempt
def get_rooms(request):
    """API สำหรับดึงข้อมูลห้องเรียนทั้งหมด"""
    try:
        rooms = RoomSchedule.objects.all()
        rooms_data = []
        
        for room in rooms:
            rooms_data.append({
                'id': room.id,
                'room_name_room': room.room_name_room,
                'room_type_room': room.room_type_room,
            })
        
        return JsonResponse({
            'status': 'success',
            'rooms': rooms_data
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error getting rooms: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["POST"])
def add_room(request):
    """API สำหรับเพิ่มห้องเรียน"""
    try:
        data = json.loads(request.body)
        
        room = RoomSchedule.objects.create(
            room_name_room=data.get('room_name_room'),
            room_type_room=data.get('room_type_room', ''),
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'เพิ่มข้อมูลห้องเรียนสำเร็จ',
            'room_id': room.id
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error adding room: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["POST"])
def add_room_bulk(request):
    """API สำหรับเพิ่มห้องเรียนหลายห้องพร้อมกัน"""
    try:
        # body อาจเป็น b'' ได้ จัด default เป็น {} กันพัง
        data = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse(
            {"status": "error", "message": "รูปแบบ JSON ไม่ถูกต้อง"},
            status=400, json_dumps_params={"ensure_ascii": False}
        )

    rooms_data = data.get("rooms", [])
    if not isinstance(rooms_data, list):
        return JsonResponse(
            {"status": "error", "message": "ฟิลด์ 'rooms' ต้องเป็นลิสต์"},
            status=400, json_dumps_params={"ensure_ascii": False}
        )

    created_ids = []
    for room_data in rooms_data:
        room = RoomSchedule.objects.create(
            room_name_room = room_data.get("room_name_room", ""),
            room_type_room = room_data.get("room_type_room", "")
        )
        created_ids.append(room.id)

    return JsonResponse(
        {
            "status": "success",
            "message": f"เพิ่มข้อมูลห้องเรียน {len(created_ids)} ห้องสำเร็จ",
            "created_ids": created_ids
        },
        json_dumps_params={"ensure_ascii": False}
    )

@csrf_exempt
@require_http_methods(["PUT"])
def update_room(request, id):
    """API สำหรับแก้ไขข้อมูลห้องเรียน"""
    try:
        room = RoomSchedule.objects.get(id=id)
        data = json.loads(request.body)
        
        room.room_name_room = data.get('room_name_room', room.room_name_room)
        room.room_type_room = data.get('room_type_room', room.room_type_room)
        
        room.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'แก้ไขข้อมูลห้องเรียนสำเร็จ'
        }, json_dumps_params={'ensure_ascii': False})
    except RoomSchedule.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'ไม่พบข้อมูลห้องเรียน'
        }, status=404, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error updating room: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["DELETE"])
def delete_room(request, id):
    """API สำหรับลบข้อมูลห้องเรียน"""
    try:
        room = RoomSchedule.objects.get(id=id)
        room.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': 'ลบข้อมูลห้องเรียนสำเร็จ'
        }, json_dumps_params={'ensure_ascii': False})
    except RoomSchedule.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'ไม่พบข้อมูลห้องเรียน'
        }, status=404, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error deleting room: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["POST"])
def upload_room_csv(request):
    """API สำหรับอัปโหลดไฟล์ CSV ข้อมูลห้องเรียน"""
    try:
        if 'file' not in request.FILES:
            return JsonResponse({
                'status': 'error',
                'message': 'ไม่พบไฟล์ที่อัปโหลด'
            }, status=400, json_dumps_params={'ensure_ascii': False})
        
        csv_file = request.FILES['file']
        
        if not csv_file.name.endswith('.csv'):
            return JsonResponse({
                'status': 'error',
                'message': 'กรุณาอัปโหลดไฟล์ CSV เท่านั้น'
            }, status=400, json_dumps_params={'ensure_ascii': False})
        
        # อ่านไฟล์ CSV พร้อมจัดการ encoding
        try:
            decoded_file = csv_file.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            for enc in ('utf-8', 'cp874', 'tis-620', 'cp1252'):
                try:
                    csv_file.seek(0)
                    decoded_file = csv_file.read().decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
        
        csv_data = StringIO(decoded_file)
        reader = csv.DictReader(csv_data)
        
        created_count = 0
        errors = []
        
        for row_num, row in enumerate(reader, start=2):
            try:
                RoomSchedule.objects.create(
                    room_name_room=norm_code(row.get('room_name_room', '')),
                    room_type_room=norm(row.get('room_type_room', '')),
                )
                created_count += 1
            except Exception as e:
                errors.append(f'แถว {row_num}: {str(e)}')
        
        if errors:
            return JsonResponse({
                'status': 'partial_success',
                'message': f'อัปโหลดสำเร็จ {created_count} รายการ แต่มีข้อผิดพลาด {len(errors)} รายการ',
                'created_count': created_count,
                'errors': errors[:10]
            }, json_dumps_params={'ensure_ascii': False})
        
        return JsonResponse({
            'status': 'success',
            'message': f'อัปโหลดข้อมูลห้องเรียนสำเร็จ {created_count} รายการ',
            'created_count': created_count
        }, json_dumps_params={'ensure_ascii': False})
        
    except Exception as e:
        logger.error(f"Error uploading room CSV: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'เกิดข้อผิดพลาดในการอัปโหลด: {str(e)}'
        }, status=500, json_dumps_params={'ensure_ascii': False})

# ========== STUDENT APIs ==========

@csrf_exempt
def get_students(request):
    """API สำหรับดึงข้อมูลนักศึกษาทั้งหมด"""
    try:
        students = StudentGroup.objects.all()
        students_data = []
        
        for student in students:
            students_data.append({
                'id': student.id,
                'student_group': student.student_group,
                'subject_code_stu': student.subject_code_stu,
                'curriculum_type_stu': student.curriculum_type_stu,
            })
        
        return JsonResponse({
            'status': 'success',
            'students': students_data
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error getting students: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["POST"])
def add_student(request):
    """API สำหรับเพิ่มกลุ่มนักศึกษา"""
    try:
        data = json.loads(request.body)
        student = StudentGroup.objects.create(
            student_group=data.get('student_group'),
            subject_code_stu=data.get('subject_code_stu'),
            curriculum_type_stu=data.get('curriculum_type_stu', ''),
        )
        return JsonResponse({
            'status': 'success',
            'message': 'เพิ่มข้อมูลกลุ่มนักศึกษาสำเร็จ',
            'student_id': student.id
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error adding student: {e}")
        return JsonResponse({'status':'error','message':str(e)},
                            status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["POST"])
def add_student_bulk(request):
    """API สำหรับเพิ่มกลุ่มนักศึกษาหลายกลุ่มพร้อมกัน"""
    try:
        data = json.loads(request.body)
        students_data = data.get('students', [])
        
        created_students = []
        for student_data in students_data:
            student = StudentGroup.objects.create(
                student_group=student_data.get('student_group'),
                subject_code_stu=student_data.get('subject_code_stu'),
                curriculum_type_stu=student_data.get('curriculum_type_stu', ''),
            )
            created_students.append(student.id)
        
        return JsonResponse({
            'status': 'success',
            'message': f'เพิ่มข้อมูลกลุ่มนักศึกษา {len(created_students)} กลุ่มสำเร็จ',
            'created_ids': created_students
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error adding students bulk: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["PUT"])
def update_student(request, id):
    """API สำหรับแก้ไขข้อมูลกลุ่มนักศึกษา"""
    try:
        student = StudentGroup.objects.get(id=id)
        data = json.loads(request.body)
        
        student.student_group = data.get('student_group', student.student_group)
        student.subject_code_stu = data.get('subject_code_stu', student.subject_code_stu)
        student.curriculum_type_stu = data.get('curriculum_type_stu', student.curriculum_type_stu)
        
        student.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'แก้ไขข้อมูลกลุ่มนักศึกษาสำเร็จ'
        }, json_dumps_params={'ensure_ascii': False})
    except StudentGroup.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'ไม่พบข้อมูลกลุ่มนักศึกษา'
        }, status=404, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error updating student: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["DELETE"])
def delete_student(request, id):
    """API สำหรับลบข้อมูลกลุ่มนักศึกษา"""
    try:
        student = StudentGroup.objects.get(id=id)
        student.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': 'ลบข้อมูลกลุ่มนักศึกษาสำเร็จ'
        }, json_dumps_params={'ensure_ascii': False})
    except StudentGroup.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'ไม่พบข้อมูลกลุ่มนักศึกษา'
        }, status=404, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error deleting student: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["POST"])
def upload_student_csv(request):
    """API สำหรับอัปโหลดไฟล์ CSV ข้อมูลกลุ่มนักศึกษา"""
    try:
        if 'file' not in request.FILES:
            return JsonResponse({
                'status': 'error',
                'message': 'ไม่พบไฟล์ที่อัปโหลด'
            }, status=400, json_dumps_params={'ensure_ascii': False})
        
        csv_file = request.FILES['file']
        
        if not csv_file.name.endswith('.csv'):
            return JsonResponse({
                'status': 'error',
                'message': 'กรุณาอัปโหลดไฟล์ CSV เท่านั้น'
            }, status=400, json_dumps_params={'ensure_ascii': False})
        
        # อ่านไฟล์ CSV พร้อมจัดการ encoding
        try:
            decoded_file = csv_file.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            for enc in ('utf-8', 'cp874', 'tis-620', 'cp1252'):
                try:
                    csv_file.seek(0)
                    decoded_file = csv_file.read().decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
        
        csv_data = csv.DictReader(StringIO(decoded_file))
        
        created_count = 0
        for row in csv_data:
            StudentGroup.objects.create(
                student_group=norm(row.get('student_group', '')),
                subject_code_stu=norm_code(row.get('subject_code_stu', '')),
                curriculum_type_stu=norm(row.get('curriculum_type_stu', '')),
            )
            created_count += 1
        
        return JsonResponse({
            'status': 'success',
            'message': f'อัปโหลดข้อมูลกลุ่มนักศึกษา {created_count} รายการสำเร็จ'
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error uploading student CSV: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'เกิดข้อผิดพลาดในการอัปโหลดไฟล์: {str(e)}'
        }, status=500, json_dumps_params={'ensure_ascii': False})

# ========== PRE-SCHEDULE APIs ==========

@csrf_exempt
def get_pre(request):
    """API สำหรับดึงข้อมูลตารางล่วงหน้าทั้งหมด"""
    try:
        pre_schedules = PreSchedule.objects.all()
        pre_data = []
        
        for pre in pre_schedules:
            pre_data.append({
                'id': pre.id,
                'teacher_name_pre': pre.teacher_name_pre,
                'subject_code_pre': pre.subject_code_pre,
                'subject_name_pre': pre.subject_name_pre,
                'curriculum_type_pre': pre.curriculum_type_pre,
                'room_type_pre': pre.room_type_pre,
                'section_pre': pre.section_pre,
                'theory_slot_amount_pre': pre.theory_slot_amount_pre,
                'lab_slot_amount_pre': pre.lab_slot_amount_pre,
                'day_pre': pre.day_pre,
                'start_time_pre': pre.start_time_pre.strftime('%H:%M') if pre.start_time_pre else '',
                'stop_time_pre': pre.stop_time_pre.strftime('%H:%M') if pre.stop_time_pre else '',
                'room_name_pre': pre.room_name_pre,
            })
        
        return JsonResponse({
            'status': 'success',
            'pre_schedules': pre_data
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error getting pre schedules: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["POST"])
def add_pre(request):
    """API สำหรับเพิ่มตารางล่วงหน้า"""
    try:
        data = json.loads(request.body)
        
        # แปลงเวลาจาก string เป็น time object
        start_time = parse_time_flexible(data.get('start_time_pre'), '08:00')
        stop_time  = parse_time_flexible(data.get('stop_time_pre'),  '09:00')

        
        pre = PreSchedule.objects.create(
            teacher_name_pre=data.get('teacher_name_pre'),
            subject_code_pre=data.get('subject_code_pre'),
            subject_name_pre=data.get('subject_name_pre'),
            curriculum_type_pre=data.get('curriculum_type_pre', ''),
            room_type_pre=data.get('room_type_pre', ''),
            section_pre=data.get('section_pre', ''),
            theory_slot_amount_pre=data.get('theory_slot_amount_pre', 0),
            lab_slot_amount_pre=data.get('lab_slot_amount_pre', 0),
            day_pre=data.get('day_pre', ''),
            start_time_pre=start_time,
            stop_time_pre=stop_time,
            room_name_pre=data.get('room_name_pre', ''),
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'เพิ่มตารางล่วงหน้าสำเร็จ',
            'pre_id': pre.id
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error adding pre schedule: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["PUT"])
def update_pre(request, id):
    """API สำหรับแก้ไขตารางล่วงหน้า"""
    try:
        pre = PreSchedule.objects.get(id=id)
        data = json.loads(request.body)
        
        pre.teacher_name_pre = data.get('teacher_name_pre', pre.teacher_name_pre)
        pre.subject_code_pre = data.get('subject_code_pre', pre.subject_code_pre)
        pre.subject_name_pre = data.get('subject_name_pre', pre.subject_name_pre)
        pre.curriculum_type_pre = data.get('curriculum_type_pre', pre.curriculum_type_pre)
        pre.room_type_pre = data.get('room_type_pre', pre.room_type_pre)
        pre.section_pre = data.get('section_pre', pre.section_pre)
        pre.theory_slot_amount_pre = data.get('theory_slot_amount_pre', pre.theory_slot_amount_pre)
        pre.lab_slot_amount_pre = data.get('lab_slot_amount_pre', pre.lab_slot_amount_pre)
        pre.day_pre = data.get('day_pre', pre.day_pre)
        pre.room_name_pre = data.get('room_name_pre', pre.room_name_pre)
        
        # แปลงเวลาถ้ามีการส่งมา
        if data.get('start_time_pre'):
            pre.start_time_pre = parse_time_flexible(data.get('start_time_pre'), '08:00')
        if data.get('stop_time_pre'):
            pre.stop_time_pre = parse_time_flexible(data.get('stop_time_pre'), '09:00')
        
        pre.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'แก้ไขตารางล่วงหน้าสำเร็จ'
        }, json_dumps_params={'ensure_ascii': False})
    except PreSchedule.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'ไม่พบข้อมูลตารางล่วงหน้า'
        }, status=404, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error updating pre schedule: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["DELETE"])
def delete_pre(request, id):
    """API สำหรับลบตารางล่วงหน้า"""
    try:
        pre = PreSchedule.objects.get(id=id)
        pre.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': 'ลบตารางล่วงหน้าสำเร็จ'
        }, json_dumps_params={'ensure_ascii': False})
    except PreSchedule.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'ไม่พบข้อมูลตารางล่วงหน้า'
        }, status=404, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error deleting pre schedule: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["POST"])
def upload_pre_csv(request):
    """API สำหรับอัปโหลดไฟล์ CSV ตารางล่วงหน้า"""
    try:
        if 'file' not in request.FILES:
            return JsonResponse({
                'status': 'error',
                'message': 'ไม่พบไฟล์ที่อัปโหลด'
            }, status=400, json_dumps_params={'ensure_ascii': False})
        
        csv_file = request.FILES['file']
        
        if not csv_file.name.endswith('.csv'):
            return JsonResponse({
                'status': 'error',
                'message': 'กรุณาอัปโหลดไฟล์ CSV เท่านั้น'
            }, status=400, json_dumps_params={'ensure_ascii': False})
        
        # อ่านไฟล์ CSV พร้อมจัดการ encoding
        try:
            decoded_file = csv_file.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            for enc in ('utf-8', 'cp874', 'tis-620', 'cp1252'):
                try:
                    csv_file.seek(0)
                    decoded_file = csv_file.read().decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
        
        csv_data = StringIO(decoded_file)
        reader = csv.DictReader(csv_data)
        
        created_count = 0
        errors = []
        
        for row_num, row in enumerate(reader, start=2):
            try:
                PreSchedule.objects.create(
                    teacher_name_pre=norm(row.get('teacher_name_pre', '')),
                    subject_code_pre=norm_code(row.get('subject_code_pre', '')),
                    subject_name_pre=norm(row.get('subject_name_pre', '')),
                    curriculum_type_pre=norm(row.get('curriculum_type_pre', '')),
                    room_type_pre=norm(row.get('room_type_pre', '')),
                    section_pre=norm(row.get('section_pre', '')),
                    theory_slot_amount_pre=to_int(row.get('theory_slot_amount_pre', 0)),
                    lab_slot_amount_pre=to_int(row.get('lab_slot_amount_pre', 0)),
                    day_pre=norm(row.get('day_pre', '')),
                    start_time_pre=parse_time_flexible(row.get('start_time_pre'), '08:00'),
                    stop_time_pre=parse_time_flexible(row.get('stop_time_pre'), '09:00'),
                    room_name_pre=norm_code(row.get('room_name_pre', '')),
                )
                created_count += 1
            except Exception as e:
                errors.append(f'แถว {row_num}: {str(e)}')
        
        if errors:
            return JsonResponse({
                'status': 'partial_success',
                'message': f'อัปโหลดสำเร็จ {created_count} รายการ แต่มีข้อผิดพลาด {len(errors)} รายการ',
                'created_count': created_count,
                'errors': errors[:10]
            }, json_dumps_params={'ensure_ascii': False})
        
        return JsonResponse({
            'status': 'success',
            'message': f'อัปโหลดตารางล่วงหน้าสำเร็จ {created_count} รายการ',
            'created_count': created_count
        }, json_dumps_params={'ensure_ascii': False})
        
    except Exception as e:
        logger.error(f"Error uploading pre CSV: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'เกิดข้อผิดพลาดในการอัปโหลด: {str(e)}'
        }, status=500, json_dumps_params={'ensure_ascii': False})

# ========== ACTIVITIES APIs ==========

@csrf_exempt
def get_activities(request):
    """API สำหรับดึงข้อมูลกิจกรรมทั้งหมด"""
    try:
        activities = ActivitySchedule.objects.all()
        activities_data = []
        
        for activity in activities:
            activities_data.append({
                'id': activity.id,
                'act_name_activities': activity.act_name_activities,
                'day_activities': activity.day_activities,
                'start_time_activities': activity.start_time_activities.strftime('%H:%M') if activity.start_time_activities else '',
                'stop_time_activities': activity.stop_time_activities.strftime('%H:%M') if activity.stop_time_activities else '',
            })
        
        return JsonResponse({
            'status': 'success',
            'activities': activities_data
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error getting activities: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["POST"])
def add_activities(request):
    """API สำหรับเพิ่มกิจกรรม"""
    try:
        data = json.loads(request.body)
        
        # แปลงเวลาจาก string เป็น time object
        start_time = parse_time_flexible(data.get('start_time_activities'), '08:00')
        stop_time  = parse_time_flexible(data.get('stop_time_activities'),  '09:00')

        
        activity = ActivitySchedule.objects.create(
            act_name_activities=data.get('act_name_activities'),
            day_activities=data.get('day_activities', ''),
            start_time_activities=start_time,
            stop_time_activities=stop_time,
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'เพิ่มกิจกรรมสำเร็จ',
            'activity_id': activity.id
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error adding activity: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["POST"])
def add_activities_bulk(request):
    """API สำหรับเพิ่มกิจกรรมหลายรายการพร้อมกัน"""
    try:
        data = json.loads(request.body)
        activities_data = data.get('activities', [])
        
        created_activities = []
        for activity_data in activities_data:
            # แปลงเวลาจาก string เป็น time object
            start_time = parse_time_flexible(activity_data.get('start_time_activities'), '08:00')
            stop_time  = parse_time_flexible(activity_data.get('stop_time_activities'),  '09:00')

            
            activity = ActivitySchedule.objects.create(
                act_name_activities=activity_data.get('act_name_activities'),
                day_activities=activity_data.get('day_activities', ''),
                start_time_activities=start_time,
                stop_time_activities=stop_time,
            )
            created_activities.append(activity.id)
        
        return JsonResponse({
            'status': 'success',
            'message': f'เพิ่มกิจกรรม {len(created_activities)} รายการสำเร็จ',
            'created_ids': created_activities
        }, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error adding activities bulk: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["PUT"])
def update_activities(request, id):
    """API สำหรับแก้ไขกิจกรรม"""
    try:
        activity = ActivitySchedule.objects.get(id=id)
        data = json.loads(request.body)
        
        activity.act_name_activities = data.get('act_name_activities', activity.act_name_activities)
        activity.day_activities = data.get('day_activities', activity.day_activities)
        
        # แปลงเวลาถ้ามีการส่งมา
        if data.get('start_time_activities'):
            activity.start_time_activities = parse_time_flexible(data.get('start_time_activities'), '08:00')
        if data.get('stop_time_activities'):
            activity.stop_time_activities = parse_time_flexible(data.get('stop_time_activities'), '09:00')
 
        activity.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'แก้ไขกิจกรรมสำเร็จ'
        }, json_dumps_params={'ensure_ascii': False})
    except ActivitySchedule.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'ไม่พบข้อมูลกิจกรรม'
        }, status=404, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error updating activity: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["DELETE"])
def delete_activities(request, id):
    """API สำหรับลบกิจกรรม"""
    try:
        activity = ActivitySchedule.objects.get(id=id)
        activity.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': 'ลบกิจกรรมสำเร็จ'
        }, json_dumps_params={'ensure_ascii': False})
    except ActivitySchedule.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'ไม่พบข้อมูลกิจกรรม'
        }, status=404, json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error(f"Error deleting activity: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["POST"])
def upload_activities_csv(request):
    """API สำหรับอัปโหลดไฟล์ CSV กิจกรรม"""
    try:
        if 'file' not in request.FILES:
            return JsonResponse({
                'status': 'error',
                'message': 'ไม่พบไฟล์ที่อัปโหลด'
            }, status=400, json_dumps_params={'ensure_ascii': False})
        
        csv_file = request.FILES['file']
        
        if not csv_file.name.endswith('.csv'):
            return JsonResponse({
                'status': 'error',
                'message': 'กรุณาอัปโหลดไฟล์ CSV เท่านั้น'
            }, status=400, json_dumps_params={'ensure_ascii': False})
        
        # อ่านไฟล์ CSV พร้อมจัดการ encoding
        try:
            decoded_file = csv_file.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            for enc in ('utf-8', 'cp874', 'tis-620', 'cp1252'):
                try:
                    csv_file.seek(0)
                    decoded_file = csv_file.read().decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
        
        csv_data = StringIO(decoded_file)
        reader = csv.DictReader(csv_data)
        
        created_count = 0
        errors = []
        
        for row_num, row in enumerate(reader, start=2):
            try:
                ActivitySchedule.objects.create(
                    act_name_activities=norm(row.get('act_name_activities', '')),
                    day_activities=norm(row.get('day_activities', '')),
                    start_time_activities=parse_time_flexible(row.get('start_time_activities'), '08:00'),
                    stop_time_activities=parse_time_flexible(row.get('stop_time_activities'), '09:00'),
                )
                created_count += 1
            except Exception as e:
                errors.append(f'แถว {row_num}: {str(e)}')
        
        if errors:
            return JsonResponse({
                'status': 'partial_success',
                'message': f'อัปโหลดสำเร็จ {created_count} รายการ แต่มีข้อผิดพลาด {len(errors)} รายการ',
                'created_count': created_count,
                'errors': errors[:10]
            }, json_dumps_params={'ensure_ascii': False})
        
        return JsonResponse({
            'status': 'success',
            'message': f'อัปโหลดกิจกรรมสำเร็จ {created_count} รายการ',
            'created_count': created_count
        }, json_dumps_params={'ensure_ascii': False})
        
    except Exception as e:
        logger.error(f"Error uploading activities CSV: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'เกิดข้อผิดพลาดในการอัปโหลด: {str(e)}'
        }, status=500, json_dumps_params={'ensure_ascii': False})

# ========== Time Parsing Utility ==========

def parse_time_flexible(value, default_time='08:00'):
    """
    แปลงเวลาแบบยืดหยุ่น:
    - "8"     -> 08:00
    - "8:5"   -> 08:05
    - "8:30"  -> 08:30
    - "8.30"  -> 08:30   (ตีความส่วนหลังจุดเป็น 'นาที' ถ้า <= 59)
    - "8.5"   -> 08:30   (ตีความทศนิยมเป็น 'เศษชั่วโมง')
    - เว้นว่าง/None -> default_time
    """
    s = '' if value is None else str(value).strip()
    if s == '':
        s = default_time

    # ปรับโคลอนแบบฟูลวิธ และตัดช่องว่าง
    s = s.replace('：', ':').strip()

    # กรณีรูปแบบ HH:MM ปกติ
    try:
        return datetime.strptime(s, '%H:%M').time()
    except ValueError:
        pass

    # ถ้าไม่มีโคลอนเลย -> อาจเป็น "8" หรือ "8.5" หรือ "8.30"
    if ':' not in s:
        # กรณี "8.30" (จุดแปลว่านาที) หรือ "8.5" (ทศนิยมชั่วโมง)
        if '.' in s:
            left, right = s.split('.', 1)
            if left.isdigit() and right.isdigit():
                # ตีความแบบ 'นาที' ก่อน หาก right <= 59
                hh = int(left)
                mm = int(right[:2])  # เอา 2 หลักแรก
                if 0 <= hh <= 23 and 0 <= mm <= 59:
                    return time(hh, mm)
            # ไม่ใช่นาที -> ลองตีความเป็นชั่วโมงทศนิยม
            try:
                f = float(s.replace(',', '.'))
                if 0 <= f < 24:
                    hh = int(f)
                    mm = int(round((f - hh) * 60))
                    if mm == 60:
                        hh += 1
                        mm = 0
                    if 0 <= hh <= 23:
                        return time(hh, mm)
            except Exception:
                pass

        # กรณีเป็นตัวเลขล้วน "8" -> "08:00"
        if s.isdigit():
            hh = int(s)
            if 0 <= hh <= 23:
                return time(hh, 0)

        # อย่างอื่น แปลงไม่ได้ -> ใช้ดีฟอลต์
        return datetime.strptime(default_time, '%H:%M').time()

    # กรณีมีโคลอน แต่ไม่ครบ 2 หลัก เช่น "8:5" -> 08:05
    parts = s.split(':', 1)
    if all(p.strip().isdigit() for p in parts):
        hh = int(parts[0]); mm = int(parts[1])
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return time(hh, mm)

    # สุดท้าย fallback
    return datetime.strptime(default_time, '%H:%M').time()

# ========== Download Schedule API ==========

@csrf_exempt
@require_http_methods(["GET"])
def download_schedule(request):
    """ดาวน์โหลดตารางสอนเป็น CSV (ใช้ Hour)"""
    try:
        # เหมือน DB:
        qs = ScheduleInfo.objects.order_by('id')

        import csv
        from io import StringIO
        buff = StringIO()
        writer = csv.DictWriter(buff, fieldnames=[
            'Course_Code', 'Subject_Name', 'Teacher',
            'Room', 'Room_Type', 'Type', 'Day', 'Hour'
        ])
        writer.writeheader()
        for s in qs:
            writer.writerow({
                'Course_Code': s.Course_Code,
                'Subject_Name': s.Subject_Name,
                'Teacher': s.Teacher,
                'Room': s.Room,
                'Room_Type': s.Room_Type,
                'Type': s.Type,
                'Day': s.Day,
                'Hour': s.Hour
            })

        csv_text = buff.getvalue()
        csv_bytes = ('\ufeff' + csv_text).encode('utf-8-sig')  # BOM เพื่อเปิดใน Excel ภาษาไทย

        from django.http import HttpResponse
        resp = HttpResponse(csv_bytes, content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = 'attachment; filename="schedule.csv"'
        return resp

    except Exception as e:
        logger.error(f"Error downloading schedule: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)},
                            status=500, json_dumps_params={'ensure_ascii': False})