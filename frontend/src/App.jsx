import { Link, Route, Routes } from 'react-router-dom';
import './styles.css';

function Home() {
  return (
    <main className="welcome-card">
      <div className="brand-mark" aria-hidden="true">CB</div>
      <p className="eyebrow">CampusBite · Capstone project</p>
      <h1>Good food, closer to campus.</h1>
      <p className="intro">
        The project foundation is ready. Restaurant ordering and role-based
        experiences will be added in the next milestones.
      </p>
      <Link className="api-link" to="/api-status">View API status <span aria-hidden="true">→</span></Link>
    </main>
  );
}

function ApiStatus() {
  return (
    <main className="welcome-card">
      <p className="eyebrow">Project foundation</p>
      <h1>API foundation</h1>
      <p className="intro">The backend health endpoint is available at <code>/health</code>.</p>
      <Link className="api-link" to="/">Back to home <span aria-hidden="true">→</span></Link>
    </main>
  );
}

export default function App() {
  return (
    <div className="page-shell">
      <header className="site-header">
        <Link className="wordmark" to="/">Campus<span>Bite</span><b aria-hidden="true">.</b></Link>
        <span className="status-pill"><i aria-hidden="true" /> Foundation</span>
      </header>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/api-status" element={<ApiStatus />} />
      </Routes>
      <footer>Built for the campus community <span aria-hidden="true">✳</span></footer>
    </div>
  );
}
