import React from 'react';
import { useApp } from '../context/AppContext';
import { Plus, Trash2, MessageSquare, Sparkles } from 'lucide-react';

export default function SessionSidebar({ isOpen, setIsOpen }) {
  const {
    sessions,
    activeSessionId,
    createSession,
    deleteSession,
    setActiveSessionId
  } = useApp();

  return (
    <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
      <div className="header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Sparkles size={16} style={{ color: '#D4A44E' }} />
          <h1 style={{ fontFamily: 'var(--font-display)', fontWeight: 800 }}>Agentic Intel</h1>
        </div>
      </div>

      <button className="new-chat-btn" onClick={createSession}>
        <Plus size={16} />
        New Research Session
      </button>

      <div className="sidebar-list">
        {sessions.map((session) => (
          <div
            key={session.id}
            className={`session-item ${session.id === activeSessionId ? 'active' : ''}`}
            onClick={() => {
              setActiveSessionId(session.id);
              if (window.innerWidth <= 768) setIsOpen(false); // Close on mobile width selection
            }}
          >
            <div className="session-title-container">
              <MessageSquare size={15} style={{ flexShrink: 0 }} />
              <span className="session-title">{session.title}</span>
            </div>
            <button
              className="delete-session-btn"
              onClick={(e) => {
                e.stopPropagation();
                deleteSession(session.id);
              }}
              title="Delete Session"
            >
              <Trash2 size={13} />
            </button>
          </div>
        ))}
      </div>
    </aside>
  );
}
