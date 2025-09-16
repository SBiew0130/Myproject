(function(){
  function byId(id){ return document.getElementById(id); }

  function makeController(cfg){
    const state = { data: [], editIndex: -1 };

    function getFieldEls(){ return cfg.fields.map(f => ({...f, el: byId(f.id)})); }

    function setAddBtnText(text){
      const addBtn = byId(cfg.addBtnId);
      if (!addBtn) return;
      const span = addBtn.querySelector('span');
      if (span) span.textContent = text; else addBtn.textContent = text;
    }

    function resetForm(){
      byId(cfg.formId)?.reset?.();
      state.editIndex = -1;
      byId(cfg.cancelBtnId)?.classList.add('d-none');
      setAddBtnText('เพิ่มข้อมูล');
    }

    function validateAndCollect(){
      const values = {};
      for (const f of getFieldEls()){
        let val = f.el.value;
        if (typeof val === 'string') val = val.trim();
        if (f.required && (!val || val === f.requiredInvalidValue)) {
          alert('กรอก/เลือก ' + (f.label || f.id) + ' ให้ครบ');
          return null;
        }
        values[f.key] = val;
      }
      return values;
    }

    async function reloadFromRemote(){
      if (!cfg.remote || !cfg.remote.load) return;
      const list = await cfg.remote.load();
      state.data = Array.isArray(list) ? list : [];
      render();
    }

    function render(){
      const tbody = byId(cfg.tableBodyId); if (!tbody) return;
      tbody.innerHTML = '';
      if (state.data.length === 0){
        const colspan = cfg.fields.length + 1;
        tbody.innerHTML = `<tr class="empty-row"><td colspan="${colspan}" class="text-center text-muted">ไม่มีข้อมูล</td></tr>`;
        return;
      }
      state.data.forEach((row, i) => {
        const cols = cfg.fields.map(f => `<td>${row[f.key] ?? ''}</td>`).join('');
        tbody.insertAdjacentHTML('beforeend',
          `<tr>${cols}<td>
             <div class="btn-group btn-group-sm">
               <button class="btn btn-outline-secondary" data-act="edit" data-i="${i}">
                 <i class="bi bi-pencil"></i>
               </button>
               <button class="btn btn-outline-danger" data-act="remove" data-i="${i}">
                 <i class="bi bi-trash"></i>
               </button>
             </div>
           </td></tr>`);
      });
      tbody.querySelectorAll('button[data-act]').forEach(btn => {
        btn.onclick = () => {
          const i = parseInt(btn.getAttribute('data-i'));
          const act = btn.getAttribute('data-act');
          if (act === 'edit') startEdit(i);
          if (act === 'remove') remove(i);
        };
      });
    }

    function startEdit(i){
      const row = state.data[i];
      for (const f of getFieldEls()){ f.el.value = row[f.key] ?? ''; }
      state.editIndex = i;
      setAddBtnText('บันทึกการแก้ไข');
      byId(cfg.cancelBtnId)?.classList.remove('d-none');
    }

    async function remove(i){
      const row = state.data[i];
      if (cfg.remote && cfg.remote.remove && row && row.id != null){
        await cfg.remote.remove(row.id);
        await reloadFromRemote();
      } else {
        state.data.splice(i,1);
        if (state.editIndex === i) resetForm();
        render();
      }
    }

    // Events
    byId(cfg.addBtnId)?.addEventListener('click', async () => {
      const values = validateAndCollect(); if (!values) return;
      if (cfg.remote && cfg.remote.create){
        await cfg.remote.create(values);
        await reloadFromRemote();
      } else {
        if (state.editIndex === -1) state.data.push(values);
        else state.data[state.editIndex] = values;
        render();
      }
      resetForm();
    });
    byId(cfg.cancelBtnId)?.addEventListener('click', resetForm);
    byId(cfg.refreshBtnId)?.addEventListener('click', async () => {
      if (cfg.remote && cfg.remote.load) await reloadFromRemote();
      else render();
    });

    // Initial
    render();
    reloadFromRemote();

    // expose (เผื่ออยากใช้จาก console)
    return { state, render, resetForm };
  }

  // export to window
  window.makeController = makeController;
})();
