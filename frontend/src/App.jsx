import { useEffect, useRef, useState } from "react";

const starterMessage = {
  role: "assistant",
  text: "Ask me about Summoner's Rift champion, item, rune, or system changes.",
  sources: [],
};

function SourceList({ sources }) {
  if (!sources.length) return null;

  return (
    <div className="sources">
      <p className="sources-title">Sources</p>
      {sources.map((source) => (
        <a
          className="source"
          href={source.url || undefined}
          target="_blank"
          rel="noreferrer"
          key={source.patch}
        >
          {source.patch}
        </a>
      ))}
    </div>
  );
}

function App() {
  const [messages, setMessages] = useState([starterMessage]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const conversationEnd = useRef(null);

  useEffect(() => {
    conversationEnd.current?.scrollIntoView({
      behavior: "smooth",
      block: "end",
    });
  }, [messages, loading]);

  async function sendQuestion(event) {
    event.preventDefault();

    const cleanQuestion = question.trim();
    if (!cleanQuestion || loading) return;

    setMessages((current) => [
      ...current,
      { role: "user", text: cleanQuestion, sources: [] },
    ]);
    setQuestion("");
    setLoading(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: cleanQuestion }),
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Request failed.");

      setMessages((current) => [
        ...current,
        { role: "assistant", text: data.answer, sources: data.sources },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        { role: "assistant", text: `Error: ${error.message}`, sources: [] },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page-shell">
      <section className="chat-panel">
        <div className="messages" aria-live="polite">
          {messages.map((message, index) => (
            <article className={`message ${message.role}`} key={index}>
              <p className="speaker">
                {message.role === "user" ? "The Summoner" : "The Herald"}
              </p>
              <div className="bubble">{message.text}</div>
              <SourceList sources={message.sources} />
            </article>
          ))}

          {loading && (
            <article className="message assistant">
              <p className="speaker">The Herald</p>
              <div className="bubble thinking">
                Searching the archive<span>.</span><span>.</span><span>.</span>
              </div>
            </article>
          )}

          <div ref={conversationEnd} />
        </div>

        <form className="composer" onSubmit={sendQuestion}>
          <label className="screen-reader-only" htmlFor="question">
            Ask about a patch change
          </label>
          <div className="input-row">
            <input
              id="question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask about a patch change..."
              autoComplete="off"
            />
            <button
              aria-label="Send question"
              disabled={loading || !question.trim()}
              type="submit"
            >
              ↑
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}

export default App;
