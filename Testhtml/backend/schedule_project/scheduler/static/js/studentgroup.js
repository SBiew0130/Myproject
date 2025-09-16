// /static/js/studentgroup.js
document.addEventListener('DOMContentLoaded', () => {
  // ---- CSRF + fetch helpers ----
  const csrftoken = (() => {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  })();

  async function apiGet(url){
    const r = await fetch(url);
    const j = await r.json();
    if (!r.ok || j.status !== 'success') throw new Error(j.message || `HTTP ${r.status}`);
    return j;
  }
  async function apiPost(url, payload){
    const r = await fetch(url, {
      method: 'POST',
      headers: {'Content-Type':'application/json','X-CSRFToken': csrftoken},
      body: JSON.stringify(payload)
    });
    const j = await r.json();
    if (!r.ok || j.status !== 'success') throw new Error(j.message || `HTTP ${r.status}`);
    return j;
  }
  async function apiDelete(url){
    const r = await fetch(url, { method: 'DELETE', headers: {'X-CSRFToken': csrftoken} });
    const j = await r.json();
    if (!r.ok || j.status !== 'success') throw new Error(j.message || `HTTP ${r.status}`);
    return j;
  }

  window.studentGroupController = makeController({
    key:'studentgroup',
    formId:'studentGroupForm',
    fields:[
      {id:'group_id',   key:'id',   label:'รหัสกลุ่มนักศึกษา', required:true},
      {id:'group_name', key:'name', label:'ชื่อกลุ่มนักศึกษา', required:true},
      {id:'group_type', key:'type', label:'ประเภทนักศึกษา', required:true, requiredInvalidValue:'เลือกประเภท'},
    ],
    tableBodyId:'studentGroupTableBody',
    addBtnId:'btnAddStudentGroup',
    cancelBtnId:'btnCancelStudentGroupEdit',
    refreshBtnId:'btnRefreshStudentGroup',

    remote: {
      async load(){
        const { items } = await apiGet('/api/studentgroup/list/');
        return items; // [{id, name, type, type_name}, ...]
      },
      async create(values){
        const payload = {
          id:   Number(values.id),                          // ตามฟอร์มที่ required id
          name: String(values.name || '').trim(),
          type: Number(values.type),
        };
        await apiPost('/api/studentgroup/add/', payload);   // upsert ตาม id
      },
      async remove(id){
        await apiDelete(`/api/studentgroup/delete/${id}/`);
      }
    }
  });
});
