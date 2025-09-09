import pandas as pd
import random
from collections import defaultdict
import json
import sys
import time as _time

# ===============================================================
# Globals
# ===============================================================
TIME_SLOTS_FROM_DB = defaultdict(set)  # {"จันทร์": {8,9,...}, ...}
SLOT_POOL = {}  # {"A101": ["จันทร์_8", ...], ...}

# def normalize_locked_sections(locked_df):
#     """
#     Auto-increment section สำหรับ locked_courses.csv
#     - จัดกลุ่มตาม (subject_code, curriculum_type)
#     - ให้เลข section ไล่จาก 1, 2, 3, ...
#     """
#     locked_df = locked_df.copy()
#     locked_df["section"] = (
#         locked_df.groupby(["subject_code", "curriculum_type"]).cumcount() + 1
#     )
#     return locked_df


def normalize_locked_sections(locked_df: pd.DataFrame) -> pd.DataFrame:
    """
    กำหนด section อัตโนมัติสำหรับ locked_courses ตามกติกา:
    - นับ section ต่อ 'subject_code' (ไม่แยกภาคปกติ/พิเศษ)
    - ครูคนเดียวกัน + วิชาเดียวกัน:
        * ถ้าเป็น theory + lab  (type ต่างกัน) => อยู่ 'sec เดียวกัน'
        * ถ้าเป็น theory ซ้ำหลายแถว (type เดียวกัน) => เปิด 'sec ใหม่' ตามจำนวน
        * ถ้าเป็น lab-only (ไม่มี theory) => รวมเป็น 'sec เดียว'
    - ครูคนละคน (ในวิชาเดียวกัน) => เปิด sec ใหม่ตามลำดับที่พบ
    """
    if locked_df is None or locked_df.empty:
        return locked_df

    df = locked_df.copy()
    df.columns = df.columns.str.strip()

    # ---- เตรียมคอลัมน์ 'type' ให้พร้อม ----
    if "type" not in df.columns:
        # รองรับฟอร์แมตเก่า (theory_slot/lab_slot)
        th = df.get("theory_slot")
        lb = df.get("lab_slot")
        if th is None and lb is None:
            raise ValueError(
                "locked_df ไม่มีคอลัมน์ type หรือ theory_slot/lab_slot ให้ระบุชนิดคลาส"
            )
        df["type"] = df.apply(
            lambda r: (
                "lab"
                if int(r.get("lab_slot") or 0) > 0
                and int(r.get("theory_slot") or 0) == 0
                else "theory"
            ),
            axis=1,
        )
    else:
        df["type"] = df["type"].astype(str).str.lower().str.strip()

    # ---- เตรียมชื่ออาจารย์ให้เป็นมาตรฐาน (ถ้ามี normalize_teacher) ----
    def _norm_teacher(x):
        s = str(x).strip()
        return s

    df["teacher_norm"] = df.get("teacher_name", "").map(_norm_teacher)

    # ---- สร้างคอลัมน์ section (ค่าเริ่ม 0) ----
    df["section"] = 0

    # ---- เดินทีละวิชา (subject_code) และจัดเลข sec ตามกติกา ----
    # ใช้อินเด็กซ์เดิมเพื่อคงลำดับที่ผู้ใช้กรอก
    for subject_code, g in df.groupby("subject_code", sort=False):
        sec_counter = 0

        # เดินตาม "ครู" ในลำดับที่ปรากฏในไฟล์
        teachers_in_order = g.drop_duplicates(subset=["teacher_norm"])[
            "teacher_norm"
        ].tolist()

        for teacher in teachers_in_order:
            mask_teacher = (df["subject_code"] == subject_code) & (
                df["teacher_norm"] == teacher
            )

            idx_theory = df.index[mask_teacher & (df["type"] == "theory")].tolist()
            idx_lab = df.index[mask_teacher & (df["type"] == "lab")].tolist()

            if len(idx_theory) > 0:
                # สร้าง sec ใหม่ตามจำนวน 'theory' ที่พบ (theory ซ้ำ = คนละ sec)
                sec_ids_for_this_teacher = []
                for idx in idx_theory:
                    sec_counter += 1
                    df.at[idx, "section"] = sec_counter
                    sec_ids_for_this_teacher.append(sec_counter)

                # แนบ lab ทั้งหมด (ถ้ามี) เข้ากับ 'sec แรก' ของครูคนนี้
                if len(idx_lab) > 0:
                    first_sec = sec_ids_for_this_teacher[0]
                    for idx in idx_lab:
                        df.at[idx, "section"] = first_sec
            else:
                # ไม่มี theory เลย แต่มี lab → รวม lab เป็น sec เดียว
                if len(idx_lab) > 0:
                    sec_counter += 1
                    for idx in idx_lab:
                        df.at[idx, "section"] = sec_counter

        # ปิดกลุ่ม: ถ้าเผื่อมีแถวไหนยังไม่ได้ section (กรณีพิเศษ) ให้กันรันตก
        unassigned = df.index[
            (df["subject_code"] == subject_code) & (df["section"] == 0)
        ].tolist()
        if unassigned:
            for idx in unassigned:
                sec_counter += 1
                df.at[idx, "section"] = sec_counter

    # เก็บงาน: ไม่ต้องใช้คอลัมน์ช่วยแล้ว
    df.drop(columns=["teacher_norm"], inplace=True)

    # ให้ section เป็น int ชัดเจน
    df["section"] = df["section"].astype(int)

    return df


# ===============================================================
# TimeSlot preprocessing
# ===============================================================
def preprocess_time_slots(timeslot_df):
    """
    เติม TIME_SLOTS_FROM_DB จาก TimeSlot.csv
    รองรับทั้งคอลัมน์ (day, hour) และ (day_of_week, start_time, stop_time)
    """
    global TIME_SLOTS_FROM_DB
    TIME_SLOTS_FROM_DB.clear()

    if timeslot_df is None or timeslot_df.empty:
        return

    df = timeslot_df.copy()
    df.columns = df.columns.str.lower().str.strip()

    if {"day", "hour"}.issubset(df.columns):
        for _, row in df.iterrows():
            d = str(row["day"]).strip()
            try:
                h = int(row["hour"])
            except Exception:
                continue
            TIME_SLOTS_FROM_DB[d].add(h)

    elif {"day_of_week", "start_time", "stop_time"}.issubset(df.columns):
        for _, row in df.iterrows():
            d = str(row["day_of_week"]).strip()
            try:
                st, en = int(row["start_time"]), int(row["stop_time"])
            except Exception:
                continue
            for h in range(st, en):
                TIME_SLOTS_FROM_DB[d].add(h)


# ===============================================================
# Build SLOT_POOL (room × all available times from TimeSlot.csv)
# ===============================================================
def build_slot_pool(timeslot_df, room_df):
    """
    สร้าง SLOT_POOL โดย "ทุกห้อง" จะได้รายการ time slot ทั้งหมดจาก TimeSlot.csv ตั้งต้นเท่ากัน
    (ต่อไปเมื่อมีการจอง จะลบ slot ออกจาก pool ของห้องนั้น ๆ)
    """
    global SLOT_POOL
    SLOT_POOL = {}

    if timeslot_df is None or timeslot_df.empty or room_df is None or room_df.empty:
        return

    df = timeslot_df.copy()
    df.columns = df.columns.str.lower().str.strip()

    all_times = []
    if {"day", "hour"}.issubset(df.columns):
        for _, row in df.iterrows():
            d = str(row["day"]).strip()
            try:
                h = int(row["hour"])
            except Exception:
                continue
            all_times.append(f"{d}_{h}")

    elif {"day_of_week", "start_time", "stop_time"}.issubset(df.columns):
        for _, row in df.iterrows():
            d = str(row["day_of_week"]).strip()
            try:
                st, en = int(row["start_time"]), int(row["stop_time"])
            except Exception:
                continue
            for h in range(st, en):
                all_times.append(f"{d}_{h}")

    # unique + sorted by (day string, hour int)
    def _key(ts):
        d, h = ts.split("_")
        return (d, int(h))

    all_times = sorted(set(all_times), key=_key)

    for _, r in room_df.iterrows():
        room = str(r.get("room_name", "")).strip()
        if room:
            SLOT_POOL[room] = list(all_times)


# ===============================================================
# Check time กันข้อมูลไม่เพียงพอในการจัด
# ===============================================================
def precheck_capacity_or_raise(courses, room_df, locked_classes, locked_activity_df):
    """
    เช็คว่า 'ชั่วโมงที่ต้องใช้' (ตาม room_type, curriculum_type) <= 'ชั่วโมงที่มีให้ใช้จริง'
    ถ้าไม่พอ: raise RuntimeError พร้อมรายละเอียด และหยุดโปรแกรม
    """
    # 1) สร้างชุดเวลาที่ถูกบล็อก (กิจกรรม) + การใช้ห้องที่ล็อกไว้แล้ว
    blocked = get_blocked_times_from_activities(locked_activity_df)
    locked_room_usage = set()
    for it in locked_classes:
        room = it.get("room")
        if room and room != "NO_VALID_ROOM":
            for t in it.get("time", []):
                if "NO_VALID_TIME" in t:
                    continue
                locked_room_usage.add((room, t))

    # 2) แผนที่ room -> room_type (lower-case)
    room_df_local = room_df.copy()
    room_df_local["room_name"] = room_df_local["room_name"].astype(str).str.strip()
    room_df_local["room_type"] = (
        room_df_local["room_type"].astype(str).str.lower().str.strip()
    )
    room_type_by_room = dict(
        zip(room_df_local["room_name"], room_df_local["room_type"])
    )

    # 3) ความจุ (capacity) ต่อคู่ (room_type, curriculum_type)
    #    นับจำนวน (room, time) ที่ยังว่างจริง และ 'ชั่วโมง' นั้นอยู่ในเกณฑ์หลักสูตร (get_hours_for_day)
    capacity = defaultdict(int)
    for room, slots in SLOT_POOL.items():
        rt = room_type_by_room.get(room, "")
        if not rt:
            continue
        slot_set = set(slots)  # ช่องที่เหลืออยู่ใน pool
        # ลบที่ถูกบล็อกทั่วระบบ + ที่ล็อกห้องนั้นไว้แล้ว
        slot_set -= blocked
        slot_set -= {t for r, t in locked_room_usage if r == room}

        # ตรวจตามกฎชั่วโมงของหลักสูตร
        for cur in ["ภาคปกติ", "ภาคพิเศษ"]:
            ok = 0
            for ts in slot_set:
                if "_" not in ts:
                    continue
                d, h = ts.split("_", 1)
                try:
                    h = int(h)
                except Exception:
                    continue
                if h in set(get_hours_for_day(d, cur)):
                    ok += 1
            capacity[(rt, cur)] += ok

    # 4) อุปสงค์ (demand): รวมชั่วโมงที่ต้องใช้จาก courses ตาม (room_type, curriculum_type)
    demand = defaultdict(int)
    for c in courses:
        demand[(c["room_type"], c.get("curriculum_type", "ภาคปกติ"))] += int(c["hours"])

    # 5) เปรียบเทียบแล้วสรุปปัญหา
    problems = []
    for key, need in demand.items():
        cap = capacity.get(key, 0)
        if cap < need:
            rt, cur = key
            problems.append((rt, cur, need, cap))

    if problems:
        lines = ["❌ เวลาที่มี ‘ไม่พอ’ ต่อไปนี้:"]
        for rt, cur, need, cap in problems:
            lines.append(
                f"- curriculum='{cur}', room_type='{rt}': ต้องการ {need} ชม. แต่มีแค่ {cap} ชม."
            )
        lines.append("โปรดเพิ่มช่องเวลา/เพิ่มห้อง/ลดล็อก หรือปรับชั่วโมงรายวิชา ก่อนค่อยรัน GA")
        raise RuntimeError("\n".join(lines))


# ===============================================================
# Curriculum helpers (วัน/ชั่วโมงที่อนุญาต)
# ===============================================================
def get_valid_days_and_hours(curriculum_type):
    """
    คืน (valid_days, hours_by_day) จาก TIME_SLOTS_FROM_DB ตามประเภทหลักสูตร
    """
    days_in_db = list(TIME_SLOTS_FROM_DB.keys())
    weekdays = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์"]
    weekends = ["เสาร์", "อาทิตย์"]

    if curriculum_type == "ภาคปกติ":
        valid_days = [d for d in days_in_db if d in weekdays]
    else:
        # ภาคพิเศษ: เปิดทั้ง จ–ศ และ เสาร์–อาทิตย์ (แต่ชั่วโมงต่างกันใน get_hours_for_day)
        valid_days = [d for d in days_in_db if d in weekdays or d in weekends]

    hours_by_day = {d: sorted(TIME_SLOTS_FROM_DB[d]) for d in valid_days}
    return valid_days, hours_by_day


def get_hours_for_day(day, curriculum_type):
    """
    คืนลิสต์ชั่วโมงที่ใช้ได้ของวันนั้น ๆ ตามหลักสูตร โดยอิงจาก TIME_SLOTS_FROM_DB
    ปรับใหม่:
    - ภาคปกติ: จ–ศ 8–19
    - ภาคพิเศษ: จ–ศ 17–22, เสาร์–อาทิตย์ 7–22
    """
    hours_from_db = list(TIME_SLOTS_FROM_DB.get(day, set()))
    weekdays = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์"]
    weekends = ["เสาร์", "อาทิตย์"]

    if curriculum_type == "ภาคปกติ":
        return sorted([h for h in hours_from_db if 8 <= h <= 19 and day in weekdays])
    elif curriculum_type == "ภาคพิเศษ":
        if day in weekdays:
            return sorted([h for h in hours_from_db if 17 <= h <= 22])
        elif day in weekends:
            return sorted([h for h in hours_from_db if 7 <= h <= 22])
        else:
            return []
    else:
        return []


# ===============================================================
# Room helpers
# ===============================================================
def get_valid_rooms(room_type, room_df):
    """คืนรายชื่อห้องที่รองรับ room_type นั้น ๆ"""
    if room_df is None or room_df.empty:
        return []
    rt = str(room_type).strip().lower()
    return (
        room_df.loc[room_df["room_type"].str.lower() == rt, "room_name"]
        .astype(str)
        .str.strip()
        .tolist()
    )


def find_available_rooms(candidate_times, room_usage, valid_room_names):
    """หา "ห้อง" ที่ว่างครบทุกชั่วโมงใน candidate_times (จาก room_usage)"""
    available = []
    for room in valid_room_names:
        if all((room, t) not in room_usage for t in candidate_times):
            available.append(room)
    return available


# ===============================================================
# NEW: get_consecutive_times ใช้ SLOT_POOL (มีตัวเลือกส่ง slot_pool เฉพาะของ individual)
# ===============================================================


def get_consecutive_times(
    hours_needed,
    blocked_times,
    room_usage,
    valid_room_names,
    curriculum_type,
    teacher_usage,
    teacher_name,
    slot_pool,
):
    """
    ดึงช่วงเวลาต่อเนื่องจาก slot_pool (หรือ SLOT_POOL ถ้าไม่ส่งมา)
    - เคารพ block activity (blocked_times)
    - กันชนอาจารย์ (teacher_usage)
    - กันชนห้อง (room_usage)
    - เลือกห้องแบบ balance: ใช้ห้องที่ถูกใช้น้อยสุด (tie-break ด้วยสุ่ม)
    - reserve slot หลังจากเลือก candidate แล้วเท่านั้น
    """
    pool = slot_pool

    # นับจำนวนการใช้งานของแต่ละห้องจาก room_usage เพื่อนำมา balance
    room_use_count = {}
    for r, t in room_usage:
        room_use_count[r] = room_use_count.get(r, 0) + 1

    candidates = []  # เก็บ (room, segment)

    for room in valid_room_names:
        if room not in pool:
            continue
        free_slots = pool[room]

        # หา "ช่วงต่อเนื่องแรกที่ valid" ของห้องนี้ (ถ้าเจอจะหยุดที่ห้องนี้แค่ 1 segment)
        found_segment = None

        for i in range(0, len(free_slots) - hours_needed + 1):
            segment = free_slots[i : i + hours_needed]

            # ต่อเนื่องใน "วันเดียวกัน"
            ok = True
            prev_day, prev_hour = None, None
            for s in segment:
                if "_" not in s:
                    ok = False
                    break
                d, h = s.split("_")
                try:
                    h = int(h)
                except Exception:
                    ok = False
                    break
                if prev_day is not None:
                    if d != prev_day or h != prev_hour + 1:
                        ok = False
                        break
                prev_day, prev_hour = d, h
            if not ok:
                continue

            # ชั่วโมงต้องถูกหลักสูตร
            valid_hours = set(get_hours_for_day(prev_day, curriculum_type))
            if not all(int(ts.split("_")[1]) in valid_hours for ts in segment):
                continue

            # กันกิจกรรม / อาจารย์ / ห้อง
            if any(s in blocked_times for s in segment):
                continue
            if teacher_usage is not None and teacher_name:
                if any((teacher_name, s) in teacher_usage for s in segment):
                    continue
            if any((room, s) in room_usage for s in segment):
                continue

            found_segment = segment
            break  # เอา segment แรกของห้องนี้พอ

        if found_segment:
            candidates.append((room, found_segment))

    # ถ้าไม่มีผู้สมัครเลย → ส่ง NO_VALID_TIME
    if not candidates:
        return {
            "times": [f"NO_VALID_TIME_{i}" for i in range(hours_needed)],
            "available_rooms": [],
        }

    # เลือก candidate ที่ใช้ห้องน้อยสุด (ถ้าเสมอกันสุ่ม)
    # score = จำนวนใช้ห้อง (น้อยดีกว่า)
    min_use = min(room_use_count.get(r, 0) for r, _ in candidates)
    best_rooms = [
        (r, seg) for r, seg in candidates if room_use_count.get(r, 0) == min_use
    ]

    room, segment = random.choice(best_rooms)

    # reserve: ลบสลอตที่เลือกออกจาก pool ของห้องนั้น
    for s in segment:
        try:
            pool[room].remove(s)
        except ValueError:
            pass

    return {"times": segment, "available_rooms": [room]}


# ===============================================================
# Loaders / extractors for locked items
# ===============================================================
def extract_locked_schedule(locked_df):
    """
    แปลงตาราง locked_courses → รายวิชา/เวลา/ห้องที่ fix แล้ว
    คาดหวังคอลัมน์: subject_code, subject_name, teacher_name, curriculum_type, room_name, room_type, section, theory_slot, lab_slot, day, start_time, stop_time
    """
    items = []
    if locked_df is None or locked_df.empty:
        return items

    df = locked_df.copy()
    df.columns = df.columns.str.lower().str.strip()

    for _, row in df.iterrows():
        subj = str(row.get("subject_code")).strip()
        sname = str(row.get("subject_name")).strip()
        teacher = str(row.get("teacher_name")).strip()
        curriculum = str(row.get("curriculum_type")).strip()
        room = str(row.get("room_name")).strip()
        room_type = str(row.get("room_type")).strip().lower()
        type = str(row.get("type")).strip().lower()
        hours = str(row.get("hours")).strip()
        section = str(row.get("section")).strip()
        day = str(row.get("day")).strip()
        st = row.get("start_time")
        en = row.get("stop_time")

        times = []
        if day and pd.notnull(st) and pd.notnull(en):
            try:
                st = int(st)
                en = int(en)
                times = [f"{day}_{h}" for h in range(st, en)]
            except Exception:
                times = []
        if not subj:
            continue

        hours_expected = en - st if pd.notnull(st) and pd.notnull(en) else None
        try:
            hours_int = int(hours) if hours else None
        except ValueError:
            hours_int = None

        if hours_expected is not None and hours_int is not None:
            if hours_int != hours_expected:
                print(
                    f"⚠️ Warning: {subj}_sec{section} ({type}) "
                    f"hours={hours_int} แต่เวลาจริง={hours_expected}"
                )
        
        course_name = f"{subj}_sec{section}" + ("_lab" if type == "lab" else "")

        items.append(
            {
                "course": course_name,
                "subject_name": sname or subj,
                "teacher": teacher,
                "room": room if room else "NO_VALID_ROOM",
                "room_type": room_type,
                "type": type,
                "curriculum_type": curriculum if curriculum else "ภาคปกติ",
                "time": times,
            }
        )

    return items

def extract_locked_activities(locked_activity_df):
    """
    คืนกิจกรรมที่บล็อกช่วงเวลาทั้งระบบ (เช่น สอบกลางภาค/ปัจฉิมนิเทศ)
    คาดหวังคอลัมน์: activity_name, day, start_time, stop_time
    """
    items = []
    if locked_activity_df is None or locked_activity_df.empty:
        return items

    for _, row in locked_activity_df.iterrows():
        code = str(row.get("activity_name", "")).strip()
        day = str(row.get("day", "")).strip()
        st = row.get("start_time")
        en = row.get("stop_time")
        times = []
        if day and pd.notnull(st) and pd.notnull(en):
            try:
                st = int(st)
                en = int(en)
                times = [f"{day}_{h}" for h in range(st, en)]
            except Exception:
                times = []

        items.append(
            {
                "course": code,
                "subject_name": code,
                "teacher": None,
                "room": None,
                "room_type": None,
                "type": "activity",
                "curriculum_type": None,
                "time": times,
            }
        )
    return items

def get_blocked_times_from_activities(locked_activity_df):
    """สร้างเซ็ตของ time slot ที่ถูกบล็อกแบบ global จาก locked_activities"""
    blocked = set()
    if locked_activity_df is None or locked_activity_df.empty:
        return blocked

    df = locked_activity_df.copy()
    df.columns = df.columns.str.lower().str.strip()

    for _, row in df.iterrows():
        day = str(row.get("day", "")).strip()
        st = row.get("start_time")
        en = row.get("stop_time")
        if day and pd.notnull(st) and pd.notnull(en):
            try:
                st = int(st)
                en = int(en)
                for h in range(st, en):
                    blocked.add(f"{day}_{h}")
            except Exception:
                continue
    return blocked

# ===============================================================
# apply_blocks_to_slot_pool ลบ slot ที่ lock_activaity ใช้ไปแล้ว
# ===============================================================
def apply_blocks_to_slot_pool(locked_activity_df):
    """
    ลบสลอตที่ 'ใช้ไม่ได้จริง' ออกจาก SLOT_POOL โดยตรง
    - กิจกรรม (locked_activities): ลบจากทุกห้อง (global)
    """
    global SLOT_POOL

    # 1) บล็อกจากกิจกรรม (ลบออกจากทุกห้อง)
    blocked = get_blocked_times_from_activities(locked_activity_df)
    if blocked:
        for room in list(SLOT_POOL.keys()):
            # เก็บเฉพาะสลอตที่ไม่ได้ถูกบล็อก
            SLOT_POOL[room] = [t for t in SLOT_POOL[room] if t not in blocked]


# ===============================================================
# GA Runner
# ===============================================================
def run_genetic_algorithm(data_loader, write_csv=False, return_df=False):
    try:
        # -------------------- Load data --------------------
        course_df, room_df, locked_df, locked_activity_df, timeslot_df = data_loader()

        # ✅ จัด section ของ locked ให้เริ่มจาก 1 ต่อเนื่องตาม (subject_code, curriculum_type)
        locked_df = normalize_locked_sections(locked_df)

        # ---------------- Preprocess time slots & pool ----------------
        preprocess_time_slots(timeslot_df)
        build_slot_pool(timeslot_df, room_df)

        # ---------------- Prepare courses list ----------------
        courses = []

        # ✅ สร้างแผนที่ "max section" ที่ locked ใช้ไปแล้ว ต่อ (subject_code, curriculum_type)
        locked_section_map = (
            locked_df.groupby(["subject_code"])["section"]
            .max()
            .to_dict()
            if not locked_df.empty
            else {}
        )

        # ✅ ตัวนับ section ต่อ (subject_code, curriculum_type) โดยเริ่มจากค่าที่ locked ใช้ไปแล้ว
        subject_section_counter = defaultdict(int)
        for key, max_sec in locked_section_map.items():
            subject_section_counter[key] = int(max_sec)

        for _, row in course_df.iterrows():
            subject_code = str(row.get("subject_code", "")).strip()
            subject_name = str(row.get("subject_name", "")).strip()
            teacher_name = str(row.get("teacher_name", "")).strip()
            room_type = str(row.get("room_type", "")).strip().lower()
            theory_slot = int(row.get("theory_slot") or 0)
            lab_slot = int(row.get("lab_slot") or 0)
            section_count = int(row.get("section_count") or 0)
            curriculum_type = str(row.get("curriculum_type", "")).strip() or "ภาคปกติ"

            key = (subject_code)

            for _sec in range(1, section_count + 1):
                # เพิ่ม section ต่อจากที่ locked ใช้ไปแล้ว
                subject_section_counter[key] += 1
                current_section = subject_section_counter[key]
                suffix = f"_sec{current_section}"

                if theory_slot > 0:
                    courses.append(
                        {
                            "name": subject_code + suffix,
                            "subject_name": subject_name or subject_code,
                            "teacher": teacher_name,
                            "type": "theory",
                            "room_type": room_type,
                            "hours": theory_slot,
                            "curriculum_type": curriculum_type,
                        }
                    )
                if lab_slot > 0:
                    courses.append(
                        {
                            "name": subject_code + suffix + "_lab",
                            "subject_name": subject_name or subject_code,
                            "teacher": teacher_name,
                            "type": "lab",
                            "room_type": room_type,
                            "hours": lab_slot,
                            "curriculum_type": curriculum_type,
                        }
                    )

        # ---------------- Locked items ----------------
        locked_classes = extract_locked_schedule(locked_df)
        locked_activities = extract_locked_activities(locked_activity_df)
        all_locked_items = locked_classes + locked_activities
        locked_names = {c["course"] for c in locked_classes}

        # global blocked times (กิจกรรมเท่านั้น)
        all_blocked_times = get_blocked_times_from_activities(locked_activity_df)
        
        apply_blocks_to_slot_pool(locked_activity_df)

        precheck_capacity_or_raise(courses, room_df, locked_classes, locked_activity_df)

        # ---------------- GA components ----------------
        def create_individual():
            """
            สร้าง individual เดียวโดยใช้ "สำเนา" ของ SLOT_POOL (local_pool) เพื่อไม่ส่งผลกับตัวอื่น
            ใช้ heuristic แบบง่าย: เรียงวิชาที่ยังไม่ล็อกโดยชั่วโมงมากก่อน + ห้องรองรับน้อยก่อน
            """
            # เริ่มต้นจากสำเนา pool (ของแต่ละ individual)
            local_pool = {room: slots.copy() for room, slots in SLOT_POOL.items()}

            individual = list(all_locked_items)  # ใส่ที่ล็อกไว้ก่อน
            used_times = set()
            room_usage = set()
            teacher_usage = set()

            # อัปเดต usage จากของที่ล็อกแล้ว และ remove ออกจาก local_pool
            for item in individual:
                for t in item["time"]:
                    if "NO_VALID_TIME" in t:
                        continue
                    used_times.add(t) # บันทึกเวลา
                    if item.get("room") and item["room"] != "NO_VALID_ROOM":
                        room_usage.add((item["room"], t)) # บันทึกห้อง
                        if item["room"] in local_pool and t in local_pool[item["room"]]:
                            try:
                                local_pool[item["room"]].remove(t)
                            except ValueError:
                                pass
                    if item.get("teacher"):
                        teacher_usage.add((item["teacher"], t))

            # ---------- NEW: วางวิชาที่ยังไม่ล็อก (เรียงตาม LPT + Scarcity) ----------
            unlocked_courses = [c for c in courses if c["name"] not in locked_names]

            def sort_key(c):
                # 1) ชั่วโมงที่ต้องใช้ (มากก่อน)
                h_key = -int(c.get("hours", 0))
                # 2) ห้องรองรับน้อย (scarcity) → มาก่อน
                room_choices = len(get_valid_rooms(c["room_type"], room_df))
                scarcity_key = room_choices
                return (h_key, scarcity_key)

            # เรียงลำดับวิชาที่ยังไม่ล็อก
            unlocked_courses.sort(key=sort_key)

            # วางวิชาตามลำดับที่เรียงไว้
            for c in unlocked_courses:
                valid_room_names = get_valid_rooms(c["room_type"], room_df)
                curriculum_type = c.get("curriculum_type")

                result = get_consecutive_times(
                    c["hours"],
                    all_blocked_times,
                    room_usage,
                    valid_room_names,
                    curriculum_type,
                    teacher_usage=teacher_usage,
                    teacher_name=c["teacher"],
                    slot_pool=local_pool,  # ใช้ pool เฉพาะ individual
                )
                times = result["times"]
                available_rooms = result["available_rooms"]
                selected_room = (
                    available_rooms[0] if available_rooms else "NO_VALID_ROOM"
                )

                cls = {
                    "course": c["name"],
                    "subject_name": c.get("subject_name", c["name"]),
                    "teacher": c["teacher"],
                    "room": selected_room,
                    "room_type": c["room_type"],
                    "type": c["type"],
                    "time": times,
                    "curriculum_type": curriculum_type,
                }

                # อัปเดต usage + remove
                for t in times:
                    if "NO_VALID_TIME" in t:
                        continue
                    used_times.add(t)
                    if selected_room != "NO_VALID_ROOM":
                        room_usage.add((selected_room, t))
                        if (
                            selected_room in local_pool
                            and t in local_pool[selected_room]
                        ):
                            try:
                                local_pool[selected_room].remove(t)
                            except ValueError:
                                pass
                    if c["teacher"]:
                        teacher_usage.add((c["teacher"], t))

                individual.append(cls)

            return individual

        def fitness(individual):
            """
            ให้คะแนนตาราง: กันชนห้อง/อาจารย์, เคารพหลักสูตร, bonus ช่วงต่อเนื่อง
            """
            score = 0
            used = {"teacher_time": set(), "room_time": set()}

            for cls in individual:
                curriculum_type = cls.get("curriculum_type", "ภาคปกติ")

                # ตรวจเวลาแต่ละสลอต
                for t in cls["time"]:
                    if "NO_VALID_TIME" in t:
                        score -= 1000
                        continue

                    if t in all_blocked_times:
                        score -= 1000

                    if "_" not in t:
                        score -= 50
                        continue

                    day, hour_str = t.split("_")
                    try:
                        hour = int(hour_str)
                    except Exception:
                        score -= 50
                        continue

                    valid_hours = get_hours_for_day(day, curriculum_type)
                    if hour not in valid_hours:
                        score -= 50
                        continue

                    # กันชนอาจารย์
                    if cls.get("teacher"):
                        key = (cls["teacher"], t)
                        if key in used["teacher_time"]:
                            score -= 1000
                        else:
                            used["teacher_time"].add(key)
                            score += 30

                    # กันชนห้อง
                    room = cls.get("room")
                    if room and room != "NO_VALID_ROOM":
                        key = (room, t)
                        if key in used["room_time"]:
                            score -= 1000
                        else:
                            used["room_time"].add(key)
                            score += 30

                # bonus: เวลาต่อเนื่องในวันเดียวกัน
                valid_times = [
                    t for t in cls["time"] if "NO_VALID_TIME" not in t and "_" in t
                ]
                if valid_times:
                    times_sorted = sorted(
                        valid_times,
                        key=lambda x: (x.split("_")[0], int(x.split("_")[1])),
                    )
                    contiguous_bonus = 0
                    prev_day, prev_hour = None, None
                    for t in times_sorted:
                        d, h = t.split("_")
                        h = int(h)
                        if (
                            prev_day == d
                            and prev_hour is not None
                            and h == prev_hour + 1
                        ):
                            contiguous_bonus += 5
                        prev_day, prev_hour = d, h
                    score += contiguous_bonus

            return score

        def crossover(p1, p2):
            """
            ผสมพันธุ์: รักษารายการที่ล็อกไว้ + ผสมส่วนที่ไม่ล็อก
            """
            locked = [
                cls.copy()
                for cls in p1
                if cls["course"] in locked_names or cls["type"] == "activity"
            ]
            u1 = [
                cls.copy()
                for cls in p1
                if cls["course"] not in locked_names and cls["type"] != "activity"
            ]
            u2 = [
                cls.copy()
                for cls in p2
                if cls["course"] not in locked_names and cls["type"] != "activity"
            ]

            if len(u1) > 1:
                point = random.randint(1, len(u1) - 1)
                child_unlocked = u1[:point] + u2[point:]
            else:
                child_unlocked = u1

            return locked + child_unlocked


        def _build_local_pool_from_individual(individual):
            """
            สร้าง local_pool จาก SLOT_POOL และลบสลอตที่ถูกใช้ใน individual ออก
            """
            lp = {room: slots.copy() for room, slots in SLOT_POOL.items()}
            for cls in individual:
                room = cls.get("room")
                if room and room in lp:
                    for t in cls["time"]:
                        if t in lp[room]:
                            try:
                                lp[room].remove(t)
                            except ValueError:
                                pass
            return lp

        def mutate(individual, rate=0.02):
            """
            กลายพันธุ์: เคลื่อนคลาสที่ไม่ล็อกไปยังช่วง/ห้องใหม่ โดยใช้ local_pool ที่เหลืออยู่
            """
            locked_items = [
                c.copy()
                for c in individual
                if c["course"] in locked_names or c["type"] == "activity"
            ]
            unlocked_items = [
                c.copy()
                for c in individual
                if c["course"] not in locked_names and c["type"] != "activity"
            ]

            # usage ปัจจุบันในตาราง
            room_usage = set()
            teacher_usage = set()
            for item in locked_items + unlocked_items:
                for t in item["time"]:
                    if "NO_VALID_TIME" in t:
                        continue
                    if item.get("room") and item["room"] != "NO_VALID_ROOM":
                        room_usage.add((item["room"], t))
                    if item.get("teacher"):
                        teacher_usage.add((item["teacher"], t))

            for cls in unlocked_items:
                if random.random() < rate:
                    # เอา usage เดิมของคลาสนี้ออกก่อน
                    for t in cls["time"]:
                        if "NO_VALID_TIME" in t:
                            continue
                        if cls.get("room") and cls["room"] != "NO_VALID_ROOM":
                            room_usage.discard((cls["room"], t))
                        if cls.get("teacher"):
                            teacher_usage.discard((cls["teacher"], t))

                    valid_room_names = get_valid_rooms(cls["room_type"], room_df)
                    curriculum_type = cls.get("curriculum_type", "ภาคปกติ")

                    # hours_needed จาก courses list
                    original = next(
                        (c for c in courses if c["name"] == cls["course"]), None
                    )
                    hours_needed = original["hours"] if original else len(cls["time"])

                    # ใช้ local_pool จากทั้ง individual
                    local_pool = _build_local_pool_from_individual(
                        locked_items + unlocked_items
                    )

                    result = get_consecutive_times(
                        hours_needed,
                        all_blocked_times,
                        room_usage,
                        valid_room_names,
                        curriculum_type,
                        teacher_usage=teacher_usage,
                        teacher_name=cls.get("teacher"),
                        slot_pool=local_pool,
                    )
                    cls["time"] = result["times"]
                    avail = result["available_rooms"]
                    cls["room"] = avail[0] if avail else "NO_VALID_ROOM"

                    # ใส่ usage ใหม่กลับ
                    for t in cls["time"]:
                        if "NO_VALID_TIME" in t:
                            continue
                        if cls.get("room") and cls["room"] != "NO_VALID_ROOM":
                            room_usage.add((cls["room"], t))
                        if cls.get("teacher"):
                            teacher_usage.add((cls["teacher"], t))

            return locked_items + unlocked_items

        def genetic_algorithm(pop_size, generations):
            population = [create_individual() for _ in range(pop_size)]

            best_individual_overall = None
            best_fitness_overall = float("-inf")
            fitness_old = None
            break_point = 0 

            for gen in range(generations):

                population.sort(key=lambda ind: fitness(ind), reverse=True)
                best = population[0]
                best_fit = fitness(best)

                print(f"Gen {gen:03d} | Fitness: {best_fit}")

                if best_fit > best_fitness_overall:
                    best_fitness_overall = best_fit
                    best_individual_overall = [c.copy() for c in best]

                if best_fit == fitness_old:
                    break_point += 1
                else:
                    break_point = 0  # reset ถ้ามีการเปลี่ยนแปลง

                if break_point >= 100:  # หยุดถ้าไม่มีการปรับปรุง 50 รอบติด
                    print("Early stopping: no improvement in 100 generations.")
                    break
                
                fitness_old = fitness(best)

                # next generation
                next_gen = population[:5]  # elites
                while len(next_gen) < pop_size:
                    p1, p2 = random.sample(population[:5], 2)
                    child = crossover(p1, p2)
                    child = mutate(child, rate=0.02)
                    next_gen.append(child)
                population = next_gen

            return best_individual_overall 



        def save_schedule(schedule, write_csv=False, out_path="schedule.csv"):
            rows = []
            for cls in schedule:
                for t in cls["time"]:
                    day = t.split("_")[0] if "_" in t else "N/A"
                    hour = (
                        int(t.split("_")[1])
                        if "_" in t and t.split("_")[1].isdigit()
                        else None
                    )
                    rows.append(
                        {
                            "Course_Code": cls["course"],
                            "Subject_Name": cls.get("subject_name"),
                            "Teacher": cls.get("teacher"),
                            "Room": cls.get("room"),
                            "Room_Type": cls.get("room_type"),
                            "Type": cls.get("type"),
                            "Curriculum_Type": cls.get("curriculum_type"),
                            "Day": day,
                            "Hour": hour,
                            "Time_Slot": t,
                        }
                    )
            rows.sort(key=lambda x: x["Course_Code"] or "")

            df = pd.DataFrame(rows)
            if write_csv:
                df.to_csv(out_path, index=False, encoding="utf-8-sig")
                print(f"✅ บันทึกไฟล์ {out_path} แล้ว")
            return df

        # ---------------- Run GA (3 rounds) ----------------
        best_schedules = []
        durations = []

        print("Start Round")
        t0 = _time.perf_counter()
        best = genetic_algorithm(pop_size=30, generations=300)
        t1 = _time.perf_counter()
        durations.append(t1 - t0)
        fit = fitness(best)
        best_schedules.append({"best_schedule": best, "fitness": fit})

        # ===============================================================================

        # for i in range(10):
        #     print(f"🔁 Round {i+1}/10")
        #     t0 = _time.perf_counter()
        #     # เรียกใช้ Genetic Algorithm
        #     best = genetic_algorithm(pop_size=30, generations=500)
        #     t1 = _time.perf_counter()
        #     durations.append(t1 - t0)
        #     # คำนวณ fitness จาก best schedule
        #     fit = fitness(best) 
            
        #     # เก็บข้อมูล
        #     best_schedules.append({
        #         "round": i + 1,
        #         "best_schedule": best,
        #         "fitness": fit
        #     })
        

        # #เรียงลำดับจาก fitness มาก → น้อย
        # best_schedules.sort(key=lambda x: x["fitness"], reverse=True)
        # average_fitness = sum(s["fitness"] for s in best_schedules) / len(best_schedules)
        # print("Average fitness:", average_fitness)
        # for s in best_schedules:
        #     print(f"Round {s['round']}: fitness = {s['fitness']}")

        # ===============================================================================
        
        #ดึงตัวที่ดีที่สุด
        best_schedule = best_schedules[0]["best_schedule"]

        #ส่งไปยัง save_schedule
        final_df = save_schedule(best_schedule, write_csv=write_csv)

        resp = {
            "status": "success",
            "message": "สร้างตารางสำเร็จ",
            "total_entries": len(final_df),
            "fitness_score": best_schedules[0]["fitness"],
            "total_time_sec": sum(durations),
        }
        if write_csv:
            resp["file_path"] = "schedule.csv"
        if return_df:
            resp["final_df"] = final_df
        return resp

    except Exception as e:
        return {"status": "error", "message": f"เกิดข้อผิดพลาด: {str(e)}"}

def run_genetic_algorithm_from_db():
    """รัน GA โดยใช้ข้อมูลจาก Django ORM — ไม่อ่าน/เขียน CSV เลย"""
    import pandas as pd
    from django.db import transaction
    from .models import (
        TeacherSchedule, RoomSchedule, PreSchedule,
        ActivitySchedule, Timedata, ScheduleInfo
    )

    def to_int(x, default=0):
        try:
            return int(str(x).strip())
        except Exception:
            return default

    def to_hour(v):
        if v is None:
            return None
        s = str(v).strip()
        try:
            if ":" in s:
                return int(s.split(":")[0])
            return int(s)
        except Exception:
            return None

    def section_count(x):
        try:
            return int(str(x).strip())
        except Exception:
            return 1

    # ----- ORM -> DataFrames -----
    room_df = pd.DataFrame([{
        "room_name": r.room_name_room or "",
        "room_type": (r.room_type_room or "").strip(),
    } for r in RoomSchedule.objects.all()])

    time_df = pd.DataFrame([{
        "day_of_week": (t.day_of_week or "").strip(),
        "start_time": to_hour(t.start_time),
        "stop_time": to_hour(t.stop_time),
    } for t in Timedata.objects.all()])

    course_df = pd.DataFrame([{
        "subject_code": t.subject_code_teacher or "",
        "subject_name": t.subject_name_teacher or "",
        "teacher_name": t.teacher_name_teacher or "",
        "room_type":    t.room_type_teacher or "",
        "theory_slot":  to_int(t.theory_slot_amount_teacher, 0),
        "lab_slot":     to_int(t.lab_slot_amount_teacher, 0),
        "section_count": section_count(t.section_teacher),
        "curriculum_type": (t.curriculum_type_teacher or "ภาคปกติ").strip() or "ภาคปกติ",
    } for t in TeacherSchedule.objects.all()])

    locked_df = pd.DataFrame([{
        "subject_code": p.subject_code_pre or "",
        "subject_name": p.subject_name_pre or "",
        "teacher_name": p.teacher_name_pre or "",
        "curriculum_type": (p.curriculum_type_pre or "ภาคปกติ").strip() or "ภาคปกติ",
        "room_name": p.room_name_pre or "",
        "room_type": p.room_type_pre or "",
        "type": (p.type_pre or "").strip().lower(),   # 'theory' / 'lab' ถ้ามี
        "hours": to_int(p.hours_pre, 0),
        "section": 1,
        "day": (p.day_pre or "").strip(),
        "start_time": to_hour(p.start_time_pre),
        "stop_time": to_hour(p.stop_time_pre),
    } for p in PreSchedule.objects.all()])

    locked_activity_df = pd.DataFrame([{
        "activity_name": a.act_name_activities or "",
        "day": (a.day_activities or "").strip(),
        "start_time": to_hour(a.start_time_activities),
        "stop_time": to_hour(a.stop_time_activities),
    } for a in ActivitySchedule.objects.all()])

    if room_df.empty:
        return {"status": "error", "message": "ไม่มีข้อมูลห้องเรียน (RoomSchedule)"}
    if time_df.empty:
        return {"status": "error", "message": "ไม่มีข้อมูลช่วงเวลา (Timedata)"}

    # ----- เรียก GA โดยส่ง loader (ไม่อ่าน CSV) -----
    def loader():
        return course_df, room_df, locked_df, locked_activity_df, time_df

    result = run_genetic_algorithm(loader, write_csv=False, return_df=True)
    final_df = result.pop("final_df", pd.DataFrame())
    
    # ----- เขียนเข้า ScheduleInfo -----
    def to_int0(x):
        try:
            return int(str(x).strip())
        except Exception:
            return 0

    from .models import ScheduleInfo
    with transaction.atomic():
        ScheduleInfo.objects.all().delete()
        items = []
        for _, row in final_df.iterrows():
            items.append(ScheduleInfo(
                Course_Code=row.get("Course_Code", ""),
                Subject_Name=row.get("Subject_Name", ""),
                Teacher=row.get("Teacher", ""),
                Room=row.get("Room", ""),
                Room_Type=row.get("Room_Type", ""),
                Type=row.get("Type", ""),
                Curriculum_Type=row.get("Curriculum_Type", ""),
                Day=row.get("Day", ""),
                Hour=to_int0(row.get("Hour", 0)),
                Time_Slot=row.get("Time_Slot", ""),
            ))
        if items:
            ScheduleInfo.objects.bulk_create(items, batch_size=1000)
            
            # ----- ถ้าไม่มีแถวให้บันทึก ให้ถือว่า error -----
        if not items:
            result.update({
                "status": "error",
                "message": (
                    "สร้างตารางไม่สำเร็จ: ไม่มีชั่วโมง/เงื่อนไขให้จัด (final_df ว่าง). "
                    "กรุณาตรวจข้อมูลต้นทาง: ห้องเรียน/ช่วงเวลา/ชั่วโมงสอน และชนิดห้องให้สอดคล้อง"
                ),
                "total_entries": 0,
            })
            return result

    result.update({
        "status": "success",
        "message": (result.get("message") or "สร้างตารางสำเร็จ") +
                   f" และบันทึกลงฐานข้อมูล {len(items)} แถวแล้ว",
        "total_entries": len(items),
    })
    return result

# ===============================================================
# Entry
# ===============================================================
if __name__ == "__main__":
    print("Use run_genetic_algorithm_from_db() via Django views. (No CSV mode)")
