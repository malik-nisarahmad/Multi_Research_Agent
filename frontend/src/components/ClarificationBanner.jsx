import React from 'react';
import { AlertTriangle } from 'lucide-react';

export default function ClarificationBanner({ show }) {
  if (!show) return null;

  return (
    <div className="clarification-banner">
      <AlertTriangle size={16} style={{ color: '#D4A44E', flexShrink: 0 }} />
      <span className="clarification-banner-text">
        Ambiguous query detected: Which company are you asking about? Please clarify below.
      </span>
    </div>
  );
}
