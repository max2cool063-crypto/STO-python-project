(function(){
  const selectors=['#date-input','#block-date'];
  const MONTHS=['январь','февраль','март','апрель','май','июнь','июль','август','сентябрь','октябрь','ноябрь','декабрь'];
  const WEEKDAYS=['Пн','Вт','Ср','Чт','Пт','Сб','Вс'];
  const pad=n=>String(n).padStart(2,'0');
  const iso=d=>`${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
  const parse=value=>{
    if(!value)return null;
    const match=String(value).match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if(!match)return null;
    const y=Number(match[1]),m=Number(match[2]),d=Number(match[3]);
    const result=new Date(y,m-1,d,12,0,0,0);
    return Number.isNaN(result.getTime())?null:result;
  };
  const sameDay=(a,b)=>a&&b&&a.getFullYear()===b.getFullYear()&&a.getMonth()===b.getMonth()&&a.getDate()===b.getDate();
  const format=value=>{const d=parse(value);return d?`${pad(d.getDate())}.${pad(d.getMonth()+1)}.${d.getFullYear()}`:'Выберите дату'};

  function init(input){
    if(!input||input.dataset.stDatePickerReady==='1')return;
    input.dataset.stDatePickerReady='1';
    input.classList.add('st-date-picker__native');

    const today=new Date();today.setHours(12,0,0,0);
    let min=parse(input.min);
    if(!min){
      min=new Date(today);
      input.min=iso(min);
    }
    min.setHours(12,0,0,0);

    let selected=parse(input.value);
    let view=selected?new Date(selected):new Date(min);
    view=new Date(view.getFullYear(),view.getMonth(),1,12,0,0,0);

    const wrap=document.createElement('div');wrap.className='st-date-picker';
    input.parentNode.insertBefore(wrap,input);wrap.appendChild(input);

    const trigger=document.createElement('button');trigger.type='button';trigger.className='st-date-picker__trigger';trigger.setAttribute('aria-haspopup','dialog');trigger.setAttribute('aria-expanded','false');
    const label=document.createElement('span');label.textContent=format(input.value);
    const icon=document.createElement('span');icon.className='st-date-picker__trigger-icon';icon.innerHTML='<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 2v4M16 2v4M3 10h18"/><rect width="18" height="18" x="3" y="4" rx="2"/></svg>';
    trigger.append(label,icon);wrap.appendChild(trigger);

    const panel=document.createElement('div');panel.className='st-date-picker__panel';panel.hidden=true;panel.setAttribute('role','dialog');panel.setAttribute('aria-label','Выбор даты');
    panel.innerHTML='<div class="st-date-picker__head"><button type="button" class="st-date-picker__nav" data-prev aria-label="Предыдущий месяц">‹</button><div class="st-date-picker__month"></div><button type="button" class="st-date-picker__nav" data-next aria-label="Следующий месяц">›</button></div><div class="st-date-picker__weekdays"></div><div class="st-date-picker__grid"></div><div class="st-date-picker__footer"><button type="button" class="st-date-picker__today">Сегодня</button></div>';
    wrap.appendChild(panel);
    const monthLabel=panel.querySelector('.st-date-picker__month');
    const grid=panel.querySelector('.st-date-picker__grid');
    const weekdays=panel.querySelector('.st-date-picker__weekdays');
    WEEKDAYS.forEach(w=>{const e=document.createElement('div');e.className='st-date-picker__weekday';e.textContent=w;weekdays.appendChild(e)});
    const prev=panel.querySelector('[data-prev]'),next=panel.querySelector('[data-next]'),todayBtn=panel.querySelector('.st-date-picker__today');

    function render(){
      if(Number.isNaN(view.getTime()))view=new Date(min.getFullYear(),min.getMonth(),1,12,0,0,0);
      monthLabel.textContent=`${MONTHS[view.getMonth()]} ${view.getFullYear()} г.`;
      grid.innerHTML='';
      const first=new Date(view.getFullYear(),view.getMonth(),1,12);const firstWeekday=(first.getDay()+6)%7;
      const start=new Date(view.getFullYear(),view.getMonth(),1-firstWeekday,12);
      for(let i=0;i<42;i++){
        const d=new Date(start);d.setDate(start.getDate()+i);d.setHours(12,0,0,0);
        const btn=document.createElement('button');btn.type='button';btn.className='st-date-picker__day';btn.textContent=d.getDate();
        if(d.getMonth()!==view.getMonth())btn.classList.add('is-outside');
        if(d<min){btn.disabled=true;btn.classList.add('is-past');btn.setAttribute('aria-label',`${format(iso(d))}, недоступно: прошедшая дата`)}
        else{btn.setAttribute('aria-label',format(iso(d)));btn.addEventListener('click',()=>selectDate(d))}
        if(sameDay(d,today))btn.classList.add('is-today');
        if(sameDay(d,selected))btn.classList.add('is-selected');
        grid.appendChild(btn);
      }
      const prevMonthEnd=new Date(view.getFullYear(),view.getMonth(),0,12);
      prev.disabled=prevMonthEnd<min;
      todayBtn.disabled=today<min;
    }
    function selectDate(d){selected=new Date(d);input.value=iso(d);label.textContent=format(input.value);input.dispatchEvent(new Event('change',{bubbles:true}));close()}
    function open(){panel.hidden=false;trigger.setAttribute('aria-expanded','true');render()}
    function close(){panel.hidden=true;trigger.setAttribute('aria-expanded','false')}
    trigger.addEventListener('click',()=>panel.hidden?open():close());
    prev.addEventListener('click',()=>{view=new Date(view.getFullYear(),view.getMonth()-1,1,12);render()});
    next.addEventListener('click',()=>{view=new Date(view.getFullYear(),view.getMonth()+1,1,12);render()});
    todayBtn.addEventListener('click',()=>{if(today>=min){view=new Date(today.getFullYear(),today.getMonth(),1,12);selectDate(today)}});
    input.addEventListener('change',()=>{selected=parse(input.value);label.textContent=format(input.value);if(selected)view=new Date(selected.getFullYear(),selected.getMonth(),1,12)});
    document.addEventListener('click',e=>{if(!wrap.contains(e.target))close()});
    document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!panel.hidden){close();trigger.focus()}});
    render();
  }

  selectors.forEach(selector=>init(document.querySelector(selector)));
})();