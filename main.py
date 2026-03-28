from fastapi import FastAPI,Request
from contextlib import asynccontextmanager
from sentence_transformers import SentenceTransformer
import asyncpg
import redis.asyncio as redis
import asyncio
from fastapi.middleware.cors import CORSMiddleware 
import os 
from dotenv import load_dotenv
# from groq import AsyncGroq
from model import llm

# load_dotenv()
# groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

model = SentenceTransformer("all-MiniLM-L6-v2")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global task_queue, result_queue, db_pool
    task_queue = asyncio.Queue()
    result_queue = asyncio.Queue()
    db_pool = None

    try:
        db_pool = await asyncpg.create_pool(user="admin",password="postpass",database="research_memory",host="127.0.0.1",port=5432)
        # connected_postgres = await asyncpg.connect(user="admin",password="postpass",database="research_memory",host="127.0.0.1",port=5432)
        print("database connection pool created")
        async with db_pool.acquire() as conn:
            await conn.execute('CREATE EXTENSION IF NOT EXISTS vector')
            await conn.execute('DROP TABLE IF EXISTS research_papers')
            await conn.execute('''
                    CREATE TABLE research_papers(
                        id SERIAL PRIMARY KEY,
                        title TEXT,
                        content TEXT,
                        embedding vector(384)
                    )
                               ''')
            print("Vector table initialized")
            print("Ingecting knowledge into memory banks")
            papers = [
                ("Quantum Topology", "Topological qubits utilize non-Abelian anyons to achieve fault-tolerant quantum computation."),
                ("AI Transformers", "Transformer architectures rely on self-attention mechanisms to process sequential data in parallel, eliminating the need for recurrent loops."),
                ("CRISPR Gene Editing", "Cas9 proteins use guide RNA to locate and cleave specific DNA sequences, allowing for highly targeted genetic modifications.")
            ]
            for title,content in papers:
                vec = model.encode(content).tolist()
                await conn.execute(
                    "insert into research_papers (title, content, embedding) values ($1, $2, $3)",
                    title, content, str(vec)
                )
            print("Memory banks fully populated.")
        # await connected_postgres.execute('CREATE EXTENSION IF NOT EXISTS vector')
        # await connected_postgres.execute('DROP TABLE IF EXISTS research_papers')
        # await connected_postgres.execute('''
        #     CREATE TABLE IF NOT EXISTS research_papers(
        #         id SERIAL PRIMARY KEY,
        #         title TEXT,
        #         content TEXT,
        #         embedding vector(384)
        #     )
        # '''
        # )
        
        client = redis.from_url("redis://localhost:6379")
        if await client.ping():
                print("Connected to Redis")
        asyncio.create_task(research_worker())
        yield
        await db_pool.close()
        
    except Exception as e:
        print(f"this is the error: {e}")
        yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_methods=["*"]
)

async def research_worker():
   while True:
        try:
            task = await task_queue.get()
            task_vector = model.encode(task).tolist()
            print(f"Worker: Researching {task}")
            async with db_pool.acquire() as conn:
                record = await conn.fetch(
                    '''SELECT TITLE, CONTENT FROM research_papers ORDER BY embedding <=> $1 LIMIT 3''',
                    str(task_vector)
                )
            if not record:
                await result_queue.put("Agent Warning: No relevant research found in the memory banks.")
                continue
            context_string = "\n\n".join([f"Source: {r['title']}\nData: {r['content']}" for r in record])
            groq_prompt = f"""
                You are an elite scientific research synthesizer. 
            The user asked: "{task}"
            
            Read the following research papers and write a brilliant, generalized summary answering their question. 
            Do NOT use outside knowledge. Rely ONLY on this provided context:
            
            {context_string}
            """
            text_response = await llm.ainvoke(
                [
                    {"role": "system", "content": "You are a precise and highly technical AI research agent."},
                    {"role": "user", "content": groq_prompt}
                ]
            )
            await result_queue.put(text_response.content)
        except Exception as e:
            await result_queue.put(f"Agent Warning: No relevant research found in the memory banks.")
            print(f"worker error: {e}")
        finally:
            task_queue.task_done()
        
@app.get("/trigger-research")
async def trigger_research(query:str):
    # title = "Quantum Topology Overview"
    # content = "Topological qubits utilize non-Abelian anyons to achieve fault-tolerant quantum computation."
    
    # vector = model.encode(content).tolist()
    # async with db_pool.acquire() as conn:
    #     await conn.execute(
    #         '''INSERT INTO research_papers (title,content,embedding) VALUES ($1, $2, $3)''',
    #         title,
    #         content,
    #         str(vector)
    #     )
    await task_queue.put(query)
    result = await result_queue.get()
    # return {
    #     "status":"Success",
    #     "message":"Research paper successfully embedded and saved to Postgres!",
    #     "dimension_saved": len(vector)
    # }
    return {"result":result}
        
    # sample_text = "Topological qubits utilize non-Abelian anyons to achieve fault-tolerant quantum computation."
    # vector = model.encode(sample_text).tolist()
    # return {"status":"Complete","preview_vector":
    # vector[:5],"total_dimensions": len(vector)}
    


@app.get('/search-research')
async def search_research(query:str,request:Request):
    query_vector = model.encode(query).tolist()
    async with db_pool.acquire() as conn:
        record = await conn.fetchrow(
            '''SELECT TITLE, CONTENT FROM research_papers ORDER BY embedding <=> $1 LIMIT 1''',
            str(query_vector)
        )
    return {"title":record['title'],"content":record['content']}


    


  




       
       
       
