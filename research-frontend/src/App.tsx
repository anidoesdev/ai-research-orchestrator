import React, { useState} from 'react'
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

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const newUserMessage = {role: "user", text: userQuery};
    setHistory(prevHistory => [...prevHistory,newUserMessage]);
    try{
      
      const response = await fetch(`http://127.0.0.1:8000/trigger-research?query=${userQuery}`);
      const data = await response.json();

      const newAgentMessage = {role: "agent",text: data.result};
      setHistory(prevHistory => [...prevHistory,newAgentMessage]);

      setUserQuery("");
      
    } catch(err){
      console.log("this is the error: " ,err);
    }
  }
  async function handleFetch(e: React.FormEvent){
    e.preventDefault()
    setIsIngesting(true);
    try{
      await fetch(`http://127.0.0.1:8000/fetch-papers?topic=${topicQuery}`)
      setIsIngesting(false);
      setTopicQuery("")

    }catch (err){
      console.log("Here is the error in reasearch topic: ",err)
    }
  }
  
  return (
    <div className='chat-container'>
      <div>
        {history.map((msg, index)=>(
          <div key={index} style={{margin: "10px",padding:"10px",border:"1px solid gray"}}>
            <strong>{msg.role.toUpperCase()}:</strong>
            <span>{msg.text}</span>
          </div>
        ))}
      </div>
      <form onSubmit={handleFetch}>
        <label>What topic you wanna research about?</label>
        <input type='text' value={topicQuery} onChange={(e)=>setTopicQuery(e.target.value)}></input>
        <button disabled={isIngesting}>{isIngesting ? "Downloading Papers..." : "Fetched Papers"}</button>
      </form>
      <form onSubmit={handleSubmit}>
        <label>enter your query</label>
        <input type='text' value={userQuery} onChange={(e)=>setUserQuery(e.target.value)}></input>
        <button>Submit</button>
      </form>
    </div>
  )
}

export default App
