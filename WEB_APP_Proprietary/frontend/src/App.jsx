// frontend/src/App.jsx
import React, { useState, useRef, useEffect } from 'react';
import './App.css';

// Components
const Sidebar = ({ settings, onSettingsChange, onAnalyze, isAnalyzing }) => {
  const [isCollapsed, setIsCollapsed] = useState(false);

  return (
    <div className={`sidebar ${isCollapsed ? 'collapsed' : ''}`}>
      <button 
        className="sidebar-toggle"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        {isCollapsed ? '»' : '«'}
      </button>
      
      {!isCollapsed && (
        <>
          <h2>⚙️ Configuration</h2>
          <p className="tip">💡 Tip: Click « to collapse</p>
          
          <div className="form-group">
            <label>Template Set</label>
            <select 
              value={settings.companionType} 
              onChange={(e) => onSettingsChange({companionType: e.target.value})}
            >
              <option value="generic">Generic</option>
              <option value="marketing">Marketing</option>
              <option value="bug_triage">Bug Triage</option>
              <option value="strategy">Strategy</option>
            </select>
          </div>

          <div className="form-group">
            <label>Model</label>
            <select 
              value={settings.model} 
              onChange={(e) => onSettingsChange({model: e.target.value})}
            >
              <option value="gpt-4o-mini">GPT-4 Optimized Mini</option>
              <option value="gpt-4o">GPT-4 Optimized</option>
              <option value="gpt-4">GPT-4</option>
              <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
            </select>
          </div>

          <div className="form-group">
            <label>Temperature: {settings.temperature}</label>
            <input 
              type="range" 
              min="0" 
              max="1" 
              step="0.1"
              value={settings.temperature}
              onChange={(e) => onSettingsChange({temperature: parseFloat(e.target.value)})}
            />
          </div>

          <div className="form-group">
            <label>Max Critique Loops: {settings.maxLoops}</label>
            <input 
              type="range" 
              min="1" 
              max="5" 
              step="1"
              value={settings.maxLoops}
              onChange={(e) => onSettingsChange({maxLoops: parseInt(e.target.value)})}
            />
          </div>

          <div className="form-group">
            <label>Similarity Threshold: {settings.similarityThreshold}</label>
            <input 
              type="range" 
              min="0.90" 
              max="0.99" 
              step="0.01"
              value={settings.similarityThreshold}
              onChange={(e) => onSettingsChange({similarityThreshold: parseFloat(e.target.value)})}
            />
          </div>

          <div className="form-group">
            <label>
              <input 
                type="checkbox"
                checked={settings.showMetrics}
                onChange={(e) => onSettingsChange({showMetrics: e.target.checked})}
              />
              Show Metrics
            </label>
          </div>

          <button 
            className="analyze-button"
            onClick={onAnalyze}
            disabled={isAnalyzing}
          >
            {isAnalyzing ? 'Analyzing...' : '🚀 Analyze'}
          </button>

          <div className="settings-summary">
            <h3>Current Settings:</h3>
            <ul>
              <li>Type: {settings.companionType}</li>
              <li>Model: {settings.model}</li>
              <li>Temp: {settings.temperature}</li>
              <li>Loops: {settings.maxLoops}</li>
              <li>Threshold: {settings.similarityThreshold}</li>
            </ul>
          </div>
        </>
      )}
    </div>
  );
};

const IterationDisplay = ({ iteration, isExpanded, onToggle, isLast }) => {
  return (
    <div className="iteration">
      <div className="iteration-header" onClick={onToggle}>
        <span className="iteration-toggle">{isExpanded ? '▼' : '▶'}</span>
        <h3>🔄 Iteration {iteration.number}</h3>
        {iteration.similarity && !isLast && (
          <span className="similarity">Similarity: {iteration.similarity.toFixed(3)}</span>
        )}
      </div>
      {isExpanded && (
        <div className="iteration-content">
          {iteration.critique && (
            <>
              <h4>Critique:</h4>
              <div className="content-block">{iteration.critique}</div>
            </>
          )}
          {iteration.revision && !isLast && (
            <>
              <h4>Revision:</h4>
              <div className="content-block">{iteration.revision}</div>
            </>
          )}
        </div>
      )}
    </div>
  );
};

const StreamingDisplay = ({ streamData }) => {
  const [expandedIterations, setExpandedIterations] = useState(new Set());

  const toggleIteration = (num) => {
    const newExpanded = new Set(expandedIterations);
    if (newExpanded.has(num)) {
      newExpanded.delete(num);
    } else {
      newExpanded.add(num);
    }
    setExpandedIterations(newExpanded);
  };

  // Auto-expand current iteration and collapse previous ones
  useEffect(() => {
    if (streamData.currentIteration > 0) {
      setExpandedIterations(new Set([streamData.currentIteration]));
    }
  }, [streamData.currentIteration]);

  return (
    <div className="streaming-display">
      {streamData.initialDraft && (
        <div className="iteration">
          <div 
            className="iteration-header" 
            onClick={() => toggleIteration(0)}
          >
            <span className="iteration-toggle">{expandedIterations.has(0) ? '▼' : '▶'}</span>
            <h3>📝 Initial Draft</h3>
          </div>
          {expandedIterations.has(0) && (
            <div className="iteration-content">
              <div className="content-block">{streamData.initialDraft}</div>
            </div>
          )}
        </div>
      )}

      {streamData.iterations.map((iter, index) => (
        <IterationDisplay
          key={iter.number}
          iteration={iter}
          isExpanded={expandedIterations.has(iter.number)}
          onToggle={() => toggleIteration(iter.number)}
          isLast={index === streamData.iterations.length - 1 && streamData.isComplete}
        />
      ))}

      {streamData.status && (
        <div className={`status ${streamData.isComplete ? 'complete' : 'in-progress'}`}>
          {streamData.status}
          {!streamData.isComplete && <span className="thinking-dots"></span>}
        </div>
      )}
    </div>
  );
};

const TemplateViewer = ({ companionType }) => {
  const [templates, setTemplates] = useState({});
  const [activeTab, setActiveTab] = useState('initial');

  useEffect(() => {
    fetch(`http://localhost:8000/templates/${companionType}`)
      .then(res => res.json())
      .then(data => setTemplates(data))
      .catch(err => console.error('Failed to load templates:', err));
  }, [companionType]);

  const tabs = [
    { id: 'initial', label: 'Initial', key: `${companionType}_initial_sys` },
    { id: 'critique', label: 'Critique', key: 'generic_critique_sys' },
    { id: 'revision', label: 'Revision', key: 'generic_revision_sys' },
    { id: 'protocol', label: 'Protocol', key: 'protocol_context' }
  ];

  return (
    <div className="template-viewer">
      <h3>📄 Active Templates</h3>
      <div className="tabs">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="template-content">
        <pre>{templates[tabs.find(t => t.id === activeTab)?.key] || 'Loading...'}</pre>
      </div>
    </div>
  );
};

// Main App Component
function App() {
  const [query, setQuery] = useState('');
  const [settings, setSettings] = useState({
    companionType: 'generic',
    model: 'gpt-4o-mini',
    temperature: 0.7,
    maxLoops: 3,
    similarityThreshold: 0.98,
    showMetrics: true
  });
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [streamData, setStreamData] = useState({
    initialDraft: '',
    iterations: [],
    currentIteration: 0,
    status: '',
    isComplete: false
  });
  const [finalAnswer, setFinalAnswer] = useState('');
  const [metrics, setMetrics] = useState(null);

  const eventSourceRef = useRef(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const updateSettings = (updates) => {
    setSettings(prev => ({ ...prev, ...updates }));
  };

  const startAnalysis = async () => {
    if (!query.trim() || isAnalyzing) return;

    setIsAnalyzing(true);
    setFinalAnswer('');
    setMetrics(null);
    setStreamData({
      initialDraft: '',
      iterations: [],
      currentIteration: 0,
      status: 'Starting analysis...',
      isComplete: false
    });

    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    // Create EventSource for SSE
    const eventSource = new EventSource(
      `http://localhost:8000/analyze/stream?${new URLSearchParams({
        query: query,
        companion_type: settings.companionType,
        model: settings.model,
        temperature: settings.temperature,
        max_loops: settings.maxLoops,
        similarity_threshold: settings.similarityThreshold
      })}`
    );

    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.error) {
        console.error('Stream error:', data.error);
        setStreamData(prev => ({ ...prev, status: `Error: ${data.error}`, isComplete: true }));
        setIsAnalyzing(false);
        eventSource.close();
        return;
      }

      // Update stream data based on phase
      if (data.phase === 'initial_draft') {
        setStreamData(prev => ({
          ...prev,
          initialDraft: data.content,
          currentIteration: 0,
          status: 'Critiquing iteration 1...'
        }));
      } else if (data.phase === 'critique') {
        setStreamData(prev => ({
          ...prev,
          iterations: [
            ...prev.iterations.slice(0, data.iteration - 1),
            {
              number: data.iteration,
              critique: data.content,
              revision: prev.iterations[data.iteration - 1]?.revision || null
            }
          ],
          currentIteration: data.iteration,
          status: `Revising iteration ${data.iteration}...`
        }));
      } else if (data.phase === 'revision') {
        setStreamData(prev => ({
          ...prev,
          iterations: prev.iterations.map((iter, idx) => 
            idx === data.iteration - 1 
              ? { ...iter, revision: data.content, similarity: data.similarity }
              : iter
          ),
          status: `Critiquing iteration ${data.iteration + 1}...`
        }));
      } else if (data.phase === 'complete') {
        setFinalAnswer(data.content);
        setStreamData(prev => ({
          ...prev,
          status: getCompletionMessage(data.reason, data.similarity),
          isComplete: true
        }));
        setMetrics({
          iterations: data.iteration,
          reason: data.reason,
          finalSimilarity: data.similarity
        });
        setIsAnalyzing(false);
        eventSource.close();
      }
    };

    eventSource.onerror = (error) => {
      console.error('EventSource error:', error);
      setStreamData(prev => ({ ...prev, status: 'Connection error', isComplete: true }));
      setIsAnalyzing(false);
      eventSource.close();
    };
  };

  const getCompletionMessage = (reason, similarity) => {
    switch(reason) {
      case 'no_improvements':
        return '✓ Early exit: No further improvements needed';
      case 'converged':
        return `✓ Converged: Similarity threshold reached (${similarity ? similarity.toFixed(3) : 'N/A'})`;
      case 'max_loops':
        return '✓ Complete: Maximum iterations reached';
      default:
        return '✓ Analysis complete';
    }
  };

  return (
    <div className="app">
      <Sidebar 
        settings={settings}
        onSettingsChange={updateSettings}
        onAnalyze={startAnalysis}
        isAnalyzing={isAnalyzing}
      />
      
      <div className="main-content">
        <header>
          <h1>🔄 Recursive Companion Studio</h1>
          <p>Watch AI agents critique and refine their own responses in real-time</p>
        </header>

        <div className="content-grid">
          <div className="left-panel">
            <div className="input-section">
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Example: Our customer retention dropped 25% after the latest update. Support tickets mention confusion with the new interface. What's happening?"
                rows={6}
              />
            </div>

            {isAnalyzing && !streamData.initialDraft && (
              <div className="thinking-indicator">
                Thinking<span className="thinking-dots"></span>
              </div>
            )}

            {streamData.initialDraft && (
              <div className="streaming-section">
                <h2>🔄 Refinement Process</h2>
                <StreamingDisplay streamData={streamData} />
              </div>
            )}

            {finalAnswer && (
              <div className="final-answer">
                <h2>📋 Final Analysis</h2>
                <div className="content-block">{finalAnswer}</div>
              </div>
            )}

            {metrics && settings.showMetrics && (
              <div className="metrics">
                <h3>📊 Metrics</h3>
                <div className="metric-grid">
                  <div className="metric">
                    <span className="metric-label">Iterations</span>
                    <span className="metric-value">{metrics.iterations}</span>
                  </div>
                  <div className="metric">
                    <span className="metric-label">Exit Reason</span>
                    <span className="metric-value">{metrics.reason}</span>
                  </div>
                  {metrics.finalSimilarity && (
                    <div className="metric">
                      <span className="metric-label">Final Similarity</span>
                      <span className="metric-value">{metrics.finalSimilarity.toFixed(3)}</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="right-panel">
            <TemplateViewer companionType={settings.companionType} />
          </div>
        </div>

        <footer>
          Built with Recursive Companion Framework | Templates loaded from templates/ directory
        </footer>
      </div>
    </div>
  );
}

export default App;