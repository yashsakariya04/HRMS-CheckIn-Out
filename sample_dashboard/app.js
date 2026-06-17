// Simple in-browser session store for check-in/out sample dashboard
const STORAGE_KEY = 'sample_sessions_v1';

function nowISO(){ return new Date().toISOString(); }
function formatTime(iso){ const d=new Date(iso); return d.toLocaleString(); }

function loadSessions(){ try{ return JSON.parse(localStorage.getItem(STORAGE_KEY)||'[]'); }catch(e){ return []; } }
function saveSessions(s){ localStorage.setItem(STORAGE_KEY, JSON.stringify(s)); }

function renderSessions(){ const tbody=document.querySelector('#sessions-table tbody'); tbody.innerHTML='';
  const sessions=loadSessions();
  sessions.forEach((s,i)=>{
    const tr=document.createElement('tr');
    const duration = s.checkout ? msToHuman(new Date(s.checkout)-new Date(s.checkin)) : '-';
    tr.innerHTML = `<td>${i+1}</td><td>${formatTime(s.checkin)}</td><td>${s.checkout?formatTime(s.checkout):'-'}</td><td>${duration}</td>`;
    tbody.appendChild(tr);
  });
  updateStatus();
}

function msToHuman(ms){ if(ms<=0) return '0s'; const s=Math.floor(ms/1000); const h=Math.floor(s/3600); const m=Math.floor((s%3600)/60); const ss=s%60; return `${h?h+'h ':''}${m?m+'m ':''}${ss}s`; }

function updateStatus(){ const sessions=loadSessions(); const last=sessions[sessions.length-1]; const statusEl=document.getElementById('current-status'); const checkoutBtn=document.getElementById('checkout-btn');
  if(last && !last.checkout){ statusEl.textContent = `Checked in at ${formatTime(last.checkin)}`; checkoutBtn.disabled=false; document.getElementById('checkin-btn').disabled=true; }
  else { statusEl.textContent = 'Not checked in'; checkoutBtn.disabled=true; document.getElementById('checkin-btn').disabled=false; }
}

function checkIn(){ const sessions=loadSessions(); sessions.push({ checkin: nowISO(), checkout: null }); saveSessions(sessions); renderSessions(); }
function checkOut(){ const sessions=loadSessions(); if(!sessions.length) return; const last=sessions[sessions.length-1]; if(last.checkout) return; last.checkout = nowISO(); saveSessions(sessions); renderSessions(); }
function clearAll(){ if(!confirm('Clear all sample sessions?')) return; localStorage.removeItem(STORAGE_KEY); renderSessions(); }

document.addEventListener('DOMContentLoaded', ()=>{
  document.getElementById('checkin-btn').addEventListener('click', checkIn);
  document.getElementById('checkout-btn').addEventListener('click', checkOut);
  document.getElementById('clear-btn').addEventListener('click', clearAll);
  renderSessions();
});
