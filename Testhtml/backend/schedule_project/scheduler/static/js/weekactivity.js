/* ---------- State ---------- */
let editRow = null;
let editId = null;

/* ---------- Utilities ---------- */
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

async function fetchJSON(url) {
  const res = await fetch(url, { headers: { 'X-CSRFToken': getCookie('csrftoken') } });
  if (!res.ok) throw new Error('Network error');
  return res.json();
}

function setSelectBusy(selectEl, text = 'กำลังโหลด…') {
  selectEl.innerHTML = `<option selected hidden value="">${text}</option>`;
  selectEl.disabled = true;
}

function populateSelect(selectEl, items, { placeholder = 'เลือก', selected = '' } = {}) {

  const opts = (Array.isArray(items) ? items : []).map(it => {
    if (typeof it === 'string') return { value: it, text: it };
    if (it && typeof it === 'object') {
      const value = it.value ?? it.val ?? it.code ?? '';
      const text  = it.text  ?? it.label ?? value ?? '';
      return { value, text };
    }
    const v = String(it ?? '');
    return { value: v, text: v };
  });

  const html = ['<option value="">' + placeholder + '</option>']
    .concat(opts.map(o => `<option value="${o.value}">${o.text}</option>`))
    .join('');
  selectEl.innerHTML = html;
  selectEl.disabled = false;

  if (selected) {
    const hit = opts.find(o => o.value === selected || o.text === selected);
    if (hit) selectEl.value = hit.value;
  }
}

/* ---------- Notifications ---------- */
function showNotification(message, type = 'info', duration = 4000) {
  const container = document.getElementById('notificationContainer');
  const n = document.createElement('div');
  const typeMap = { success:'success', error:'error', warning:'warning', info:'info', debug:'info' };
  n.className = `notification ${typeMap[type] || 'info'}`;
  n.innerHTML = `
    <button class="notification-close" onclick="closeNotification(this)">&times;</button>
    <div>${message}</div>
    <div class="notification-progress"></div>
  `;
  container.appendChild(n);
  setTimeout(() => n.classList.add('show'), 50);
  const bar = n.querySelector('.notification-progress');
  bar.style.width = '100%';
  setTimeout(() => { bar.style.transitionDuration = duration + 'ms'; bar.style.width = '0%'; }, 80);
  setTimeout(() => closeNotification(n.querySelector('.notification-close')), duration + 120);
}
function closeNotification(btn){ const n = btn.parentElement; n.style.opacity='0'; n.style.transform='translateX(100%)'; setTimeout(()=>n.remove(),300); }

/* ---------- Meta loaders (Days / Start / Stop) ---------- */
// สำหรับฟอร์มหลัก
async function loadDaysForCreate() {
  const root = document.getElementById('activity-form');
  const daySel = document.getElementById('day_activity');
  const startSel = document.getElementById('start_time_activity');
  const stopSel = document.getElementById('stop_time_activity');

  setSelectBusy(daySel);
  setSelectBusy(startSel, 'เลือกวันก่อน');
  setSelectBusy(stopSel, 'เลือกเวลาเริ่มก่อน');

  try {
    const { days } = await fetchJSON(root.dataset.endpointDays);
    populateSelect(daySel, days, { placeholder: 'เลือกวัน' });
  } catch {
    daySel.innerHTML = `<option value="">โหลดวันไม่สำเร็จ</option>`;
    showNotification('โหลดรายการวันไม่สำเร็จ', 'error');
  }

  daySel.addEventListener('change', async () => {
    const day = daySel.value;
    setSelectBusy(startSel);
    setSelectBusy(stopSel, 'เลือกเวลาเริ่มก่อน');
    if (!day) return;

    try {
      const { start_times } = await fetchJSON(root.dataset.endpointStart + encodeURIComponent(day));
      populateSelect(startSel, start_times, { placeholder: 'เลือกเวลาเริ่ม' });
    } catch {
      populateSelect(startSel, [], { placeholder: 'ไม่มีข้อมูลเวลาเริ่ม' });
      showNotification('โหลดเวลาเริ่มไม่สำเร็จ', 'error');
    }
  });

  startSel.addEventListener('change', async () => {
    const day = daySel.value;
    const start = startSel.value;
    setSelectBusy(stopSel);
    if (!day || !start) { setSelectBusy(stopSel, 'เลือกเวลาเริ่มก่อน'); return; }

    try {
      const url = root.dataset.endpointStop
        .replace('{day}', encodeURIComponent(day))
        .replace('{start}', encodeURIComponent(start));
      const { stop_times } = await fetchJSON(url);
      populateSelect(stopSel, stop_times, { placeholder: 'เลือกเวลาสิ้นสุด' });
    } catch {
      populateSelect(stopSel, [], { placeholder: 'ไม่มีข้อมูลเวลาสิ้นสุด' });
      showNotification('โหลดเวลาสิ้นสุดไม่สำเร็จ', 'error');
    }
  });
}

// สำหรับ Modal แก้ไข
async function loadDaysForEdit(prefill) {
  const root = document.getElementById('activity-edit');
  const daySel = document.getElementById('edit_day_activity');
  const startSel = document.getElementById('edit_start_time_activity');
  const stopSel = document.getElementById('edit_stop_time_activity');

  setSelectBusy(daySel);
  setSelectBusy(startSel, 'เลือกวันก่อน');
  setSelectBusy(stopSel, 'เลือกเวลาเริ่มก่อน');

  try {
    const { days } = await fetchJSON(root.dataset.endpointDays);
    populateSelect(daySel, days, { placeholder: 'เลือกวัน', selected: prefill.day });
  } catch {
    daySel.innerHTML = `<option value="">โหลดวันไม่สำเร็จ</option>`;
  }

  // โหลด start ตามวัน (ใช้ค่า prefill.start ถ้ามี)
  if (daySel.value) {
    try {
      const { start_times } = await fetchJSON(root.dataset.endpointStart + encodeURIComponent(daySel.value));
      populateSelect(startSel, start_times, { placeholder: 'เลือกเวลาเริ่ม', selected: prefill.start });
    } catch {
      populateSelect(startSel, [], { placeholder: 'ไม่มีข้อมูลเวลาเริ่ม' });
    }
  }

  // โหลด stop ตามวัน+start (ใช้ค่า prefill.stop ถ้ามี)
  if (daySel.value && startSel.value) {
    try {
      const url = root.dataset.endpointStop
        .replace('{day}', encodeURIComponent(daySel.value))
        .replace('{start}', encodeURIComponent(startSel.value));
      const { stop_times } = await fetchJSON(url);
      populateSelect(stopSel, stop_times, { placeholder: 'เลือกเวลาสิ้นสุด', selected: prefill.stop });
    } catch {
      populateSelect(stopSel, [], { placeholder: 'ไม่มีข้อมูลเวลาสิ้นสุด' });
    }
  }

  // รีแคสเคดเมื่อมีการเปลี่ยนใน modal
  daySel.onchange = async () => {
    const day = daySel.value;
    setSelectBusy(startSel);
    setSelectBusy(stopSel, 'เลือกเวลาเริ่มก่อน');
    if (!day) return;
    try {
      const { start_times } = await fetchJSON(root.dataset.endpointStart + encodeURIComponent(day));
      populateSelect(startSel, start_times, { placeholder: 'เลือกเวลาเริ่ม' });
    } catch {
      populateSelect(startSel, [], { placeholder: 'ไม่มีข้อมูลเวลาเริ่ม' });
    }
  };

  startSel.onchange = async () => {
    const day = daySel.value;
    const start = startSel.value;
    setSelectBusy(stopSel);
    if (!day || !start) { setSelectBusy(stopSel, 'เลือกเวลาเริ่มก่อน'); return; }
    try {
      const url = root.dataset.endpointStop
        .replace('{day}', encodeURIComponent(day))
        .replace('{start}', encodeURIComponent(start));
      const { stop_times } = await fetchJSON(url);
      populateSelect(stopSel, stop_times, { placeholder: 'เลือกเวลาสิ้นสุด' });
    } catch {
      populateSelect(stopSel, [], { placeholder: 'ไม่มีข้อมูลเวลาสิ้นสุด' });
    }
  };
}

/* ---------- CRUD ---------- */
function addActivity() {
  const act_name_activity      = document.getElementById("act_name_activity").value.trim();
  const day_activity           = document.getElementById("day_activity").value;
  const start_time_activity    = document.getElementById("start_time_activity").value;
  const stop_time_activity     = document.getElementById("stop_time_activity").value;

  // ตรวจสอบ: ชื่อกิจกรรมเป็น “ข้อความ” (string) — อินพุตนี้รองรับข้อความอยู่แล้ว
  if (!act_name_activity) return showNotification("กรุณากรอกชื่อกิจกรรม", "warning");
  if (!day_activity) return showNotification("กรุณาเลือกวัน", "warning");
  if (!start_time_activity) return showNotification("กรุณาเลือกเวลาเริ่ม", "warning");
  if (!stop_time_activity) return showNotification("กรุณาเลือกเวลาสิ้นสุด", "warning");

  fetch('/api/activity/add/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
    body: JSON.stringify({
      act_name_activity,                   // <-- เก็บเป็น “ข้อความ”
      day_activity,
      start_time_activity,
      stop_time_activity
    })
  })
  .then(r => r.json())
  .then(data => {
    if (data.status === 'success') {
      showNotification("✅ เพิ่มกิจกรรมเรียบร้อยแล้ว", 'success');
      location.reload();
    } else {
      showNotification('เกิดข้อผิดพลาด: ' + (data.message || ''), 'error');
    }
  })
  .catch(() => showNotification('เกิดข้อผิดพลาดในการเพิ่มข้อมูล', 'error'));
}

function confirmDelete(button) {
  if (!confirm("คุณแน่ใจหรือไม่ว่าต้องการลบรายการนี้?")) return;
  const row = button.closest("tr");
  const id = row.getAttribute("data-id");

  fetch(`/api/activity/delete/${id}/`, {
    method: 'DELETE',
    headers: { 'X-CSRFToken': getCookie('csrftoken') }
  })
  .then(r => r.json())
  .then(data => {
    if (data.status === 'success') {
      row.remove();
      showNotification("✅ ลบข้อมูลเรียบร้อยแล้ว", 'success');
    } else {
      showNotification('เกิดข้อผิดพลาดในการลบข้อมูล', 'error');
    }
  })
  .catch(() => showNotification('เกิดข้อผิดพลาดในการลบข้อมูล', 'error'));
}

function openEditModal(button) {
  const row = button.closest("tr");
  editRow = row;
  editId = row.getAttribute("data-id");

  const cells = row.getElementsByTagName("td");
  const prefill = {
    name: cells[0].innerText.trim(),
    day:  cells[1].querySelector('.badge').innerText.trim(),
    start: cells[2].querySelector('.badge').innerText.trim(),
    stop:  cells[3].querySelector('.badge').innerText.trim(),
  };

  document.getElementById("edit_act_name_activity").value = prefill.name;

  // โหลด dropdown ของ modal ตามค่าที่แถวปัจจุบันถืออยู่
  loadDaysForEdit({ day: prefill.day, start: prefill.start, stop: prefill.stop });

  new bootstrap.Modal(document.getElementById("editModal")).show();
}

function saveEdit() {
  const act_name_activity = document.getElementById("edit_act_name_activity").value.trim(); 
  const day_activity = document.getElementById("edit_day_activity").value;
  const start_time_activity = document.getElementById("edit_start_time_activity").value;
  const stop_time_activity = document.getElementById("edit_stop_time_activity").value;

  if (!act_name_activity || !day_activity || !start_time_activity || !stop_time_activity) {
    return showNotification("กรุณากรอกข้อมูลให้ครบถ้วน", 'warning');
  }

  fetch(`/api/activity/update/${editId}/`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
    body: JSON.stringify({
      act_name_activity, day_activity, start_time_activity, stop_time_activity
    })
  })
  .then(r => r.json())
  .then(data => {
    if (data.status === 'success') {
      showNotification("✅ แก้ไขข้อมูลเรียบร้อยแล้ว", 'success');
      bootstrap.Modal.getInstance(document.getElementById("editModal")).hide();
      location.reload();
    } else {
      showNotification('เกิดข้อผิดพลาดในการแก้ไขข้อมูล', 'error');
    }
  })
  .catch(() => showNotification('เกิดข้อผิดพลาดในการแก้ไขข้อมูล', 'error'));
}

function refreshData() { location.reload(); }

/* ---------- Init ---------- */
window.addEventListener('load', () => {
  showNotification("ยินดีต้อนรับสู่หน้าจัดการกิจกรรม", 'info');
  loadDaysForCreate(); // โหลด dropdown สำหรับฟอร์มสร้างใหม่

  // Django messages (ถ้ามี)
  if (Array.isArray(window.__DJANGO_MESSAGES__)) {
    window.__DJANGO_MESSAGES__.forEach(m => showNotification(m.text, m.level || 'info'));
  }
});
