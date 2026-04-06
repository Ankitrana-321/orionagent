import { useEffect, useState } from 'react';
import axios from 'axios';
import './App.css';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
const getApiUrl = (path) => `${API_BASE_URL}${path}`;

function App() {
  const [health, setHealth] = useState({
    loading: true,
    error: '',
    data: null,
  });
  const [singleInput, setSingleInput] = useState('How much should I score in each subject to pass CA final?');
  const [singleResponse, setSingleResponse] = useState('');
  const [singleError, setSingleError] = useState('');
  const [singleLoading, setSingleLoading] = useState(false);

  const [batchText, setBatchText] = useState(
    'How much should I score in Accounts?\nHow much should I score in Law?\nHow much should I score in Audit?'
  );
  const [batchResponses, setBatchResponses] = useState([]);
  const [batchError, setBatchError] = useState('');
  const [batchLoading, setBatchLoading] = useState(false);

  useEffect(() => {
    const checkBackendHealth = async () => {
      try {
        const { data } = await axios.get(getApiUrl('/api/health'));
        setHealth({
          loading: false,
          error: '',
          data,
        });
      } catch (error) {
        setHealth({
          loading: false,
          error: error.response?.data?.error ?? error.message ?? 'Backend is unreachable.',
          data: null,
        });
      }
    };

    checkBackendHealth();
  }, []);

  const handleSingleSubmit = async (event) => {
    event.preventDefault();
    setSingleLoading(true);
    setSingleError('');

    try {
      const { data } = await axios.post(getApiUrl('/api/ask'), {
        userInput: singleInput,
      });
      setSingleResponse(data.response ?? '');
    } catch (error) {
      setSingleError(error.response?.data?.error ?? 'Unable to fetch the single response.');
      setSingleResponse('');
    } finally {
      setSingleLoading(false);
    }
  };

  const handleBatchSubmit = async (event) => {
    event.preventDefault();
    setBatchLoading(true);
    setBatchError('');

    const userInputs = batchText
      .split('\n')
      .map((item) => item.trim())
      .filter(Boolean);

    try {
      const { data } = await axios.post(getApiUrl('/api/ask/batch'), {
        userInputs,
      });
      setBatchResponses(data.responses ?? []);
    } catch (error) {
      setBatchError(error.response?.data?.error ?? 'Unable to fetch batch responses.');
      setBatchResponses([]);
    } finally {
      setBatchLoading(false);
    }
  };

  return (
    <main className="app-shell">
      <section className="hero">
        <p className="eyebrow">Flask + MongoDB + OpenAI</p>
        <h1>Education Prompt API Tester</h1>
        <p className="hero-copy">
          This React page talks to the Flask backend and lets you test both the single-question and
          batch-question endpoints.
        </p>
        <p className="endpoint-note">API base URL: {API_BASE_URL || '(same origin via Vite proxy)'}</p>
      </section>

      <section className="status-strip">
        <article className={`status-card ${health.error ? 'status-card-error' : 'status-card-ok'}`}>
          <div>
            <p className="status-label">Backend status</p>
            <h2>
              {health.loading ? 'Checking...' : health.error ? 'Connection failed' : 'Connected'}
            </h2>
          </div>
          <p className="status-copy">
            {health.loading
              ? 'Flask API health endpoint ko ping kiya ja raha hai.'
              : health.error
                ? health.error
                : `MongoDB: ${health.data?.mongoDb} | Model: ${health.data?.model}`}
          </p>
          {!health.loading && !health.error ? (
            <p className="status-meta">Health endpoint: {getApiUrl('/api/health')}</p>
          ) : null}
        </article>
      </section>

      <section className="panel-grid">
        <article className="panel">
          <div className="panel-header">
            <h2>Single request</h2>
            <span>POST /api/ask</span>
          </div>

          <form onSubmit={handleSingleSubmit} className="form-stack">
            <label htmlFor="singleInput">userInput</label>
            <textarea
              id="singleInput"
              value={singleInput}
              onChange={(event) => setSingleInput(event.target.value)}
              rows="5"
              placeholder="Ask one education-related question"
            />
            <button type="submit" disabled={singleLoading}>
              {singleLoading ? 'Thinking...' : 'Send single request'}
            </button>
          </form>

          <div className="result-box">
            <h3>Response</h3>
            {singleError ? <p className="error-text">{singleError}</p> : <p>{singleResponse || 'No response yet.'}</p>}
          </div>
        </article>

        <article className="panel">
          <div className="panel-header">
            <h2>Batch request</h2>
            <span>POST /api/ask/batch</span>
          </div>

          <form onSubmit={handleBatchSubmit} className="form-stack">
            <label htmlFor="batchText">userInputs</label>
            <textarea
              id="batchText"
              value={batchText}
              onChange={(event) => setBatchText(event.target.value)}
              rows="8"
              placeholder="One prompt per line"
            />
            <button type="submit" disabled={batchLoading}>
              {batchLoading ? 'Running batch...' : 'Send batch request'}
            </button>
          </form>

          <div className="result-box">
            <h3>Responses</h3>
            {batchError ? (
              <p className="error-text">{batchError}</p>
            ) : batchResponses.length ? (
              <ol className="response-list">
                {batchResponses.map((response, index) => (
                  <li key={`${index}-${response.slice(0, 20)}`}>{response}</li>
                ))}
              </ol>
            ) : (
              <p>No responses yet.</p>
            )}
          </div>
        </article>
      </section>
    </main>
  );
}

export default App;
