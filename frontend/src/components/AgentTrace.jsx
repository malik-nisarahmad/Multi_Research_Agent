import React from 'react';
import { useApp } from '../context/AppContext';
import { CheckCircle2, Loader2, Circle, AlertTriangle, ShieldAlert, Award, ArrowRight } from 'lucide-react';

export default function AgentTrace({ isOpen }) {
  const { agentTrace, confidenceScore, researchAttempts } = useApp();

  const getStatusIcon = (status) => {
    switch (status) {
      case 'running':
        return <Loader2 size={14} style={{ animation: 'spin 1.5s linear infinite' }} />;
      case 'done':
        return <CheckCircle2 size={14} />;
      case 'skipped':
        return <ArrowRight size={14} />;
      case 'pending':
      default:
        return <Circle size={14} />;
    }
  };

  const steps = [
    {
      id: 'clarity',
      name: 'Clarity Agent',
      status: agentTrace.clarity,
      description: 'Validates company details & search parameters.',
      meta: null
    },
    {
      id: 'research',
      name: 'Research Agent',
      status: agentTrace.research,
      description: 'Executes parallel searches (news, financials, developments).',
      meta: (agentTrace.research === 'done' || agentTrace.research === 'running') && confidenceScore > 0 ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.65rem' }}>
          <Award size={13} style={{ color: '#D4A44E' }} />
          <span>Confidence: <strong>{confidenceScore.toFixed(1)}/10</strong></span>
        </div>
      ) : null
    },
    {
      id: 'validator',
      name: 'Validator Agent',
      status: agentTrace.validator,
      description: 'Verifies data completeness & checks for news/figures.',
      meta: (agentTrace.validator === 'done' || agentTrace.validator === 'running' || researchAttempts > 0) ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.65rem' }}>
          <ShieldAlert size={13} style={{ color: '#D4A44E' }} />
          <span>Attempts: <strong>{researchAttempts}/3</strong></span>
        </div>
      ) : null
    },
    {
      id: 'synthesis',
      name: 'Synthesis Agent',
      status: agentTrace.synthesis,
      description: 'Formats consolidated markdown summaries.',
      meta: null
    }
  ];

  return (
    <aside className={`trace-panel ${isOpen ? 'open' : ''}`}>
      <div className="header">
        <h2 style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', fontWeight: 600, letterSpacing: '0.09em', textTransform: 'uppercase', color: '#8C897F' }}>
          Agent Pipeline Trace
        </h2>
      </div>

      <div className="trace-steps">
        {steps.map((step) => (
          <div key={step.id} className={`trace-step ${step.status}`}>
            <div className="trace-icon">
              {getStatusIcon(step.status)}
            </div>
            <div className="trace-content">
              <span className="trace-name">{step.name}</span>
              <span className="trace-status">{step.status || 'pending'}</span>
              <p style={{ fontSize: '0.67rem', color: '#5E5C57', marginTop: '2px' }}>
                {step.description}
              </p>
              {step.meta && <div className="trace-meta">{step.meta}</div>}
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}
