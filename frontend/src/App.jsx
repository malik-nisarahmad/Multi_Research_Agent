import React, { useState, useEffect, useRef } from 'react';
import { AppProvider, useApp } from './context/AppContext';
import SessionSidebar from './components/SessionSidebar';
import AgentTrace from './components/AgentTrace';
import ChatMessage from './components/ChatMessage';
import ClarificationBanner from './components/ClarificationBanner';
import TypingIndicator from './components/TypingIndicator';
import { 
  Menu, 
  ChevronRight, 
  ChevronLeft, 
  Sparkles, 
  LayoutGrid, 
  Gift, 
  Bell, 
  Paperclip, 
  SlidersHorizontal, 
  Mic, 
  ArrowUp, 
  ChevronDown,
  Layers,
  Smartphone,
  AppWindow,
  Globe 
} from 'lucide-react';

function AppContent() {
  const {
    messages,
    isLoading,
    awaitingClarification,
    sendMessage
  } = useApp();

  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth > 768);
  const [traceOpen, setTraceOpen] = useState(true);
  const [input, setInput] = useState('');
  const [activeTab, setActiveTab] = useState('Full Stack App');
  
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    sendMessage(input);
    setInput('');
  };

  const handleSampleClick = (promptText) => {
    setInput('');
    sendMessage(promptText);
  };

  const samplePrompts = [
    "Tell me about Tesla's latest financials",
    "What's happening with OpenAI?",
    "Research Apple's competitors"
  ];

  return (
    <div className={`app-container ${sidebarOpen ? 'sidebar-open' : 'sidebar-collapsed'} ${traceOpen ? 'trace-open' : 'trace-collapsed'}`}>
      {/* Sidebar backdrop for mobile */}
      {sidebarOpen && (
        <div 
          className="sidebar-backdrop"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar Component */}
      <SessionSidebar isOpen={sidebarOpen} setIsOpen={setSidebarOpen} />

      {/* Main Conversation Stream */}
      <main className="main-content">
        {/* Navigation Header */}
        <header className="header">
          {/* Left Actions */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button 
              className="header-icon-btn" 
              onClick={() => setSidebarOpen(!sidebarOpen)}
              title="Toggle Sidebar"
            >
              <Menu size={16} />
            </button>
            
            <button className="home-pill" title="Home View">
              <LayoutGrid size={14} />
              <span>Home</span>
            </button>
          </div>

          {/* Right Actions */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button 
              className="header-icon-btn" 
              onClick={() => setTraceOpen(!traceOpen)}
              title={traceOpen ? "Hide Execution Trace" : "Show Execution Trace"}
            >
              {traceOpen ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
            </button>
          </div>
        </header>

        {/* Message Thread */}
        <div className="chat-thread">
          <div className="chat-thread-inner">
            {messages.length === 0 ? (
              <div className="empty-state">
                {/* Hero Title */}
                <h1 className="hero-title">Agentic Business Research</h1>
                <p className="hero-subtitle">
                  A collaborative multi-agent assistant built with LangGraph to collect business data, support follow-up inquiries, and prompt for clarification when queries are ambiguous.
                </p>

                {/* Styled Sample Prompts */}
                <div className="sample-prompts-container">
                  <p style={{ fontSize: '0.78rem', color: 'hsl(var(--text-muted-hsl))', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Or select a company to begin research:
                  </p>
                  <div className="sample-prompts">
                    {samplePrompts.map((prompt, idx) => (
                      <button 
                        key={idx}
                        className="sample-prompt-card"
                        onClick={() => handleSampleClick(prompt)}
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <>
                {messages.map((msg, index) => (
                  <ChatMessage key={index} message={msg} />
                ))}
                <TypingIndicator show={isLoading} />
              </>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* User Input Bar */}
        <div className="input-area">
          <div className="input-area-inner">
            <ClarificationBanner show={awaitingClarification} />

            {/* Premium Multi-Action Input Card */}
            <form onSubmit={handleSubmit} className="premium-chat-card">
              <textarea
                className="premium-chat-input"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit(e);
                  }
                }}
                placeholder={awaitingClarification ? "Type your clarification..." : "Enter a company or business query..."}
                disabled={isLoading && !awaitingClarification}
                rows={2}
              />
              
              <div className="premium-chat-actions">
                {/* Left controls */}
                <div className="actions-left">
                  {/* Model indicator selector pill */}
                  <div className="model-selector-pill">
                    <Sparkles size={12} style={{ color: '#D4A44E' }} />
                    <span>Gemini 1.5 Flash</span>
                    <ChevronDown size={11} />
                  </div>
                </div>

                {/* Right controls */}
                <div className="actions-right">
                  <button type="button" className="action-circle-btn" title="Parameters">
                    <SlidersHorizontal size={14} />
                  </button>
                  
                  <button 
                    type="submit" 
                    className="send-arrow-btn"
                    disabled={(isLoading && !awaitingClarification) || !input.trim()}
                    title={awaitingClarification ? "Send Clarification" : "Send Query"}
                  >
                    <ArrowUp size={15} />
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      </main>

      {/* Real-time Agent Trace */}
      <AgentTrace isOpen={traceOpen} />
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  );
}
