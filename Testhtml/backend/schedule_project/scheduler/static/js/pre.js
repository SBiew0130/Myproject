// ===== helper: set selected value on <select> =====
function setSelectValue(sel, val) {
  if (!sel) return;
  const hit = [...sel.options].find(o => o.value === val || o.text === val);
  if (hit) sel.value = hit.value;
  else if (val !== undefined && val !== null && String(val).trim() !== '') {
    const opt = document.createElement('option');
    opt.value = val;
    opt.text = val;
    sel.appendChild(opt);
    sel.value = val;
  }
}

// ===== time utilities =====
function hhmmToMinutes(hhmm){
  if(!hhmm) return null;
  const [h,m]=hhmm.split(':').map(Number);
  return (isNaN(h)||isNaN(m))?null:(h*60+m);
}
function minutesToHHMM(mins){
  mins = ((mins % 1440) + 1440) % 1440;
  const h = String(Math.floor(mins/60)).padStart(2,'0');
  const m = String(mins%60).padStart(2,'0');
  return `${h}:${m}`;
}
function calcEnd(startStr, hoursStr){
  const s=hhmmToMinutes(startStr), h=parseFloat(hoursStr||0);
  if(s===null || !isFinite(h) || h<=0) return '';
  return minutesToHHMM(s + Math.round(h*60));
}
function wireAutoStop(startSel, hoursSel, stopSel){
  const startEl = document.querySelector(startSel);
  const hoursEl = document.querySelector(hoursSel);
  const stopEl  = document.querySelector(stopSel);
  if(!startEl||!hoursEl||!stopEl) return;

  const update = () => {
    const end = calcEnd(startEl.value, hoursEl.value);
    if(!end){ stopEl.value=''; return; }
    let hit=[...stopEl.options].find(o=>o.value===end||o.text===end);
    if(!hit){
      const opt=document.createElement('option');
      opt.value=end; opt.text=end;
      stopEl.appendChild(opt);
      hit=opt;
    }
    stopEl.value = end;
  };
  startEl.addEventListener('change', update);
  hoursEl.addEventListener('input', update);
  update();
}

// ===== notification system =====
function showNotification(message, type='info', duration=5000){
  const container = document.getElementById('notificationContainer');
  const notification = document.createElement('div');
  const typeMap = {success:'success', error:'error', warning:'warning', info:'info', debug:'info'};
  const notificationType = typeMap[type] || 'info';

  notification.className = `notification ${notificationType}`;
  notification.innerHTML = `
    <button class="notification-close" onclick="closeNotification(this)">&times;</button>
    <div>${message}</div>
    <div class="notification-progress"></div>
  `;
  container.appendChild(notification);

  setTimeout(()=>notification.classList.add('show'),100);

  const progressBar = notification.querySelector('.notification-progress');
  progressBar.style.width = '100%';
  setTimeout(()=>{ progressBar.style.width='0%'; progressBar.style.transitionDuration = duration+'ms'; }, 100);

  setTimeout(()=> closeNotification(notification.querySelector('.notification-close')), duration);
}
function closeNotification(button){
  const notification = button.parentElement;
  notification.style.opacity='0';
  notification.style.transform='translateX(100%)';
  setTimeout(()=>{ if(notification.parentElement){ notification.parentElement.removeChild(notification); } }, 300);
}

// ===== csrf helper =====
function getCookie(name){
  let cookieValue=null;
  if(document.cookie && document.cookie!==''){
    const cookies=document.cookie.split(';');
    for(let i=0;i<cookies.length;i++){
      const cookie=cookies[i].trim();
      if(cookie.substring(0, name.length+1)===(name+'=')){
        cookieValue=decodeURIComponent(cookie.substring(name.length+1));
        break;
      }
    }
  }
  return cookieValue;
}

// ===== AJAX helper to populate selects =====
async function populateSelect(url, selectId, mapItem) {
  const sel = document.getElementById(selectId);
  if (!sel) return;
  const prev = sel.value;
  sel.innerHTML = '<option value="">กำลังโหลด...</option>';
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const payload = await r.json();
    const results = Array.isArray(payload)
      ? payload
      : (payload.results || payload.items || payload.days || payload.start_times || payload.stop_times || []);
    sel.innerHTML = '<option value="">เลือก</option>';
    (results || []).forEach(item => {
      const opt = document.createElement('option');
      const { value, label, dataset } = mapItem(item);
      opt.value = value; opt.textContent = label;
      if (dataset) Object.entries(dataset).forEach(([k, v]) => opt.dataset[k] = v);
      sel.appendChild(opt);
    });
    // keep previous value if exists
    if (prev) setSelectValue(sel, prev);
  } catch (e) {
    console.error(`Populate ${selectId} fail:`, e);
    sel.innerHTML = '<option value="">โหลดไม่สำเร็จ</option>';
  }
}

// ===== sync subject code/name =====
function wireSubjectCodeNameSync(codeSelId, nameSelId) {
  const codeSel = document.getElementById(codeSelId);
  const nameSel = document.getElementById(nameSelId);
  if (!codeSel || !nameSel) return;

  codeSel.addEventListener('change', () => {
    const codeOpt = codeSel.selectedOptions[0];
    if (!codeOpt) return;
    const sid = codeOpt.dataset.sid;
    if (!sid) return;
    const match = [...nameSel.options].find(o => o.dataset.sid === sid);
    if (match) nameSel.value = match.value;
  });

  nameSel.addEventListener('change', () => {
    const nameOpt = nameSel.selectedOptions[0];
    if (!nameOpt) return;
    const sid = nameOpt.dataset.sid;
    if (!sid) return;
    const match = [...codeSel.options].find(o => o.dataset.sid === sid);
    if (match) codeSel.value = match.value;
  });
}

// ===== CRUD functions =====
function addPreSchedule(){
  const payload = {
    teacher_name_pre   : document.getElementById("teacher_name_pre").value,
    subject_code_pre   : document.getElementById("subject_code_pre").value,
    subject_name_pre   : document.getElementById("subject_name_pre").value,
    room_type_pre      : document.getElementById("subject_type_pre").value,
    type_pre           : document.getElementById("type_pre").value,
    curriculum_type_pre: document.getElementById("student_type_pre").value,
    hours_pre          : Number(document.getElementById("hours_pre").value || 0),
    group_no_pre       : Number(document.getElementById("group_no_pre")?.value || 0), // กลุ่มเรียน (ใหม่)
    day_pre            : document.getElementById("day_pre").value,
    start_time_pre     : document.getElementById("start_time_pre").value,
    stop_time_pre      : document.getElementById("stop_time_pre").value,
    room_name_pre      : document.getElementById("room_name_pre").value,
  };

  if(!payload.subject_code_pre){ showNotification('กรุณาเลือกรหัสวิชา','warning'); return; }

  fetch('/api/pre/add/', {
    method:'POST',
    headers:{'Content-Type':'application/json','X-CSRFToken': getCookie('csrftoken')},
    body: JSON.stringify(payload)
  })
  .then(r=>r.json())
  .then(d=>{
    if(d.status==='success'){ showNotification('✅ เพิ่มวิชาล่วงหน้าสำเร็จ','success'); location.reload(); }
    else{ showNotification('เกิดข้อผิดพลาด: '+(d.message||'ไม่สามารถเพิ่มข้อมูลได้'),'error'); }
  })
  .catch(()=> showNotification('เกิดข้อผิดพลาดในการเพิ่มข้อมูล','error'));
}

function confirmDelete(button){
  if(confirm("คุณแน่ใจหรือไม่ว่าต้องการลบรายการนี้?")){
    const row = button.closest("tr");
    const id  = row.getAttribute("data-id");

    fetch(`/api/pre/delete/${id}/`, {
      method:'DELETE',
      headers:{ 'X-CSRFToken': getCookie('csrftoken') }
    })
    .then(r=>r.json())
    .then(d=>{
      if(d.status==='success'){ row.remove(); showNotification("✅ ลบข้อมูลเรียบร้อยแล้ว",'success'); }
      else{ showNotification('เกิดข้อผิดพลาดในการลบข้อมูล','error'); }
    })
    .catch(()=> showNotification('เกิดข้อผิดพลาดในการลบข้อมูล','error'));
  }
}

let editRow = null;
let editId  = null;
function openEditModal(button){
  editRow = button.closest("tr");
  editId  = editRow.getAttribute("data-id");
  const cells = editRow.getElementsByTagName("td");

  // ตั้งค่า dropdown/inputs จากค่าที่แสดงในตาราง (ใช้ setSelectValue สำหรับฟิลด์ที่โหลด async)
  setSelectValue(document.getElementById("editteacher_name_pre"), cells[0].innerText.trim());
  setSelectValue(document.getElementById("editsubject_code_pre"), cells[1].querySelector('.badge').innerText.trim());
  setSelectValue(document.getElementById("editsubject_name_pre"), cells[2].innerText.trim());
  setSelectValue(document.getElementById("editsubject_type_pre"), cells[3].innerText.trim());
  setSelectValue(document.getElementById("edittype_pre"), cells[4].innerText.trim());
  setSelectValue(document.getElementById("editstudent_type_pre"), cells[5].innerText.trim());
  document.getElementById("edithours_pre").value = cells[6].innerText.trim();

  // กลุ่มเรียน: ถ้าตารางมี data-group ให้ดึงใช้, ไม่งั้นเคลียร์ค่า
  const groupFromAttr = editRow.getAttribute('data-group');
  const groupInput = document.getElementById("editgroup_no_pre");
  if (groupInput) groupInput.value = groupFromAttr ? Number(groupFromAttr) : '';

  setSelectValue(document.getElementById("editday_pre"), cells[7].innerText.trim());
  setSelectValue(document.getElementById("editstart_time_pre"), cells[8].innerText.trim());
  setSelectValue(document.getElementById("editstop_time_pre"),  cells[9].innerText.trim());
  setSelectValue(document.getElementById("editroom_name_pre"), cells[10].innerText.trim());

  new bootstrap.Modal(document.getElementById("editModal")).show();
}

function saveEdit(){
  const payload = {
    teacher_name_pre   : document.getElementById("editteacher_name_pre").value,
    subject_code_pre   : document.getElementById("editsubject_code_pre").value,
    subject_name_pre   : document.getElementById("editsubject_name_pre").value,
    room_type_pre      : document.getElementById("editsubject_type_pre").value,
    type_pre           : document.getElementById("edittype_pre").value,
    curriculum_type_pre: document.getElementById("editstudent_type_pre").value,
    hours_pre          : Number(document.getElementById("edithours_pre").value || 0),
    group_no_pre       : Number(document.getElementById("editgroup_no_pre")?.value || 0), // กลุ่มเรียน (ใหม่)
    day_pre            : document.getElementById("editday_pre").value,
    start_time_pre     : document.getElementById("editstart_time_pre").value,
    stop_time_pre      : document.getElementById("editstop_time_pre").value,
    room_name_pre      : document.getElementById("editroom_name_pre").value,
  };

  fetch(`/api/pre/update/${editId}/`, {
    method:'PUT',
    headers:{'Content-Type':'application/json','X-CSRFToken': getCookie('csrftoken')},
    body: JSON.stringify(payload)
  })
  .then(r=>r.json())
  .then(d=>{
    if(d.status==='success'){
      showNotification("✅ แก้ไขข้อมูลเรียบร้อยแล้ว",'success');
      bootstrap.Modal.getInstance(document.getElementById("editModal")).hide();
      location.reload();
    }else{
      showNotification('เกิดข้อผิดพลาดในการแก้ไขข้อมูล','error');
    }
  })
  .catch(()=> showNotification('เกิดข้อผิดพลาดในการแก้ไขข้อมูล','error'));
}

function refreshData(){ location.reload(); }

// ===== init wiring =====
document.addEventListener('DOMContentLoaded', async () => {
  // --- Add Form dropdowns ---
  // ครู: backend คืน {items:[{id,name}...]} หรือ array -> map ให้รองรับทั้งสองแบบ
  await populateSelect('/api/teachers/', 'teacher_name_pre',
    t => ({ value: (t.name ?? t.label), label: (t.name ?? t.label) }));

  // วิชา: /api/subjects/ คืน array [{id,code,name}]
  await populateSelect('/api/subjects/', 'subject_code_pre',
    s => ({ value: s.code, label: s.code, dataset: { sid: String(s.id ?? s.sid ?? s.code) } }));
  await populateSelect('/api/subjects/', 'subject_name_pre',
    s => ({ value: s.name, label: s.name, dataset: { sid: String(s.id ?? s.sid ?? s.code) } }));
  wireSubjectCodeNameSync('subject_code_pre', 'subject_name_pre');

  // ห้อง: เปลี่ยนเป็น /api/room/list/
  await populateSelect('/api/room/list/', 'room_name_pre',
    r => ({ value: (r.name ?? r.id ?? r.value), label: (r.name ?? r.label) }));

  // หมวด/ประเภท (คงเดิมถ้ามี endpoint เหล่านี้)
  await populateSelect('/api/lookups/subject-types/',   'subject_type_pre', i => i);
  await populateSelect('/api/lookups/department-types/','type_pre',         i => i);
  await populateSelect('/api/lookups/curriculum-types/','student_type_pre', i => i);

  // วัน: เปลี่ยนเป็น /api/meta/days/
  await populateSelect('/api/meta/days/', 'day_pre',
    d => ({ value: (d.value ?? d), label: (d.text ?? d) }));

  // เวลาเริ่ม/เลิก: ใช้ meta + ผูก event ตามค่าที่เลือกจริง
  await loadStartTimesForCreate();      // โหลดตามค่า day ปัจจุบัน (ถ้ามี)
  document.getElementById('day_pre')?.addEventListener('change', loadStartTimesForCreate);
  document.getElementById('start_time_pre')?.addEventListener('change', loadStopTimesForCreate);

  // --- Edit Modal dropdowns ---
  await populateSelect('/api/teachers/', 'editteacher_name_pre',
    t => ({ value: (t.name ?? t.label), label: (t.name ?? t.label) }));
  await populateSelect('/api/subjects/', 'editsubject_code_pre',
    s => ({ value: s.code, label: s.code, dataset: { sid: String(s.id ?? s.sid ?? s.code) } }));
  await populateSelect('/api/subjects/', 'editsubject_name_pre',
    s => ({ value: s.name, label: s.name, dataset: { sid: String(s.id ?? s.sid ?? s.code) } }));
  wireSubjectCodeNameSync('editsubject_code_pre', 'editsubject_name_pre');

  await populateSelect('/api/room/list/', 'editroom_name_pre',
    r => ({ value: (r.name ?? r.id ?? r.value), label: (r.name ?? r.label) }));

  await populateSelect('/api/lookups/subject-types/',   'editsubject_type_pre', i => i);
  await populateSelect('/api/lookups/department-types/','edittype_pre',         i => i);
  await populateSelect('/api/lookups/curriculum-types/','editstudent_type_pre', i => i);

  await loadStartTimesForEdit();       // โหลดตามค่า day ปัจจุบัน (ถ้ามี)
  document.getElementById('editday_pre')?.addEventListener('change', loadStartTimesForEdit);
  document.getElementById('editstart_time_pre')?.addEventListener('change', loadStopTimesForEdit);

  // Auto-calc stop time (ตามชั่วโมงเรียน)
  wireAutoStop('#start_time_pre',      '#hours_pre',      '#stop_time_pre');
  wireAutoStop('#editstart_time_pre',  '#edithours_pre',  '#editstop_time_pre');
});

// ===== helper loaders for meta times =====
async function loadStartTimesForCreate(){
  const day = document.getElementById('day_pre')?.value || '';
  const url = day ? `/api/meta/start-times/?day=${encodeURIComponent(day)}` : null;
  if (!url) { document.getElementById('start_time_pre').innerHTML = '<option value="">เลือก</option>'; return; }
  await populateSelect(url, 'start_time_pre', t => ({ value: (t.value ?? t), label: (t.text ?? t) }));
  await loadStopTimesForCreate(); // รีโหลด stop ตาม start ใหม่
}
async function loadStopTimesForCreate(){
  const day   = document.getElementById('day_pre')?.value || '';
  const start = document.getElementById('start_time_pre')?.value || '';
  const url = (day && start) ? `/api/meta/stop-times/?day=${encodeURIComponent(day)}&start=${encodeURIComponent(start)}` : null;
  if (!url) { document.getElementById('stop_time_pre').innerHTML = '<option value="">เลือก</option>'; return; }
  await populateSelect(url, 'stop_time_pre', t => ({ value: (t.value ?? t), label: (t.text ?? t) }));
}

async function loadStartTimesForEdit(){
  const day = document.getElementById('editday_pre')?.value || '';
  const url = day ? `/api/meta/start-times/?day=${encodeURIComponent(day)}` : null;
  if (!url) { document.getElementById('editstart_time_pre').innerHTML = '<option value="">เลือก</option>'; return; }
  await populateSelect(url, 'editstart_time_pre', t => ({ value: (t.value ?? t), label: (t.text ?? t) }));
  await loadStopTimesForEdit();
}
async function loadStopTimesForEdit(){
  const day   = document.getElementById('editday_pre')?.value || '';
  const start = document.getElementById('editstart_time_pre')?.value || '';
  const url = (day && start) ? `/api/meta/stop-times/?day=${encodeURIComponent(day)}&start=${encodeURIComponent(start)}` : null;
  if (!url) { document.getElementById('editstop_time_pre').innerHTML = '<option value="">เลือก</option>'; return; }
  await populateSelect(url, 'editstop_time_pre', t => ({ value: (t.value ?? t), label: (t.text ?? t) }));
}
