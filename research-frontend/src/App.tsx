import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import './App.css';

interface Message {
  role: string;
  text: string;
}

function App() {
  const [userQuery, setUserQuery] = useState("");
  const [history, setHistory] = useState<Message[]>([]);
  const [topicQuery, setTopicQuery] = useState("");
  const [isIngesting, setIsIngesting] = useState(false);
  const [isThinking, setIsThinking] = useState(false);  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  
  // Advanced smooth scroll that tracks the bottom perfectly
  const scrollToBottom = () => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  };
  
  useEffect(() => {
    scrollToBottom();
  }, [history, isThinking]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!userQuery.trim()) return;

    const queryText = userQuery;
    setUserQuery("");
    
    setHistory(prev => [...prev, { role: "user", text: queryText }]);
    const currentHistory = [...history,{role: "user", text: queryText}];
    
    setIsThinking(true);
    setHistory(prev => [...prev, { role: "agent", text: "" }]);

    try {
      const response = await fetch(`http://127.0.0.1:8000/trigger-research`,{
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({history: currentHistory})
      });
      if (!response.body) throw new Error("No response body");
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        
        setHistory(prev => {
          const newHistory = [...prev];
          const lastIndex = newHistory.length - 1;
          newHistory[lastIndex] = { 
            ...newHistory[lastIndex], 
            text: newHistory[lastIndex].text + chunk 
          };
          return newHistory;
        });
      }
      setIsThinking(false);
    } catch (err) {
      console.log("Chat error: ", err);
      setIsThinking(false);
    }
  }

  async function handleFetch(e: React.FormEvent) {
    e.preventDefault();
    if (!topicQuery.trim()) return;
    setIsIngesting(true);
    try {
      await fetch(`http://127.0.0.1:8000/fetch-papers?topic=${topicQuery}`);
    } catch (err) {
      console.log("Ingestion error: ", err);
    } finally {
      setIsIngesting(false);
      setTopicQuery("");
    }
  }

  return (
    // h-dvh guarantees it perfectly fits the screen on all devices
    <div className="flex h-dvh w-full bg-[#09090b] text-zinc-300 font-sans antialiased overflow-hidden selection:bg-zinc-800 selection:text-white">
      
      {/* LEFT SIDEBAR - Fixed width, strictly no stretching */}
      <aside className="w-80 shrink-0 bg-[#0a0a0c] border-r border-white/5 flex flex-col z-20">
        <div className="p-8 pb-6">
          <div className="flex items-center gap-3 mb-1">
            <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.4)]"></div>
            <h2 className="text-lg font-medium text-zinc-100 tracking-tight">Neural Vault</h2>
          </div>
          <p className="text-[10px] text-zinc-500 font-mono uppercase tracking-widest ml-5">arXiv Integration</p>
        </div>

        <div className="px-8 flex-1">
          {/* Active Ingestion UI vs Form UI */}
          {isIngesting ? (
            <div className="h-32 bg-zinc-900/40 border border-white/5 rounded-xl flex flex-col items-center justify-center gap-4">
              <div className="w-5 h-5 border-2 border-zinc-600 border-t-zinc-100 rounded-full animate-spin"></div>
              <p className="text-xs text-zinc-400 font-mono uppercase tracking-widest animate-pulse">Scraping arXiv...</p>
            </div>
          ) : (
            <form className="flex flex-col gap-4" onSubmit={handleFetch}>
              <div className="flex flex-col gap-2">
                <label className="text-[10px] font-semibold text-zinc-500 uppercase tracking-widest">
                  Knowledge Target
                </label>
                <input 
                  type="text" 
                  placeholder="e.g. Graph Networks"
                  value={topicQuery} 
                  onChange={(e) => setTopicQuery(e.target.value)}
                  className="bg-zinc-900/50 border border-white/5 rounded-lg px-4 py-3 text-sm text-zinc-200 focus:border-white/20 focus:bg-zinc-900 focus:ring-2 focus:ring-emerald-500/20 transition-all outline-none placeholder:text-zinc-600"
                />
              </div>
              <button 
                type="submit" 
                disabled={!topicQuery.trim()}
                className="px-4 py-3 rounded-lg font-medium text-sm transition-all duration-300 bg-zinc-100 hover:bg-white text-zinc-950 shadow-[0_0_15px_rgba(255,255,255,0.05)] disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
              >
                Initialize Context
              </button>
            </form>
          )}
        </div>
        
        <div className="p-8 border-t border-white/5 bg-[#09090b]">
           <p className="text-[10px] text-zinc-600 font-mono uppercase tracking-widest text-center">System v1.0.0</p>
        </div>
      </aside>

      {/* MAIN CHAT AREA - min-h-0 prevents flexbox from breaking out of the screen */}
      <main className="flex-1 flex flex-col relative bg-[#09090b] min-w-0 h-full">
        
        {/* Messages Container - Custom hidden scrollbar utility classes */}
        <div 
          ref={scrollContainerRef}
          className="flex-1 overflow-y-auto p-8 md:p-12 lg:px-24 flex flex-col gap-8 pb-40 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]"
        >
          {history.length === 0 ? (
            <div className="m-auto text-center max-w-sm opacity-60">
              <div className="w-10 h-10 rounded-xl border border-white/10 flex items-center justify-center mx-auto mb-6 bg-zinc-900/50">
                <span className="text-zinc-400 text-lg font-serif">✧</span>
              </div>
              <p className="text-sm text-zinc-400 font-light leading-relaxed">
                The vault is empty. Provide a target in the sidebar to begin synthesis.
              </p>
            </div>
          ) : (
            history.map((msg, index) => (
              <div key={index} className={`flex w-full ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] md:max-w-[75%] px-6 py-5 text-[0.95rem] font-light leading-relaxed transition-all ${
                  msg.role === 'user' 
                    ? 'bg-zinc-800/80 text-zinc-50 rounded-3xl rounded-tr-md shadow-sm ring-1 ring-white/5' 
                    : 'bg-zinc-900/40 text-zinc-200 rounded-3xl rounded-tl-md ring-1 ring-white/5'
                }`}>
                  {msg.role === 'agent' && (
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-4 h-4 rounded border border-white/10 flex items-center justify-center bg-zinc-900">
                        <span className="text-[8px] text-zinc-400">AI</span>
                      </div>
                      <span className="text-[10px] text-zinc-500 uppercase tracking-widest font-semibold">Agent Response</span>
                    </div>
                  )}
                  
                  {/* Markdown Container with Strict Typography */}
                  <div className={`prose prose-invert max-w-none prose-p:leading-7 prose-pre:bg-zinc-900/80 prose-pre:border prose-pre:border-white/5 prose-pre:rounded-xl prose-pre:p-4 prose-pre:overflow-x-auto prose-code:rounded-md prose-code:bg-zinc-900/60 prose-code:px-2 prose-code:py-0.5 prose-a:text-emerald-300 prose-a:underline prose-strong:text-zinc-100 prose-hr:border-white/10 ${msg.role === 'user' ? 'text-zinc-100' : 'text-zinc-300'}`}>
                     <ReactMarkdown
                       components={{
                        a: ({ node, ...props }: { node?: unknown } & React.ComponentPropsWithoutRef<'a'>) => {
                           void node;
                           return (
                             <a
                               {...props}
                               target="_blank"
                               rel="noreferrer"
                               className={
                                 props.className ??
                                 "underline decoration-emerald-400/40 underline-offset-4 hover:decoration-emerald-300"
                               }
                             />
                           );
                         },
                       }}
                     >
                       {msg.text}
                     </ReactMarkdown>
                  </div>
                </div>
              </div>
            ))
          )}
          
          {isThinking && (
            <div className="flex w-full justify-start">
               <div className="px-6 py-5 flex items-center gap-2">
                 <div className="w-4 h-4 rounded border border-white/10 flex items-center justify-center bg-zinc-900">
                    <span className="text-[8px] text-zinc-400">AI</span>
                  </div>
                 <div className="flex gap-1 pl-2">
                    <div className="w-1.5 h-1.5 bg-zinc-600 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                    <div className="w-1.5 h-1.5 bg-zinc-600 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                    <div className="w-1.5 h-1.5 bg-zinc-600 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                 </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} className="h-1" />
        </div>

        {/* Floating Input Area */}
        <div className="absolute bottom-0 w-full px-8 md:px-12 lg:px-24 pb-8 bg-gradient-to-t from-[#09090b] via-[#09090b] to-transparent pt-32 pointer-events-none">
          <form className="max-w-4xl mx-auto relative flex items-center pointer-events-auto" onSubmit={handleSubmit}>
            <input 
              type="text" 
              placeholder="Query the contextual vault..."
              value={userQuery} 
              onChange={(e) => setUserQuery(e.target.value)}
              disabled={isThinking}
              className="w-full bg-zinc-900/90 backdrop-blur-md border border-white/10 rounded-2xl pl-6 pr-24 py-4 text-sm text-zinc-200 focus:border-white/20 focus:bg-zinc-900 focus:ring-2 focus:ring-emerald-500/25 outline-none transition-all disabled:opacity-50 shadow-2xl"
            />
            <button 
              type="submit" 
              disabled={isThinking || !userQuery.trim()}
              className="absolute right-2 px-5 py-2 rounded-xl bg-zinc-100 hover:bg-white text-zinc-950 text-sm font-medium transition-all disabled:bg-zinc-800 disabled:text-zinc-600 disabled:cursor-not-allowed shadow-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
            >
              Send
            </button>
          </form>
        </div>

      </main>
    </div>
  );
}

export default App;