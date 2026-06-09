import React, { createContext, useContext, useState, useEffect, useRef } from 'react';

const AppContext = createContext();

// Set the Backend API URL correctly dynamically
const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export const AppProvider = ({ children }) => {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [awaitingClarification, setAwaitingClarification] = useState(false);
  const [agentTrace, setAgentTrace] = useState({
    clarity: 'pending',
    research: 'pending',
    validator: 'pending',
    synthesis: 'pending',
  });
  const [confidenceScore, setConfidenceScore] = useState(0);
  const [researchAttempts, setResearchAttempts] = useState(0);
  const [darkMode, setDarkMode] = useState(true);

  const pollIntervalRef = useRef(null);

  // Initialize and load sessions
  useEffect(() => {
    const saved = localStorage.getItem('research_sessions');
    if (saved) {
      const parsed = JSON.parse(saved);
      setSessions(parsed);
      if (parsed.length > 0) {
        setActiveSessionId(parsed[0].id);
      }
    } else {
      const newId = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 15);
      const initial = [{ id: newId, title: 'Tell me about Tesla', timestamp: Date.now() }];
      setSessions(initial);
      localStorage.setItem('research_sessions', JSON.stringify(initial));
      setActiveSessionId(newId);
    }
  }, []);

  // Update theme class on HTML element (always keep dark theme)
  useEffect(() => {
    document.documentElement.classList.add('dark');
    localStorage.setItem('theme', 'dark');
  }, []);

  // Fetch history when session changes
  useEffect(() => {
    if (!activeSessionId) return;
    loadSessionHistory(activeSessionId);
    // If active session changes, ensure we stop any running pollers
    stopPolling();
    setIsLoading(false);
  }, [activeSessionId]);

  const loadSessionHistory = async (sessionId) => {
    try {
      const res = await fetch(`${API_BASE}/history/${sessionId}`);
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages || []);
        setAgentTrace(data.agent_trace || {
          clarity: 'pending',
          research: 'pending',
          validator: 'pending',
          synthesis: 'pending'
        });
        setConfidenceScore(data.confidence_score || 0);
        setResearchAttempts(data.research_attempts || 0);
        setAwaitingClarification(data.awaiting_clarification || false);
      }
    } catch (err) {
      console.error('Failed to load session history:', err);
    }
  };

  const createSession = () => {
    const newId = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 15);
    const newSession = {
      id: newId,
      title: 'New Research Chat',
      timestamp: Date.now()
    };
    const updated = [newSession, ...sessions];
    setSessions(updated);
    localStorage.setItem('research_sessions', JSON.stringify(updated));
    setActiveSessionId(newId);
    setMessages([]);
    setAwaitingClarification(false);
    setAgentTrace({
      clarity: 'pending',
      research: 'pending',
      validator: 'pending',
      synthesis: 'pending'
    });
    setConfidenceScore(0);
    setResearchAttempts(0);
  };

  const deleteSession = async (sessionId) => {
    try {
      await fetch(`${API_BASE}/session/${sessionId}`, { method: 'DELETE' });
    } catch (err) {
      console.warn('Could not contact server to delete session data:', err);
    }

    const updated = sessions.filter(s => s.id !== sessionId);
    setSessions(updated);
    localStorage.setItem('research_sessions', JSON.stringify(updated));

    if (activeSessionId === sessionId) {
      if (updated.length > 0) {
        setActiveSessionId(updated[0].id);
      } else {
        const newId = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 15);
        const newSession = { id: newId, title: 'New Research Chat', timestamp: Date.now() };
        setSessions([newSession]);
        localStorage.setItem('research_sessions', JSON.stringify([newSession]));
        setActiveSessionId(newId);
      }
    }
  };

  const startPolling = (sessionId) => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    pollIntervalRef.current = setInterval(() => {
      loadSessionHistory(sessionId);
    }, 2000);
  };

  const stopPolling = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  };

  useEffect(() => {
    return () => stopPolling();
  }, []);

  const sendMessage = async (text) => {
    if (!text.trim() || !activeSessionId) return;

    // Set title on first user query
    const isFirstUserMsg = messages.filter(m => m.role === 'user').length === 0;
    if (isFirstUserMsg) {
      const updated = sessions.map(s => {
        if (s.id === activeSessionId) {
          const shortTitle = text.length > 25 ? text.substring(0, 25) + '...' : text;
          return { ...s, title: shortTitle };
        }
        return s;
      });
      setSessions(updated);
      localStorage.setItem('research_sessions', JSON.stringify(updated));
    }

    // Optimistically update message stream
    const userMsg = { role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setIsLoading(true);

    // Turn on status poller to retrieve background state updates
    startPolling(activeSessionId);

    try {
      const url = awaitingClarification ? `${API_BASE}/clarify` : `${API_BASE}/chat`;
      const bodyPayload = awaitingClarification 
        ? { session_id: activeSessionId, clarification: text }
        : { session_id: activeSessionId, message: text };

      let response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(bodyPayload),
      });

      if (!response.ok && response.status === 400 && awaitingClarification) {
        console.warn('Clarification request failed with 400. Attempting to fall back to a fresh chat request.');
        setAwaitingClarification(false);
        const fallbackUrl = `${API_BASE}/chat`;
        const fallbackPayload = { session_id: activeSessionId, message: text };
        response = await fetch(fallbackUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(fallbackPayload),
        });
      }

      if (response.ok) {
        stopPolling();
        // Trigger a final load to fetch complete results
        await loadSessionHistory(activeSessionId);
      } else {
        stopPolling();
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: 'Error: The server returned an error during calculation. Please check backend console.',
          name: 'System Error'
        }]);
      }
    } catch (err) {
      stopPolling();
      console.error(err);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: Connection lost. Ensure your backend is running at ${API_BASE}.`,
        name: 'Network Connection Error'
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AppContext.Provider value={{
      sessions,
      activeSessionId,
      messages,
      isLoading,
      awaitingClarification,
      agentTrace,
      confidenceScore,
      researchAttempts,
      darkMode,
      setDarkMode,
      createSession,
      deleteSession,
      setActiveSessionId,
      sendMessage
    }}>
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => useContext(AppContext);
