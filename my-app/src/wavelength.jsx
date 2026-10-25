import React, { useState } from "react";
import { Copy, Check, Loader2 } from "lucide-react";

const INTENSITY_CONFIG = {
  light: {
    label: "Light touch",
    angle: 150,
    instruction:
      "Make the lightest edit that removes obvious AI phrasing. Keep sentence structure and word choice close to the original wherever it already sounds like a real person wrote it.",
  },
  natural: {
    label: "Natural",
    angle: 90,
    instruction:
      "Make a moderate, natural edit. Rework phrasing and rhythm where it sounds AI-drafted, but keep it clearly the same piece of writing.",
  },
  thorough: {
    label: "Full rewrite",
    angle: 30,
    instruction:
      "Rewrite as thoroughly as needed to fully shake off AI phrasing patterns and rhythm, while keeping every fact, claim, and the original intent completely unchanged.",
  },
};

export default function Wavelength() {
  const [inputText, setInputText] = useState("");
  const [voiceNotes, setVoiceNotes] = useState("");
  const [showVoiceNotes, setShowVoiceNotes] = useState(false);
  const [intensity, setIntensity] = useState("natural");
  const [outputText, setOutputText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [beforeScore, setBeforeScore] = useState(null);
  const [afterScore, setAfterScore] = useState(null);
  const [checkingBefore, setCheckingBefore] = useState(false);

  const angle = INTENSITY_CONFIG[intensity].angle;
  const rotation = 90 - angle;

  async function analyzeText(text) {
    const analyzePrompt = [
      "You analyze a short passage and estimate how AI-typical its phrasing and rhythm read, based on patterns common in AI-drafted writing: uniform sentence length, throat-clearing openers, hedging, robotic transitions, listy structure inside prose, and unusually polished vocabulary, versus natural personal writing: varied rhythm, contractions, specific idiosyncratic detail, occasional fragments.",
      "This is a rough style estimate, not a real AI-detection system, and it should not claim otherwise.",
      "",
      "Respond with ONLY valid JSON, no markdown fences, no commentary, in exactly this shape:",
      '{"score": <integer 0-100, 100 means strongly reads as AI-typical, 0 means strongly reads as natural personal writing>, "reasons": [<1 to 3 short phrases, each under 8 words, naming a specific pattern you noticed>]}',
    ].join("\n");

    const response = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "claude-sonnet-4-6",
        max_tokens: 1000,
        system: analyzePrompt,
        messages: [{ role: "user", content: text }],
      }),
    });

    if (!response.ok) throw new Error("Analysis failed");
    const data = await response.json();
    const raw = (data.content || [])
      .map((block) => (block.type === "text" ? block.text : ""))
      .join("")
      .trim()
      .replace(/^```json/i, "")
      .replace(/^```/, "")
      .replace(/```$/, "")
      .trim();

    const parsed = JSON.parse(raw);
    const score = Math.max(0, Math.min(100, Math.round(parsed.score)));
    const reasons = Array.isArray(parsed.reasons) ? parsed.reasons.slice(0, 3) : [];
    return { score, reasons };
  }

  async function handleCheckDraft() {
    if (!inputText.trim()) return;
    setCheckingBefore(true);
    try {
      const result = await analyzeText(inputText);
      setBeforeScore(result);
    } catch (err) {
      setBeforeScore(null);
    } finally {
      setCheckingBefore(false);
    }
  }

  async function handleTune() {
    if (!inputText.trim()) return;
    setLoading(true);
    setError("");
    setOutputText("");
    setAfterScore(null);
    setCopied(false);

    const systemPrompt = [
      "You are helping someone reclaim their own voice in a piece of writing they drafted with AI assistance.",
      "Rewrite the text so it reads as natural, personal writing, the way this person would actually write it themselves.",
      "",
      "Rules:",
      "- Preserve the exact meaning, facts, claims, and intent. Never add, remove, or change any factual content.",
      "- Preserve the author's apparent personality and tone (casual, blunt, warm, dry, whatever the original suggests). Don't flatten it into something generic.",
      "- Strip telltale AI patterns: throat-clearing openers, over-hedging, robotic transitions like 'furthermore' or 'in conclusion', excessive em dashes, uniform sentence rhythm, listy parallel structure inside prose, and unnaturally polished word choice.",
      "- Introduce the small irregularities of real human writing: varied sentence length, the occasional fragment, plain word choice over 'elevated' vocabulary, contractions where natural.",
      "- This is often short-form writing such as comments, replies, messages, and social posts, where one clunky phrase stands out. Don't pad or lengthen it.",
      INTENSITY_CONFIG[intensity].instruction,
      voiceNotes.trim()
        ? `The author described their own voice like this: "${voiceNotes.trim()}". Match it.`
        : "",
      "",
      "Output ONLY the rewritten text. No preamble, no explanation, no quotation marks around it.",
    ]
      .filter(Boolean)
      .join("\n");

    try {
      const rewritePromise = fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "claude-sonnet-4-6",
          max_tokens: 1000,
          system: systemPrompt,
          messages: [{ role: "user", content: inputText }],
        }),
      });

      const [response, before] = await Promise.all([
        rewritePromise,
        beforeScore ? Promise.resolve(beforeScore) : analyzeText(inputText).catch(() => null),
      ]);
      setBeforeScore(before);

      if (!response.ok) throw new Error("Request failed");
      const data = await response.json();
      const text = (data.content || [])
        .map((block) => (block.type === "text" ? block.text : ""))
        .join("")
        .trim();

      if (!text) throw new Error("Empty response");
      setOutputText(text);

      analyzeText(text)
        .then(setAfterScore)
        .catch(() => setAfterScore(null));
    } catch (err) {
      setError("Couldn't tune that just now. Give it another try.");
    } finally {
      setLoading(false);
    }
  }

  function handleCopy() {
    if (!outputText) return;
    navigator.clipboard?.writeText(outputText).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }

  return (
    <div className="wl-root">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600&family=IBM+Plex+Mono:wght@400;500&display=swap');

        .wl-root {
          --bg: #12161D;
          --panel: #1B212B;
          --panel-border: #2A3240;
          --text: #EDE7D8;
          --text-muted: #8D96A6;
          --accent-human: #E3A73B;
          --accent-ai: #5B7A99;
          --warn: #C1443C;

          background: var(--bg);
          color: var(--text);
          font-family: 'Source Serif 4', Georgia, serif;
          min-height: 100%;
          padding: 40px 20px 56px;
          display: flex;
          justify-content: center;
          box-sizing: border-box;
        }

        .wl-root *, .wl-root *::before, .wl-root *::after {
          box-sizing: border-box;
        }

        .wl-container {
          width: 100%;
          max-width: 560px;
        }

        .wl-header {
          text-align: center;
          margin-bottom: 8px;
        }

        .wl-title {
          font-size: clamp(28px, 5vw, 36px);
          font-weight: 600;
          letter-spacing: -0.01em;
          margin: 0;
        }

        .wl-subtitle {
          color: var(--text-muted);
          font-size: 15px;
          margin: 10px auto 0;
          max-width: 380px;
          line-height: 1.55;
        }

        .wl-dial-wrap {
          display: flex;
          flex-direction: column;
          align-items: center;
          margin: 28px 0 8px;
        }

        .wl-needle {
          transform-origin: 100px 100px;
          transition: transform 0.5s cubic-bezier(.4,1.4,.4,1);
        }

        .wl-loading .wl-needle {
          animation: wl-sweep 1.1s ease-in-out infinite;
        }

        @keyframes wl-sweep {
          0%, 100% { transform: rotate(calc(var(--rot) - 10deg)); }
          50% { transform: rotate(calc(var(--rot) + 10deg)); }
        }

        .wl-intensity-row {
          display: flex;
          gap: 8px;
          margin-top: 14px;
          flex-wrap: wrap;
          justify-content: center;
        }

        .wl-intensity-btn {
          font-family: 'IBM Plex Mono', ui-monospace, monospace;
          font-size: 12px;
          letter-spacing: 0.02em;
          background: transparent;
          border: 1px solid var(--panel-border);
          color: var(--text-muted);
          padding: 7px 12px;
          border-radius: 4px;
          cursor: pointer;
          transition: border-color 0.2s, color 0.2s, background 0.2s;
        }

        .wl-intensity-btn:hover {
          border-color: var(--accent-human);
          color: var(--text);
        }

        .wl-intensity-btn.active {
          background: rgba(227, 167, 59, 0.12);
          border-color: var(--accent-human);
          color: var(--accent-human);
        }

        .wl-panel {
          background: var(--panel);
          border: 1px solid var(--panel-border);
          border-radius: 4px;
          padding: 18px;
          margin-top: 18px;
        }

        .wl-panel-label {
          font-family: 'IBM Plex Mono', ui-monospace, monospace;
          font-size: 11px;
          color: var(--text-muted);
        }

        .wl-panel-label-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
          margin-bottom: 10px;
        }

        .wl-check-btn {
          font-family: 'IBM Plex Mono', ui-monospace, monospace;
          font-size: 11px;
          color: var(--accent-ai);
          background: none;
          border: none;
          cursor: pointer;
          padding: 0;
        }

        .wl-check-btn:hover:not(:disabled) {
          color: var(--text);
        }

        .wl-check-btn:disabled {
          opacity: 0.5;
          cursor: default;
        }

        .wl-badge-wrap {
          margin-bottom: 12px;
        }

        .wl-badge {
          display: inline-block;
          font-family: 'IBM Plex Mono', ui-monospace, monospace;
          font-size: 12px;
          border: 1px solid;
          border-radius: 3px;
          padding: 3px 8px;
        }

        .wl-badge-reasons {
          font-family: 'IBM Plex Mono', ui-monospace, monospace;
          font-size: 11px;
          color: var(--text-muted);
          margin-top: 6px;
          line-height: 1.5;
        }

        .wl-textarea {
          width: 100%;
          min-height: 140px;
          background: transparent;
          border: none;
          outline: none;
          resize: vertical;
          color: var(--text);
          font-family: 'Source Serif 4', Georgia, serif;
          font-size: 16px;
          line-height: 1.6;
        }

        .wl-textarea::placeholder {
          color: #545E6E;
        }

        .wl-voice-toggle {
          font-family: 'IBM Plex Mono', ui-monospace, monospace;
          font-size: 12px;
          color: var(--accent-ai);
          background: none;
          border: none;
          cursor: pointer;
          padding: 4px 0;
          margin-top: 4px;
        }

        .wl-voice-toggle:hover {
          color: var(--text);
        }

        .wl-voice-textarea {
          width: 100%;
          min-height: 56px;
          background: transparent;
          border: 1px dashed var(--panel-border);
          border-radius: 4px;
          outline: none;
          resize: vertical;
          color: var(--text);
          font-family: 'Source Serif 4', Georgia, serif;
          font-size: 14px;
          line-height: 1.5;
          padding: 10px;
          margin-top: 8px;
        }

        .wl-action-row {
          display: flex;
          justify-content: center;
          margin-top: 22px;
        }

        .wl-tune-btn {
          font-family: 'IBM Plex Mono', ui-monospace, monospace;
          font-size: 13px;
          letter-spacing: 0.02em;
          background: var(--accent-human);
          color: #1A1305;
          border: none;
          padding: 12px 28px;
          border-radius: 4px;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 8px;
          transition: opacity 0.2s, transform 0.1s;
        }

        .wl-tune-btn:hover:not(:disabled) {
          opacity: 0.9;
        }

        .wl-tune-btn:active:not(:disabled) {
          transform: scale(0.98);
        }

        .wl-tune-btn:disabled {
          opacity: 0.5;
          cursor: default;
        }

        .wl-spin {
          animation: wl-rotate 0.8s linear infinite;
        }

        @keyframes wl-rotate {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        .wl-error {
          text-align: center;
          color: var(--warn);
          font-family: 'IBM Plex Mono', ui-monospace, monospace;
          font-size: 13px;
          margin-top: 14px;
        }

        .wl-output-panel {
          border-color: var(--accent-human);
        }

        .wl-output-text {
          font-size: 16px;
          line-height: 1.65;
          white-space: pre-wrap;
          margin: 0;
        }

        .wl-copy-btn {
          display: flex;
          align-items: center;
          gap: 6px;
          font-family: 'IBM Plex Mono', ui-monospace, monospace;
          font-size: 12px;
          background: none;
          border: 1px solid var(--panel-border);
          color: var(--text-muted);
          padding: 6px 10px;
          border-radius: 4px;
          cursor: pointer;
          flex-shrink: 0;
          transition: border-color 0.2s, color 0.2s;
        }

        .wl-copy-btn:hover {
          border-color: var(--accent-human);
          color: var(--accent-human);
        }

        .wl-footnote {
          text-align: center;
          font-family: 'IBM Plex Mono', ui-monospace, monospace;
          font-size: 11.5px;
          color: var(--text-muted);
          line-height: 1.6;
          margin-top: 32px;
        }
      `}</style>

      <div className="wl-container">
        <div className="wl-header">
          <h1 className="wl-title">Wavelength</h1>
          <p className="wl-subtitle">
            Paste writing you drafted with AI help and get it back in your own voice: same meaning, same facts, still sounds like you.
          </p>
        </div>

        <div className={`wl-dial-wrap ${loading ? "wl-loading" : ""}`} style={{ "--rot": `${rotation}deg` }}>
          <svg width="200" height="118" viewBox="0 0 200 118">
            <defs>
              <linearGradient id="wl-arc-grad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="var(--accent-ai)" />
                <stop offset="100%" stopColor="var(--accent-human)" />
              </linearGradient>
            </defs>
            <path
              d="M 20 100 A 80 80 0 0 1 180 100"
              fill="none"
              stroke="url(#wl-arc-grad)"
              strokeWidth="3"
              strokeLinecap="round"
              opacity="0.55"
            />
            {[150, 90, 30].map((a) => {
              const rad = (a * Math.PI) / 180;
              const x1 = 100 + 68 * Math.cos(rad);
              const y1 = 100 - 68 * Math.sin(rad);
              const x2 = 100 + 78 * Math.cos(rad);
              const y2 = 100 - 78 * Math.sin(rad);
              return (
                <line
                  key={a}
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  stroke="var(--panel-border)"
                  strokeWidth="2"
                />
              );
            })}
            <line
              className="wl-needle"
              x1="100"
              y1="100"
              x2="100"
              y2="38"
              stroke="var(--text)"
              strokeWidth="2.5"
              strokeLinecap="round"
              style={{ transform: `rotate(${rotation}deg)` }}
            />
            <circle cx="100" cy="100" r="5" fill="var(--accent-human)" />
          </svg>

          <div className="wl-intensity-row">
            {Object.entries(INTENSITY_CONFIG).map(([key, cfg]) => (
              <button
                key={key}
                className={`wl-intensity-btn ${intensity === key ? "active" : ""}`}
                onClick={() => setIntensity(key)}
                type="button"
              >
                {cfg.label}
              </button>
            ))}
          </div>
        </div>

        <div className="wl-panel">
          <div className="wl-panel-label-row">
            <span className="wl-panel-label">your draft</span>
            <button
              className="wl-check-btn"
              type="button"
              onClick={handleCheckDraft}
              disabled={checkingBefore || !inputText.trim()}
            >
              {checkingBefore ? "checking…" : "check reading"}
            </button>
          </div>
          {beforeScore && (
            <div className="wl-badge-wrap">
              <span
                className="wl-badge"
                style={{
                  borderColor:
                    beforeScore.score >= 66
                      ? "var(--accent-ai)"
                      : beforeScore.score <= 33
                      ? "var(--accent-human)"
                      : "var(--text-muted)",
                  color:
                    beforeScore.score >= 66
                      ? "var(--accent-ai)"
                      : beforeScore.score <= 33
                      ? "var(--accent-human)"
                      : "var(--text-muted)",
                }}
              >
                {beforeScore.score}%{" "}
                {beforeScore.score >= 66
                  ? "AI-typical"
                  : beforeScore.score <= 33
                  ? "natural"
                  : "mixed"}
              </span>
              {beforeScore.reasons.length > 0 && (
                <div className="wl-badge-reasons">{beforeScore.reasons.join(", ")}</div>
              )}
            </div>
          )}
          <textarea
            className="wl-textarea"
            placeholder="Paste the comment, reply, or message here."
            value={inputText}
            onChange={(e) => {
              setInputText(e.target.value);
              setBeforeScore(null);
              setAfterScore(null);
            }}
          />
          <button
            className="wl-voice-toggle"
            type="button"
            onClick={() => setShowVoiceNotes((v) => !v)}
          >
            {showVoiceNotes ? "− hide voice notes" : "+ describe your voice (optional)"}
          </button>
          {showVoiceNotes && (
            <textarea
              className="wl-voice-textarea"
              placeholder="e.g. I'm blunt, I write in lowercase, I never use exclamation points, I swear occasionally."
              value={voiceNotes}
              onChange={(e) => setVoiceNotes(e.target.value)}
            />
          )}
        </div>

        <div className="wl-action-row">
          <button
            className="wl-tune-btn"
            onClick={handleTune}
            disabled={loading || !inputText.trim()}
            type="button"
          >
            {loading ? (
              <>
                <Loader2 size={15} className="wl-spin" />
                tuning
              </>
            ) : (
              "tune to my voice"
            )}
          </button>
        </div>

        {error && <div className="wl-error">{error}</div>}

        {outputText && (
          <div className="wl-panel wl-output-panel">
            <div className="wl-panel-label-row">
              <span className="wl-panel-label">in your voice</span>
              <button className="wl-copy-btn" onClick={handleCopy} type="button">
                {copied ? <Check size={13} /> : <Copy size={13} />}
                {copied ? "copied" : "copy"}
              </button>
            </div>
            {afterScore && (
              <div className="wl-badge-wrap">
                <span
                  className="wl-badge"
                  style={{
                    borderColor:
                      afterScore.score >= 66
                        ? "var(--accent-ai)"
                        : afterScore.score <= 33
                        ? "var(--accent-human)"
                        : "var(--text-muted)",
                    color:
                      afterScore.score >= 66
                        ? "var(--accent-ai)"
                        : afterScore.score <= 33
                        ? "var(--accent-human)"
                        : "var(--text-muted)",
                  }}
                >
                  {afterScore.score}%{" "}
                  {afterScore.score >= 66
                    ? "AI-typical"
                    : afterScore.score <= 33
                    ? "natural"
                    : "mixed"}
                </span>
                {afterScore.reasons.length > 0 && (
                  <div className="wl-badge-reasons">{afterScore.reasons.join(", ")}</div>
                )}
              </div>
            )}
            <p className="wl-output-text">{outputText}</p>
          </div>
        )}

        <div className="wl-footnote">
          Wavelength keeps your meaning and facts intact.
          <br />
          The reading score is a rough style estimate from Claude, not a real
          detector. Turnitin, GPTZero, and similar services use their own
          closed models and may score the same text differently.
        </div>
      </div>
    </div>
  );
}
