import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Copy, Check, Bot } from 'lucide-react';

export default function ChatMessage({ message }) {
  const { role, content, name } = message;
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getBadgeClass = (agentName) => {
    if (!agentName) return 'system';
    const lower = agentName.toLowerCase();
    if (lower.includes('clarity')) return 'clarity';
    if (lower.includes('validator')) return 'validator';
    if (lower.includes('research')) return 'research';
    return '';
  };

  return (
    <div className={`message-row ${role === 'user' ? 'user' : 'assistant'}`}>
      <div className="message-bubble markdown-body">
        {role === 'assistant' && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span className={`agent-badge ${getBadgeClass(name)}`}>
              <Bot size={11} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
              {name || 'Synthesis Agent'}
            </span>
          </div>
        )}
        
        {role === 'user' ? (
          <p style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{content}</p>
        ) : (
          <>
            <div style={{ fontSize: '0.94rem' }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {content}
              </ReactMarkdown>
            </div>
            <div className="message-actions">
              <button className="copy-btn" onClick={handleCopy}>
                {copied ? <Check size={12} style={{ color: '#56C487' }} /> : <Copy size={12} />}
                <span>{copied ? 'Copied!' : 'Copy'}</span>
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
