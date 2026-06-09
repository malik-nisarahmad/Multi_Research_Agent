import React from 'react';

export default function TypingIndicator({ show }) {
  if (!show) return null;

  return (
    <div className="message-row assistant">
      <div className="message-bubble" style={{ padding: '10px 14px', borderBottomLeftRadius: '4px' }}>
        <div className="typing-indicator">
          <div className="typing-dot"></div>
          <div className="typing-dot"></div>
          <div className="typing-dot"></div>
        </div>
      </div>
    </div>
  );
}
