document.addEventListener('DOMContentLoaded', () => {
  // ---- helpers fetch + CSRF ----
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

  // ---- hook เข้า controller ----
  window.groupAllowController = makeController({
    key:'groupallow',
    formId:'groupAllowForm',
    fields:[
      {id:'ga_dept_id', key:'dept', label:'รหัสภาค', required:true},
      {id:'ga_slot_id', key:'slot', label:'รหัสคาบ', required:true},
    ],
    tableBodyId:'groupAllowTableBody',
    addBtnId:'btnAddGroupAllow',
    cancelBtnId:'btnCancelGroupAllowEdit',
    refreshBtnId:'btnRefreshGroupAllow',

    // ใช้แบ็กเอนด์จริง
    remote: {
      async load(){
        const { items } = await apiGet('/api/groupallow/list/');
        return items; // [{id, dept, slot, dept_name?, slot_text?}, ...]
      },
      async create(values){
        // ถ้าอยู่โหมดแก้ไข: ลบของเดิมก่อนแล้วค่อยเพิ่ม (GroupAllow ใช้คู่ค่า unique)
        const idx = groupAllowController.state.editIndex;
        if (idx >= 0){
          const row = groupAllowController.state.data[idx];
          if (row && row.id != null){
            await apiDelete(`/api/groupallow/delete/${row.id}/`);
          }
        }
        await apiPost('/api/groupallow/add/', values);
      },
      async remove(id){
        await apiDelete(`/api/groupallow/delete/${id}/`);
      }
    }
  });
});
