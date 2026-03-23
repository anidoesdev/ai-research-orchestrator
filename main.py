from fastapi import FastAPI,Request
from contextlib import asynccontextmanager
from sentence_transformers import SentenceTransformer
import asyncpg
import redis.asyncio as redis
import asyncio
from fastapi.middleware.cors import CORSMiddleware 


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
                record = await conn.fetchrow(
                    '''SELECT TITLE, CONTENT FROM research_papers ORDER BY embedding <=> $1 LIMIT 1''',
                    str(task_vector)
                )
            # raise ValueError("The AI API crashed!")
            await result_queue.put(f"Agent Synthesis Complete: The most relevant context for '{task}' is the paper '{record['title']}'. Core findings: {record['content']} ")
        except Exception as e:
            await result_queue.put(f"Agent Warning: No relevant research found in the memory banks.")
            print(f"worker error: {e}")
        finally:
            task_queue.task_done()
        
@app.get("/trigger-research")
async def trigger_research(query:str,request:Request):
    title = "Quantum Topology Overview"
    content = "Topological qubits utilize non-Abelian anyons to achieve fault-tolerant quantum computation."
    
    vector = model.encode(content).tolist()
    async with db_pool.acquire() as conn:
        await conn.execute(
            '''INSERT INTO research_papers (title,content,embedding) VALUES ($1, $2, $3)''',
            title,
            content,
            str(vector)
        )
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
    


  




       
       
       
