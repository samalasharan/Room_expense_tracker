// =============================
// Helper API function
// =============================
async function api(path, opts={}) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    const t = await res.text();
    console.error("API error", res.status, t);
    return null;
  }
  return res.json();
}

// =============================
// On Page Load
// =============================
document.addEventListener('DOMContentLoaded', ()=> {
  const dEl = document.getElementById('date'); 
  if(dEl) dEl.value = new Date().toISOString().slice(0,10);
  const tEl = document.getElementById('time'); 
  if(tEl) tEl.value = new Date().toTimeString().slice(0,5);

  loadBudget();
  loadExpenses();

  const saveBudgetBtn = document.getElementById('saveBudgetBtn');
  if(saveBudgetBtn) saveBudgetBtn.addEventListener('click', saveBudget);

  const addBtn = document.getElementById('addBtn');
  if(addBtn) addBtn.addEventListener('click', addExpense);

  const downloadBtns = document.querySelectorAll('.downloadBtn');
  downloadBtns.forEach(btn => btn.addEventListener('click', () => download(btn.dataset.period)));
});

// =============================
// Save Budget
// =============================
async function saveBudget(){
  const val = parseFloat(document.getElementById('budgetInput').value || 0);
  const res = await api('/api/budget', { 
    method:'POST', 
    headers:{'Content-Type':'application/json'}, 
    body: JSON.stringify({amount: val})
  });
  if(res) {
    alert('Budget saved');
    loadBudget();
    loadExpenses();
  }
}

// =============================
// Load Budget
// =============================
async function loadBudget(){
  const res = await api('/api/budget');
  const budgetEl = document.getElementById('budgetDisplay');
  const remainingEl = document.getElementById('remainingDisplay');
  if(res && budgetEl && remainingEl){
    const budget = res.amount || 0;
    budgetEl.innerText = `₹${budget}`;

    // Calculate remaining from total expenses
    const expRes = await api('/api/expenses');
    const total = expRes?.total || 0;
    const remaining = budget - total;
    remainingEl.innerText = `₹${remaining >=0 ? remaining : 0}`;
  }
}

// =============================
// Add Expense
// =============================
async function addExpense(){
  const item = document.getElementById('item').value;
  const amount = parseFloat(document.getElementById('amount').value);
  const category = document.getElementById('category').value;
  const date = document.getElementById('date').value;
  const time = document.getElementById('time').value;
  const splitsText = document.getElementById('splits').value.trim();
  const participantsText = document.getElementById('participants').value.trim();

  let payload = { item, amount, category, date, time };

  if(splitsText){
    try{ payload.splits = JSON.parse(splitsText); } 
    catch(e){ alert('Invalid splits JSON'); return; }
  } else if(participantsText){
    payload.participants = participantsText.split(',').map(s=>parseInt(s.trim())).filter(Boolean);
  }

  const res = await api('/api/expense', { 
    method:'POST', 
    headers:{'Content-Type':'application/json'}, 
    body: JSON.stringify(payload)
  });

  if(res) { 
    alert('Expense added'); 
    document.getElementById('expense-form').reset();
    loadExpenses();
    loadBudget(); // refresh remaining
  }
}

// =============================
// Load Expenses
// =============================
async function loadExpenses(){
  const res = await api('/api/expenses');
  if(!res) return;

  const tbody = document.querySelector('#table tbody');
  tbody.innerHTML = '';

  res.expenses.forEach(e=>{
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${e.item}</td>
      <td>₹${e.amount}</td>
      <td>${e.payer_name}</td>
      <td>${e.date}</td>
      <td>${e.time}</td>
      <td>${(e.shares||[]).map(s=>s.display_name+'('+s.share_amount+')').join('; ')}</td>
    `;
    tbody.appendChild(tr);
  });

  const totalEl = document.getElementById('totalSpent'); 
  if(totalEl) totalEl.innerText = `₹${res.total || 0}`;
}

// =============================
// Download Report
// =============================
function download(period){
  window.location.href = `/api/report/${period}`;
}
