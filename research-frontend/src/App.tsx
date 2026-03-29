import React, { useEffect, useRef, useState} from 'react'
import './App.css'

interface Message {
  role: string;
  text: string;
}
function App() {
  const [userQuery,setUserQuery] = useState("");
  const [history,setHistory] = useState<Message[]>([]);
  const [topicQuery,setTopicQuery] = useState("");
  const [isIngesting,setIsIngesting] = useState(false);
  const [isThinking,setIsThinking] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollToBottom = () =>{
    messagesEndRef.current?.scrollIntoView({behavior: "smooth"})
  }
  useEffect(()=>{
    scrollToBottom();
  },[history,isThinking]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!userQuery.trim()) return;
    const newUserMessage = {role: "user", text: userQuery};
    setHistory(prevHistory => [...prevHistory,newUserMessage]);
    setUserQuery("");
    setIsThinking(true);
    try{
      
      const response = await fetch(`http://127.0.0.1:8000/trigger-research?query=${userQuery}`);
      const data = await response.json();

      const newAgentMessage = {role: "agent",text: data.result};
      setHistory(prevHistory => [...prevHistory,newAgentMessage]);
      
    } catch(err){
      console.log("this is the error: " ,err);
      setHistory(prevHistory => [...prevHistory,{role: "agent", text: "Error: Could not connect to the agent."}])
    } finally {
      setIsThinking(false);
    }
  }
  async function handleFetch(e: React.FormEvent){
    e.preventDefault()
    // if(!topicQuery.trim()) return;
    setIsIngesting(true);
    try{
      await fetch(`http://127.0.0.1:8000/fetch-papers?topic=${topicQuery}`)
    }catch (err){
      console.log("Here is the error in reasearch topic: ",err)
    }finally{
      setIsIngesting(false);
      setTopicQuery("")
    }
  }
  
  return (
    <div className="flex h-screen w-screen bg-[#09090b] text-zinc-300 overflow-hidden font-sans tracking-wide">
      
      {/* LEFT SIDEBAR: Minimalist Glass */}
      <aside className="w-80 bg-[#09090b] border-r border-white/5 p-8 flex flex-col z-10">
        <div className="mb-12">
          <h2 className="text-xl font-medium text-zinc-100 tracking-tight">Neural Vault</h2>
          <p className="text-xs text-zinc-500 mt-2 font-mono uppercase tracking-widest">arXiv Link</p>
        </div>

        <form className="flex flex-col gap-4" onSubmit={handleFetch}>
          <div className="flex flex-col gap-2">
            <label className="text-[10px] font-semibold text-zinc-500 uppercase tracking-widest">
              Knowledge Target
            </label>
            <input 
              type="text" 
              placeholder="e.g. Quantum Gravity"
              value={topicQuery} 
              onChange={(e) => setTopicQuery(e.target.value)}
              disabled={isIngesting}
              className="bg-zinc-900/50 border border-white/5 rounded-lg px-4 py-3 text-sm text-zinc-200 focus:border-white/20 focus:bg-zinc-900 transition-all outline-none disabled:opacity-50 placeholder:text-zinc-700"
            />
          </div>
          <button 
            type="submit" 
            disabled={isIngesting || !topicQuery.trim()}
            className={`px-4 py-3 rounded-lg font-medium text-sm transition-all duration-300 ${
              isIngesting 
                ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed animate-pulse' 
                : 'bg-zinc-100 hover:bg-white text-zinc-950 shadow-[0_0_15px_rgba(255,255,255,0.05)]'
            }`}
          >
            {isIngesting ? "Fetching Data..." : "Initialize"}
          </button>
        </form>
        
        <div className="mt-auto flex items-center text-[11px] font-medium text-zinc-500 tracking-wider">
          <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 mr-2 animate-pulse"></span>
          SYSTEM IDLE
        </div>
      </aside>

      {/* MAIN CHAT AREA */}
      <main className="flex-1 flex flex-col relative bg-[#09090b]">
        
        {/* Messages Container (Scrollable, but invisible scrollbar) */}
        <div className="flex-1 overflow-y-auto p-8 md:p-12 flex flex-col gap-8 pb-32">
          {history.length === 0 ? (
            <div className="m-auto text-center max-w-sm opacity-50">
              <div className="w-12 h-12 rounded-full border border-white/10 flex items-center justify-center mx-auto mb-6">
                <span className="text-zinc-500 text-lg font-serif">✧</span>
              </div>
              <p className="text-sm text-zinc-400 font-light leading-relaxed">
                Vault is empty. Provide a target on the left to begin synthesis.
              </p>
            </div>
          ) : (
            history.map((msg, index) => (
              <div key={index} className={`flex w-full ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[70%] px-6 py-4 text-[0.95rem] font-light leading-relaxed whitespace-pre-wrap transition-all ${
                  msg.role === 'user' 
                    ? 'bg-zinc-800 text-zinc-100 rounded-2xl rounded-tr-sm' 
                    : 'bg-transparent text-zinc-300 rounded-2xl'
                }`}>
                  {msg.role === 'agent' && <div className="text-[10px] text-zinc-600 uppercase tracking-widest mb-2 font-semibold">Agent Response</div>}
                  {msg.text}
                </div>
              </div>
            ))
          )}
          
          {isThinking && (
            <div className="flex w-full justify-start">
              <div className="max-w-[70%] px-6 py-4 text-zinc-500 text-[0.95rem] font-light italic animate-pulse">
                Synthesizing...
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area (Floating Glass Effect) */}
        <div className="absolute bottom-0 w-full p-8 bg-linear-to-t from-[#09090b] via-[#09090b] to-transparent pt-20 pointer-events-none">
          <form className="max-w-3xl mx-auto relative flex items-center pointer-events-auto" onSubmit={handleSubmit}>
            <input 
              type="text" 
              placeholder="Query the system..."
              value={userQuery} 
              onChange={(e) => setUserQuery(e.target.value)}
              disabled={isThinking}
              className="w-full bg-zinc-900/80 backdrop-blur-xl border border-white/10 rounded-2xl pl-6 pr-24 py-4 text-sm text-zinc-200 focus:border-white/30 outline-none transition-all disabled:opacity-50 shadow-2xl shadow-black"
            />
            <button 
              type="submit" 
              disabled={isThinking || !userQuery.trim()}
              className="absolute right-2 px-5 py-2 rounded-xl bg-zinc-100 hover:bg-white text-zinc-950 text-sm font-medium transition-all disabled:bg-zinc-800 disabled:text-zinc-600 disabled:cursor-not-allowed"
            >
              Send
            </button>
          </form>
        </div>

      </main>
    </div>
  );
}

export default App
