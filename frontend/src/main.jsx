import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API = import.meta.env.VITE_API_URL || "";
const EMPTY_FORM = {
  title: "", description: "", priority: "medium", due_date: "",
  category: "", estimated_minutes: "", goal_id: "",
  milestone_id: "",
};

async function request(path, options = {}) {
  const token = localStorage.getItem("task_token");
  let response;
  try {
    response = await fetch(`${API}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers || {}),
      },
    });
  } catch {
    throw new Error("Cannot reach the backend. Start FastAPI on port 8000.");
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail;
    throw new Error(Array.isArray(detail) ? detail.map((item) => item.msg).join(", ") : detail || `Request failed (${response.status})`);
  }
  return body;
}

function Logo() {
  return <div className="brand"><div className="brand-mark">✦</div><div><strong>Taskwise</strong><span>AI productivity</span></div></div>;
}

function Auth({ onLogin }) {
  const [register, setRegister] = useState(false);
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  async function submit(event) {
    event.preventDefault();
    setError("");
    try {
      const data = await request(`/api/auth/${register ? "register" : "login"}`, { method: "POST", body: JSON.stringify(form) });
      localStorage.setItem("task_token", data.access_token);
      onLogin(data.user);
    } catch (err) { setError(err.message); }
  }
  return (
    <main className="auth-page">
      <div className="auth-decoration"><span>✦</span><span>◌</span><span>✧</span></div>
      <form className="auth-card" onSubmit={submit}>
        <Logo />
        <div className="auth-heading"><p className="eyebrow">YOUR FOCUS, ELEVATED</p><h1>{register ? "Create your account" : "Welcome back"}</h1><p>One calm space for your tasks, plans, and momentum.</p></div>
        <label>Email<input required type="email" placeholder="you@example.com" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
        <label>Password<input required minLength="8" type="password" placeholder="At least 8 characters" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>
        {error && <p className="error">{error}</p>}
        <button className="button button-primary" type="submit">{register ? "Create account" : "Sign in"} <span>→</span></button>
        <button className="button button-ghost" type="button" onClick={() => setRegister(!register)}>{register ? "Already have an account? Sign in" : "New here? Create an account"}</button>
      </form>
    </main>
  );
}

function Stat({ label, value, tone, icon }) {
  return <div className="stat-card"><div className={`stat-icon ${tone}`}>{icon}</div><div><span>{label}</span><strong>{value}</strong></div></div>;
}

function TaskRow({ task, onToggle, onEdit, onDelete }) {
  const overdue = task.due_date && !task.completed && new Date(task.due_date) < new Date();
  return <div className={`task-row ${task.completed ? "task-complete" : ""}`}>
    <button className={`check ${task.completed ? "checked" : ""}`} onClick={() => onToggle(task)} aria-label={`Mark ${task.title} ${task.completed ? "pending" : "complete"}`}>{task.completed ? "✓" : ""}</button>
    <div className="task-main"><strong>{task.title}</strong><span>{task.category || "General"} {task.due_date && ` · ${new Date(task.due_date).toLocaleDateString()}`} {task.estimated_minutes && ` · ${task.estimated_minutes} min`}</span></div>
    <span className={`priority priority-${task.priority}`}>{task.priority}</span>
    {overdue && <span className="overdue">Overdue</span>}
    <div className="row-actions"><button onClick={() => onEdit(task)} aria-label="Edit task">Edit</button><button onClick={() => onDelete(task)} aria-label="Delete task">×</button></div>
  </div>;
}

function TaskModal({ form, editing, setForm, onSave, onClose, goals }) {
  function change(event) { setForm({ ...form, [event.target.name]: event.target.value }); }
  return <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
    <form className="modal" onSubmit={onSave}>
      <div className="modal-head"><div><p className="eyebrow">{editing ? "EDIT TASK" : "NEW TASK"}</p><h2>{editing ? "Refine your task" : "Capture a new task"}</h2></div><button type="button" className="close-button" onClick={onClose}>×</button></div>
      <label>Task title<input name="title" required autoFocus value={form.title} onChange={change} placeholder="What needs your attention?" /></label>
      <label>Description<textarea name="description" rows="3" value={form.description} onChange={change} placeholder="Add helpful context..." /></label>
      <div className="modal-grid"><label>Priority<select name="priority" value={form.priority} onChange={change}><option>low</option><option>medium</option><option>high</option><option>urgent</option></select></label><label>Category<input name="category" value={form.category} onChange={change} placeholder="Career" /></label><label>Deadline<input name="due_date" type="datetime-local" value={form.due_date} onChange={change} /></label><label>Estimate (minutes)<input name="estimated_minutes" type="number" min="1" value={form.estimated_minutes} onChange={change} placeholder="60" /></label><label>Goal<select name="goal_id" value={form.goal_id} onChange={(e) => setForm({ ...form, goal_id: e.target.value, milestone_id: "" })}><option value="">No goal</option>{goals.map((goal) => <option key={goal.id} value={goal.id}>{goal.title}</option>)}</select></label><label>Milestone<select name="milestone_id" value={form.milestone_id} onChange={change}><option value="">No milestone</option>{(goals.find((goal) => String(goal.id) === String(form.goal_id))?.milestones || []).map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label></div>
      <div className="modal-actions"><button type="button" className="button button-ghost" onClick={onClose}>Cancel</button><button className="button button-primary" type="submit">{editing ? "Save changes" : "Add task"} <span>→</span></button></div>
    </form>
  </div>;
}

function Assistant({ chat, message, setMessage, loading, send, onPrompt }) {
  const prompts = ["Plan my day", "Review my tasks", "Show my pending tasks", "Add a task to finish my CV"];
  return <section className="assistant-panel panel">
    <div className="panel-title"><div><span className="section-kicker">AI ASSISTANT</span><h2>Your thoughtful co-pilot</h2><p>Ask naturally. Your assistant can manage tasks and keep you moving.</p></div><div className="ai-orb">✦</div></div>
    <div className="suggestions">{prompts.map((prompt) => <button key={prompt} onClick={() => onPrompt(prompt)}>{prompt} <span>↗</span></button>)}</div>
    <div className="chat-log">{chat.length === 0 && <div className="chat-empty"><div className="empty-orb">✦</div><strong>What would you like to accomplish?</strong><span>Try one of the prompts above or ask anything about your tasks.</span></div>}{chat.map((item, index) => <div key={index} className={`chat-message ${item.role === "user" ? "chat-user" : "chat-assistant"}`}><span className="message-label">{item.role === "user" ? "You" : "Taskwise AI"}</span><p>{item.content}</p></div>)}{loading && <div className="typing"><i></i><i></i><i></i> Assistant is thinking</div>}</div>
    <form className="chat-composer" onSubmit={send}><input value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Ask your assistant anything..." /><button className="send-button" disabled={loading} aria-label="Send message">↑</button></form>
  </section>;
}

function GoalPage({ setError }) {
  const [goals, setGoals] = useState([]);
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState({ title: "", description: "", start_date: "", target_date: "" });
  const [milestone, setMilestone] = useState("");
  const [proposal, setProposal] = useState(null);
  const [newTask, setNewTask] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    try { const data = await request("/api/goals"); setGoals(data); if (selected) setSelected(data.find((item) => item.id === selected.id) || null); }
    catch (e) { setError(e.message); }
  }
  useEffect(() => { load(); }, []);
  function edit(goal) {
    setSelected(goal);
    setForm({ title: goal.title, description: goal.description || "", start_date: goal.start_date?.slice(0, 16) || "", target_date: goal.target_date?.slice(0, 16) || "" });
  }
  async function save(event) {
    event.preventDefault();
    const payload = { ...form, start_date: form.start_date ? new Date(form.start_date).toISOString() : null, target_date: form.target_date ? new Date(form.target_date).toISOString() : null };
    try { await request(selected ? `/api/goals/${selected.id}` : "/api/goals", { method: selected ? "PATCH" : "POST", body: JSON.stringify(payload) }); setForm({ title: "", description: "", start_date: "", target_date: "" }); setSelected(null); await load(); }
    catch (e) { setError(e.message); }
  }
  async function remove(goal) {
    if (!window.confirm(`Delete "${goal.title}" and its milestones?`)) return;
    try { await request(`/api/goals/${goal.id}`, { method: "DELETE" }); setSelected(null); await load(); } catch (e) { setError(e.message); }
  }
  async function addMilestone(event) {
    event.preventDefault(); if (!selected || !milestone.trim()) return;
    try { await request(`/api/goals/${selected.id}/milestones`, { method: "POST", body: JSON.stringify({ title: milestone.trim() }) }); setMilestone(""); await load(); } catch (e) { setError(e.message); }
  }
  async function toggleMilestone(item) {
    try { await request(`/api/goals/${selected.id}/milestones/${item.id}`, { method: "PATCH", body: JSON.stringify({ status: item.status === "completed" ? "pending" : "completed" }) }); await load(); } catch (e) { setError(e.message); }
  }
  async function addMilestoneTask(event, milestoneId) {
    event.preventDefault();
    if (!selected || !newTask.trim()) return;
    try {
      await request("/api/tasks", { method: "POST", body: JSON.stringify({ title: newTask.trim(), goal_id: selected.id, milestone_id: milestoneId }) });
      setNewTask(""); await load();
    } catch (e) { setError(e.message); }
  }
  async function moveTask(taskId, milestoneId) {
    try {
      await request(`/api/tasks/${taskId}`, { method: "PATCH", body: JSON.stringify({ milestone_id: milestoneId ? Number(milestoneId) : null }) });
      await load();
    } catch (e) { setError(e.message); }
  }
  async function createBreakdown() {
    if (!selected) return;
    setBusy(true); try { setProposal(await request(`/api/goals/${selected.id}/breakdown`, { method: "POST" })); } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function approveBreakdown() {
    try { await request(`/api/goals/${selected.id}/breakdown/approve`, { method: "POST", body: JSON.stringify({ proposal }) }); setProposal(null); await load(); } catch (e) { setError(e.message); }
  }
  return <section className="goals-page">
    <div className="welcome-row"><div><span className="section-kicker">GOALS</span><h1>Build what matters</h1><p>Turn meaningful outcomes into clear milestones and tasks.</p></div><button className="button button-primary" onClick={() => { setSelected(null); setForm({ title: "", description: "", start_date: "", target_date: "" }); }}>＋ New goal</button></div>
    <div className="goals-layout"><div className="goal-list panel">{goals.length ? goals.map((goal) => <button key={goal.id} className={`goal-card ${selected?.id === goal.id ? "goal-selected" : ""}`} onClick={() => edit(goal)}><span className="goal-status">{goal.status}</span><strong>{goal.title}</strong><small>{goal.progress}% complete · {goal.task_ids.length} linked tasks</small><div className="goal-progress"><i style={{ width: `${goal.progress}%` }} /></div></button>) : <div className="empty-state"><span>◎</span><strong>No goals yet</strong><p>Create a goal to start a focused breakdown.</p></div>}</div>
      <div className="goal-workspace panel"><form onSubmit={save} className="goal-form"><div className="panel-title"><div><span className="section-kicker">{selected ? "EDIT GOAL" : "NEW GOAL"}</span><h2>{selected ? "Refine your goal" : "Create a goal"}</h2></div>{selected && <button type="button" className="text-button" onClick={() => remove(selected)}>Delete</button>}</div><label>Title<input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Become a full-stack developer" /></label><label>Description<textarea rows="3" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="What does success look like?" /></label><div className="modal-grid"><label>Start date<input type="datetime-local" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} /></label><label>Target date<input type="datetime-local" value={form.target_date} onChange={(e) => setForm({ ...form, target_date: e.target.value })} /></label></div><button className="button button-primary" type="submit">{selected ? "Save goal" : "Create goal"}</button></form>
        {selected && <><div className="goal-divider" /><div className="panel-title"><div><span className="section-kicker">MILESTONES</span><h2>Progress markers</h2></div><span className="muted">{selected.milestones.filter((item) => item.status === "completed").length}/{selected.milestones.length}</span></div><form className="inline-form" onSubmit={addMilestone}><input value={milestone} onChange={(e) => setMilestone(e.target.value)} placeholder="Add a milestone..." /><button className="button button-violet">Add</button></form><div className="milestone-list">{selected.milestones.map((item) => <div key={item.id} className="milestone-section"><button className="milestone" onClick={() => toggleMilestone(item)}><span>{item.status === "completed" ? "✓" : "○"}</span><strong>{item.title}</strong><small>{item.task_count} tasks</small></button><div className="milestone-tasks">{item.tasks.map((task) => <div className="linked-task" key={task.id}><span>{task.completed ? "✓" : "•"} {task.title}</span><select value={task.milestone_id || ""} onChange={(e) => moveTask(task.id, e.target.value)}><option value="">No milestone</option>{selected.milestones.map((option) => <option key={option.id} value={option.id}>{option.title}</option>)}</select></div>)}<form className="inline-form compact-form" onSubmit={(e) => addMilestoneTask(e, item.id)}><input value={newTask} onChange={(e) => setNewTask(e.target.value)} placeholder="Add task to this milestone..." /><button className="text-button">＋ Add</button></form></div></div>)}</div><div className="breakdown-box"><div><span className="section-kicker">AI BREAKDOWN</span><h2>Make this goal actionable</h2><p className="muted">Generate milestones and smaller tasks for your approval. Nothing is saved until you approve it.</p></div><button className="button button-violet" onClick={createBreakdown} disabled={busy}>{busy ? "Thinking..." : "Suggest breakdown"}</button></div>{proposal && <div className="proposal"><h2>{proposal.summary}</h2><p className="muted">{proposal.milestones.length} milestones · {proposal.tasks.length} tasks proposed</p><ul>{proposal.tasks.map((item, index) => <li key={index}><strong>{item.title}</strong><span>{item.priority} · {item.estimated_minutes || "—"} min</span></li>)}</ul><button className="button button-primary" onClick={approveBreakdown}>Approve and add to goal</button></div>}</>}
      </div></div>
  </section>;
}

function Dashboard({ user, onLogout }) {
  const [tasks, setTasks] = useState([]);
  const [goals, setGoals] = useState([]);
  const [view, setView] = useState("Overview");
  const [filters, setFilters] = useState({ priority: "", category: "", completed: "", sort: "created" });
  const [form, setForm] = useState(EMPTY_FORM);
  const [editing, setEditing] = useState(null);
  const [modal, setModal] = useState(false);
  const [message, setMessage] = useState("");
  const [chat, setChat] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [mobileNav, setMobileNav] = useState(false);

  const loadTasks = () => {
    const params = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
    request(`/api/tasks?${params}`).then(setTasks).catch((e) => setError(e.message));
  };
  const loadGoals = () => request("/api/goals").then(setGoals).catch((e) => setError(e.message));
  useEffect(loadTasks, [filters]);
  useEffect(loadGoals, []);

  const stats = useMemo(() => {
    const completed = tasks.filter((task) => task.completed).length;
    const overdue = tasks.filter((task) => !task.completed && task.due_date && new Date(task.due_date) < new Date()).length;
    return { total: tasks.length, completed, pending: tasks.length - completed, overdue };
  }, [tasks]);
  const categories = [...new Set(tasks.map((task) => task.category).filter(Boolean))];
  const upcoming = tasks.filter((task) => !task.completed && task.due_date).sort((a, b) => new Date(a.due_date) - new Date(b.due_date)).slice(0, 4);
  const today = tasks.filter((task) => task.due_date && new Date(task.due_date).toDateString() === new Date().toDateString());

  function openCreate() { setEditing(null); setForm(EMPTY_FORM); setModal(true); }
  function openEdit(task) { setEditing(task); setForm({ title: task.title, description: task.description || "", priority: task.priority, due_date: task.due_date ? task.due_date.slice(0, 16) : "", category: task.category || "", estimated_minutes: task.estimated_minutes || "", goal_id: task.goal_id || "", milestone_id: task.milestone_id || "" }); setModal(true); }
  async function saveTask(event) {
    event.preventDefault();
    const payload = { ...form, goal_id: form.goal_id ? Number(form.goal_id) : null, due_date: form.due_date ? new Date(form.due_date).toISOString() : null, estimated_minutes: form.estimated_minutes ? Number(form.estimated_minutes) : null };
    try {
      if (editing) await request(`/api/tasks/${editing.id}`, { method: "PATCH", body: JSON.stringify(payload) });
      else await request("/api/tasks", { method: "POST", body: JSON.stringify(payload) });
      setModal(false); loadTasks(); loadGoals();
    } catch (e) { setError(e.message); }
  }
  async function toggle(task) { try { await request(`/api/tasks/${task.id}`, { method: "PATCH", body: JSON.stringify({ completed: !task.completed }) }); loadTasks(); } catch (e) { setError(e.message); } }
  async function remove(task) { if (!window.confirm(`Delete "${task.title}"?`)) return; try { await request(`/api/tasks/${task.id}`, { method: "DELETE" }); loadTasks(); } catch (e) { setError(e.message); } }
  async function send(event) { event.preventDefault(); if (!message.trim()) return; const text = message.trim(); setMessage(""); setChat((items) => [...items, { role: "user", content: text }]); setLoading(true); try { const data = await request("/api/chat", { method: "POST", body: JSON.stringify({ message: text }) }); setChat((items) => [...items, data.message]); loadTasks(); } catch (e) { setChat((items) => [...items, { role: "assistant", content: e.message }]); } finally { setLoading(false); } }

  const nav = [["Overview", "⌂", true], ["AI Assistant", "✦", true], ["My Tasks", "✓", true], ["Goals", "◎", true], ["Calendar", "▣", false], ["My Planner", "◫", false], ["Analytics", "◒", false], ["Reminders", "◷", false], ["Settings", "⚙", false]];
  return <div className="app-shell">
    <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}><div><Logo /><button className="mobile-close" onClick={() => setMobileNav(false)}>×</button><nav>{nav.map(([label, icon, enabled]) => <button key={label} className={view === label ? "nav-active" : ""} disabled={!enabled} onClick={() => { setView(label); setMobileNav(false); }}><span>{icon}</span>{label}{!enabled && <em>Soon</em>}</button>)}</nav></div><div className="sidebar-bottom"><div className="upgrade-card"><span>✦</span><strong>Work smarter</strong><p>Let AI help you find your next best action.</p><button onClick={() => setView("AI Assistant")}>Open assistant →</button></div><div className="profile"><div className="avatar">{user.email[0].toUpperCase()}</div><div><strong>{user.email.split("@")[0]}</strong><span>{user.email}</span></div><button onClick={onLogout} aria-label="Log out">↗</button></div></div></aside>
    <main className="main-area"><header className="topbar"><button className="mobile-menu" onClick={() => setMobileNav(true)}>☰</button><div className="breadcrumb"><span>Workspace</span><b>/</b><strong>{view}</strong></div><div className="top-actions"><span className="date-label">{new Date().toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}</span><button className="icon-button">♧</button><div className="top-avatar">{user.email[0].toUpperCase()}</div></div></header>
      <div className="page-content">{error && <div className="alert">{error}<button onClick={() => setError("")}>×</button></div>}
        {view === "AI Assistant" ? <Assistant chat={chat} message={message} setMessage={setMessage} loading={loading} send={send} onPrompt={(prompt) => { setMessage(prompt); }} /> : view === "Goals" ? <GoalPage setError={setError} /> : <><div className="welcome-row"><div><span className="section-kicker">OVERVIEW</span><h1>Good morning, {user.email.split("@")[0]} <span className="wave">✦</span></h1><p>Make today meaningful, one task at a time.</p></div><button className="button button-primary" onClick={openCreate}>＋ New task</button></div>
          <div className="stats-grid"><Stat label="Total tasks" value={stats.total} tone="violet" icon="◈" /><Stat label="Completed" value={stats.completed} tone="green" icon="✓" /><Stat label="In progress" value={stats.pending} tone="amber" icon="◌" /><Stat label="Overdue" value={stats.overdue} tone="red" icon="!" /></div>
          <div className="dashboard-grid"><section className="panel task-overview"><div className="panel-title"><div><span className="section-kicker">FOCUS LIST</span><h2>{view === "My Tasks" ? "All your tasks" : "Your tasks today"}</h2></div><button className="text-button" onClick={() => setView("My Tasks")}>View all →</button></div><div className="task-filters"><input placeholder="Search tasks..." onChange={(e) => setFilters({ ...filters, category: e.target.value })} /><select value={filters.priority} onChange={(e) => setFilters({ ...filters, priority: e.target.value })}><option value="">All priority</option><option value="urgent">Urgent</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select><select value={filters.completed} onChange={(e) => setFilters({ ...filters, completed: e.target.value })}><option value="">All status</option><option value="false">Pending</option><option value="true">Completed</option></select></div><div className="task-list">{tasks.length ? tasks.slice(0, view === "My Tasks" ? tasks.length : 5).map((task) => <TaskRow key={task.id} task={task} onToggle={toggle} onEdit={openEdit} onDelete={remove} />) : <div className="empty-state"><span>✦</span><strong>No tasks yet</strong><p>Create your first task to get moving.</p><button className="text-button" onClick={openCreate}>Add a task →</button></div>}</div></section>
            <section className="side-stack"><div className="panel productivity-panel"><div className="panel-title"><div><span className="section-kicker">MOMENTUM</span><h2>Weekly progress</h2></div><span className="trend">+12%</span></div><div className="progress-ring"><div><strong>{stats.total ? Math.round((stats.completed / stats.total) * 100) : 0}%</strong><span>complete</span></div></div><div className="mini-bars">{[38, 58, 46, 72, 54, 82, 64].map((height, index) => <div key={index} className={index === 5 ? "bar today" : "bar"} style={{ height: `${height}%` }}><span>{["M", "T", "W", "T", "F", "S", "S"][index]}</span></div>)}</div></div><div className="panel upcoming-panel"><div className="panel-title"><div><span className="section-kicker">UP NEXT</span><h2>Upcoming deadlines</h2></div><span className="calendar-icon">▣</span></div>{upcoming.length ? upcoming.map((task) => <div className="deadline" key={task.id}><span className={`deadline-dot dot-${task.priority}`}></span><div><strong>{task.title}</strong><span>{new Date(task.due_date).toLocaleDateString(undefined, { month: "short", day: "numeric" })} · {task.category || "General"}</span></div></div>) : <p className="muted">No upcoming deadlines.</p>}</div></section></div>
          <section className="ai-banner"><div className="ai-banner-orb">✦</div><div><span className="section-kicker">TASKWISE AI</span><h2>Ready to make progress?</h2><p>Tell me what you want to get done and I'll help organize the next step.</p></div><button className="button button-violet" onClick={() => setView("AI Assistant")}>Chat with AI <span>→</span></button></section>
        </>}
      </div>
    </main>
    {modal && <TaskModal form={form} editing={editing} setForm={setForm} goals={goals} onSave={saveTask} onClose={() => setModal(false)} />}
  </div>;
}

function App() {
  const [user, setUser] = useState(null);
  useEffect(() => { if (localStorage.getItem("task_token")) request("/api/auth/me").then(setUser).catch(() => { localStorage.removeItem("task_token"); }); }, []);
  if (!user) return <Auth onLogin={setUser} />;
  return <Dashboard user={user} onLogout={() => { localStorage.removeItem("task_token"); setUser(null); }} />;
}

createRoot(document.getElementById("root")).render(<App />);
