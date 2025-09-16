// subject.js (REST + fetch + CSRF + inline edit/delete)
document.addEventListener('DOMContentLoaded', () => {
  // ---------- Config ----------
  const API_BASE = '/api/subjects/'; // ต้องมีใน urls.py เช่น path("api/subjects/", views.subject_api)
  const IDs = {
    form: 'subjectForm',
    code: 'subject_code',
    name: 'subject_name',
    tbody: 'subjectTableBody',
    btnCancel: 'btnCancelSubjectEdit',
    btnRefresh: 'btnRefreshSubject', // ถ้าใน HTML ใช้ btnRefreshTeacher ให้แก้เป็นชื่อนี้
    btnSubmit: 'btnAddSubject',
  };

  // ---------- Elements ----------
  const form = document.getElementById(IDs.form);
  const codeInput = document.getElementById(IDs.code);
  const nameInput = document.getElementById(IDs.name);
  const tbody = document.getElementById(IDs.tbody);
  const btnCancel = document.getElementById(IDs.btnCancel);
  const btnRefresh = document.getElementById(IDs.btnRefresh);
  const btnSubmit = document.getElementById(IDs.btnSubmit);

  // hidden state (id ที่กำลังแก้)
  let editingId = null;

  // ---------- Helpers ----------
  const getCSRFToken = () => {
    // อ่านจาก input hidden ที่ Django ใส่ให้ใน form
    const el = form.querySelector('input[name="csrfmiddlewaretoken"]');
    return el ? el.value : '';
  };

  const headersJSON = () => ({
    'Content-Type': 'application/json',
    'X-CSRFToken': getCSRFToken(),
    'Accept': 'application/json',
  });

  const setLoading = (isLoading) => {
    if (!btnSubmit) return;
    btnSubmit.disabled = isLoading;
    btnSubmit.querySelector('span')?.classList?.toggle('d-none', isLoading);
    // เพิ่ม/ถอด spinner แบบเบาๆ
    let spinner = btnSubmit.querySelector('.spinner-border');
    if (isLoading) {
      if (!spinner) {
        spinner = document.createElement('span');
        spinner.className = 'spinner-border spinner-border-sm ms-2';
        spinner.setAttribute('role', 'status');
        spinner.setAttribute('aria-hidden', 'true');
        btnSubmit.appendChild(spinner);
      }
    } else if (spinner) {
      spinner.remove();
    }
  };

  const toast = (msg) => {
    // ใช้ alert แบบง่าย ๆ เพื่อไม่ผูกกับ UI Framework
    console.log(msg);
  };

  const clearForm = () => {
    form.reset();
    editingId = null;
    btnCancel?.classList.add('d-none');
    // คืนข้อความปุ่ม
    if (btnSubmit) {
      btnSubmit.innerHTML = `<i class="bi bi-plus-lg me-2"></i><span>เพิ่มข้อมูล</span>`;
      btnSubmit.disabled = false;
    }
  };

  const fillFormForEdit = (row) => {
    codeInput.value = row.dataset.code || '';
    nameInput.value = row.dataset.name || '';
    editingId = row.dataset.id || null;
    btnCancel?.classList.remove('d-none');
    if (btnSubmit) {
      btnSubmit.innerHTML = `<i class="bi bi-save me-2"></i><span>บันทึกการแก้ไข</span>`;
    }
  };

  const rowHTML = ({ id, code, name }) => `
    <tr data-id="${id}" data-code="${escapeHtml(code)}" data-name="${escapeHtml(name)}">
      <td class="fw-semibold">${escapeHtml(code)}</td>
      <td>${escapeHtml(name)}</td>
      <td class="text-nowrap">
        <button type="button" class="btn btn-outline-primary btn-sm me-1 btn-edit">
          <i class="bi bi-pencil-square me-1"></i>แก้ไข
        </button>
        <button type="button" class="btn btn-outline-danger btn-sm btn-delete">
          <i class="bi bi-trash me-1"></i>ลบ
        </button>
      </td>
    </tr>
  `;

  const escapeHtml = (s) =>
    String(s ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');

  // ---------- CRUD ----------
  const listSubjects = async () => {
    const res = await fetch(API_BASE, { method: 'GET', headers: { 'Accept': 'application/json' }});
    if (!res.ok) throw new Error(`โหลดข้อมูลไม่สำเร็จ (${res.status})`);
    return await res.json(); // ต้องเป็น list ของ {id, code, name}
  };

  const createSubject = async (payload) => {
    const res = await fetch(API_BASE, {
      method: 'POST',
      headers: headersJSON(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const msg = await parseErr(res);
      throw new Error(msg || `เพิ่มข้อมูลไม่สำเร็จ (${res.status})`);
    }
    return await res.json();
  };

  const updateSubject = async (id, payload) => {
    // ต้องมี route PUT /api/subjects/<id>/ ฝั่ง Django
    const res = await fetch(`${API_BASE}${id}/`, {
      method: 'PUT',
      headers: headersJSON(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const msg = await parseErr(res);
      throw new Error(msg || `แก้ไขข้อมูลไม่สำเร็จ (${res.status})`);
    }
    return await res.json();
  };

  const deleteSubject = async (id) => {
    // ต้องมี route DELETE /api/subjects/<id>/ ฝั่ง Django
    const res = await fetch(`${API_BASE}${id}/`, {
      method: 'DELETE',
      headers: { 'X-CSRFToken': getCSRFToken() },
    });
    if (!res.ok) {
      const msg = await parseErr(res);
      throw new Error(msg || `ลบข้อมูลไม่สำเร็จ (${res.status})`);
    }
    // บาง backend อาจไม่ส่ง body กลับ
    return true;
  };

  const parseErr = async (res) => {
    try {
      const data = await res.json();
      if (data && (data.detail || data.error || data.message)) {
        return data.detail || data.error || data.message;
      }
      return '';
    } catch {
      return '';
    }
  };

  // ---------- Render ----------
  const renderTable = (items = []) => {
    if (!tbody) return;
    if (!Array.isArray(items) || items.length === 0) {
      tbody.innerHTML = `
        <tr class="empty-row">
          <td colspan="3" class="text-center text-muted">ไม่มีข้อมูลรายวิชา</td>
        </tr>`;
      return;
    }
    tbody.innerHTML = items
      .map(({ id, code, name }) => rowHTML({ id, code, name }))
      .join('');
  };

  const refresh = async () => {
    try {
      btnRefresh && (btnRefresh.disabled = true);
      const items = await listSubjects();
      renderTable(items);
    } catch (err) {
      alert(err.message || 'เกิดข้อผิดพลาดในการโหลดข้อมูล');
    } finally {
      btnRefresh && (btnRefresh.disabled = false);
    }
  };

  // ---------- Events ----------
  // โหลดครั้งแรก
  refresh();

  // กดรีเฟรช
  btnRefresh?.addEventListener('click', refresh);

  // ส่งฟอร์ม (create/update)
  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const code = codeInput.value.trim();
    const name = nameInput.value.trim();

    if (!code || !name) {
      alert('กรุณากรอก "รหัสวิชา" และ "ชื่อรายวิชา" ให้ครบ');
      return;
    }

    const payload = { code, name };

    try {
      setLoading(true);
      if (editingId) {
        await updateSubject(editingId, payload);
        toast('แก้ไขข้อมูลสำเร็จ');
      } else {
        await createSubject(payload);
        toast('เพิ่มข้อมูลสำเร็จ');
      }
      clearForm();
      await refresh();
    } catch (err) {
      alert(err.message || 'เกิดข้อผิดพลาดในการบันทึก');
    } finally {
      setLoading(false);
    }
  });

  // ยกเลิกโหมดแก้ไข
  btnCancel?.addEventListener('click', clearForm);

  // แก้ไข/ลบ จากตาราง (event delegation)
  tbody?.addEventListener('click', async (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;

    const row = e.target.closest('tr');
    const id = row?.dataset?.id;

    if (btn.classList.contains('btn-edit')) {
      fillFormForEdit(row);
      codeInput.focus();
      return;
    }

    if (btn.classList.contains('btn-delete')) {
      if (!id) return;
      if (!confirm('ยืนยันการลบรายวิชานี้?')) return;
      try {
        await deleteSubject(id);
        toast('ลบข้อมูลสำเร็จ');
        // ถ้าเป็นแถวที่กำลังแก้ ให้เคลียร์ฟอร์มด้วย
        if (editingId === id) clearForm();
        await refresh();
      } catch (err) {
        alert(err.message || 'เกิดข้อผิดพลาดในการลบ');
      }
    }
  });
});
