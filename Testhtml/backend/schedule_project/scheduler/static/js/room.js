// /static/js/room.js
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

  window.roomController = makeController({
    key:'room',
    formId:'roomForm',
    fields:[
      {id:'room_id',   key:'id',   label:'รหัสห้อง',    required:false},
      {id:'room_name', key:'name', label:'ชื่อห้องเรียน', required:true},
      {id:'room_type', key:'type', label:'ประเภทห้อง',  required:true, requiredInvalidValue:'เลือกประเภท'},
    ],
    tableBodyId:'roomTableBody',
    addBtnId:'btnAddRoom',
    cancelBtnId:'btnCancelRoomEdit',
    refreshBtnId:'btnRefreshRoom',

    remote: {
      async load(){
        const { items } = await apiGet('/api/room/list/');
        return items; // [{id, name, type, type_name}, ...]
      },
      async create(values){
        const payload = {
          name: String(values.name || '').trim(),
          type: Number(values.type),
        };
        // ส่ง id เฉพาะเมื่อกรอก (รองรับ upsert ด้วย PK)
        if (String(values.id || '').trim() !== '') {
          payload.id = Number(values.id);
        }
        await apiPost('/api/room/add/', payload);
      },
      async remove(id){
        await apiDelete(`/api/room/delete/${id}/`);
      }
    }
  });
});
