import os
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from sentence_transformers import SentenceTransformer
import asyncpg
import redis.asyncio as redis
import asyncio
from fastapi.middleware.cors import CORSMiddleware 
from model import llm
import arxiv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel
from typing import List, Optional

class Message(BaseModel):
    role: str
    text: str

class ChatRequest(BaseModel):
    history: List[Message]

DB_USER = os.getenv("PG_USER", "admin")
DB_PASSWORD = os.getenv("PG_PASSWORD", "postpass")
DB_NAME = os.getenv("PG_DB", "research_memory")
DB_HOST = os.getenv("PG_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("PG_PORT", "5432"))

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SENTENCE_TRANSFORMER_MODEL = os.getenv("SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))

model = SentenceTransformer(SENTENCE_TRANSFORMER_MODEL)


async def embed_text(text: str) -> List[float]:
    # SentenceTransformer encoding is CPU/GPU bound; keep the event loop responsive.
    vec = await asyncio.to_thread(model.encode, text)
    return vec.tolist()

@asynccontextmanager
async def lifespan(app: FastAPI):
    ingestion_task: Optional[asyncio.Task] = None

    app.state.db_pool = None
    app.state.redis_client = None

    try:
        app.state.db_pool = await asyncpg.create_pool(
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            host=DB_HOST,
            port=DB_PORT,
        )
        print("database connection pool created")

        async with app.state.db_pool.acquire() as conn:
            await conn.execute('CREATE EXTENSION IF NOT EXISTS vector')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS research_papers(
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding vector(%d)
                )
                ''' % EMBEDDING_DIM
            )
            print("Vector table initialized")

        app.state.redis_client = redis.from_url(REDIS_URL)
        if await app.state.redis_client.ping():
            print("Connected to Redis")

        ingestion_task = asyncio.create_task(ingestion_worker(app))
        yield
        
        # Shutdown
    finally:
        if ingestion_task:
            ingestion_task.cancel()
            with suppress(asyncio.CancelledError):
                await ingestion_task

        if app.state.redis_client:
            with suppress(Exception):
                await app.state.redis_client.close()

        if app.state.db_pool:
            await app.state.db_pool.close()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_methods=["*"]
)

# async def research_worker():
#    while True:
#         try:
#             task = await task_queue.get()
#             task_vector = model.encode(task).tolist()
#             print(f"Worker: Researching {task}")
#             async with db_pool.acquire() as conn:
#                 record = await conn.fetch(
#                     '''SELECT TITLE, CONTENT FROM research_papers ORDER BY embedding <=> $1 LIMIT 3''',
#                     str(task_vector)
#                 )
#             if not record:
#                 await result_queue.put("Agent Warning: No relevant research found in the memory banks.")
#                 continue
#             context_string = "\n\n".join([f"Source: {r['title']}\nData: {r['content']}" for r in record])
#             groq_prompt = f"""
#                 You are an elite scientific research synthesizer. 
#             The user asked: "{task}"
            
#             Read the following research papers and write a brilliant, generalized summary answering their question. 
#             Do NOT use outside knowledge. Rely ONLY on this provided context:
            
#             {context_string}
#             """
#             text_response = await llm.astream(
#                 [
#                     {"role": "system", "content": "You are a precise and highly technical AI research agent."},
#                     {"role": "user", "content": groq_prompt}
#                 ]
#             )
#             await result_queue.put(text_response.content)
#         except Exception as e:
#             await result_queue.put(f"Agent Warning: No relevant research found in the memory banks.")
#             print(f"worker error: {e}")
#         finally:
#             task_queue.task_done()

async def ingestion_worker(app: FastAPI):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size = 1000,
        chunk_overlap = 200,
        length_function = len,
    )
    db_pool = app.state.db_pool
    redis_client = app.state.redis_client
    if not db_pool or not redis_client:
        raise RuntimeError("DB pool or Redis client not initialized")

    backoff_s = 1
    while True:
        try:
            # brpop returns None on timeout; keep looping without error spam.
            result = await redis_client.brpop("ingestion_tasks", timeout=5)
            if result is None:
                continue

            _, task_data = result
            topic = task_data.decode("utf-8").strip()
            if not topic:
                continue
            print(f"This is the topic: {topic}")
            search = arxiv.Search(
                query=f"all:{topic}",
                max_results=3,
                sort_by=arxiv.SortCriterion.Relevance
            )
            client = arxiv.Client()
            papers = await asyncio.to_thread(lambda: list(client.results(search)))
            if not papers:
                print(f"Agent Warning: No papers found for '{topic}'")
                continue
            for paper in papers:
                title = paper.title.replace('\n',' ')
                full_text = paper.summary.replace('\n',' ')
                chunks = text_splitter.split_text(full_text)
                print(f"Processing: {title[:40]}... (Split into {len(chunks)} chunks)")
                
                for chunk in chunks:
                    chunk_vector = await embed_text(chunk)
                    
                    async with db_pool.acquire() as conn:
                        await conn.execute(
                            '''
                            Insert into research_papers (title, content, embedding) values ($1,$2,$3)
                            ''',
                            title, chunk, str(chunk_vector)
                            
                        )
            print(f"Agent: Successfully saved  '{topic}' data to neural vault.")
            backoff_s = 1
        except Exception as e:
            # Keep the worker alive even if one topic fails.
            print(f"Ingestion worker error: {str(e)}")
            await asyncio.sleep(backoff_s)
            backoff_s = min(backoff_s * 2, 30)

@app.get("/fetch-papers")
async def fetch_papers(topic:str):
    redis_client = app.state.redis_client if hasattr(app, "state") else None
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis not initialized")

    topic = topic.strip()
    if not topic:
        raise HTTPException(status_code=422, detail="topic is required")

    await redis_client.lpush("ingestion_tasks", topic)
    return {"status":"Ingestion started via Redis queue"}


        
@app.post("/trigger-research")
async def trigger_research(request: ChatRequest):
    if not request.history:
        raise HTTPException(status_code=422, detail="history is required")

    latest_user_message = request.history[-1].text.strip()
    if not latest_user_message:
        raise HTTPException(status_code=422, detail="latest user message must not be empty")

    db_pool = app.state.db_pool if hasattr(app, "state") else None
    if not db_pool:
        raise HTTPException(status_code=503, detail="DB not initialized")

    try:
        query_vector = await embed_text(latest_user_message)

        async with db_pool.acquire() as conn:
            records = await conn.fetch(
                '''select title, content from research_papers order by embedding <=> $1 limit 3''',
                str(query_vector)
            )
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to retrieve relevant research")

    if not records:
        context_string = ""
        sources_md = "_No relevant sources were found in the vault._"
    else:
        sources_md = "\n\n".join(
            [f"[{idx+1}] {r['title']}\n{r['content']}" for idx, r in enumerate(records)]
        )
        context_string = "\n\n".join(
            [f"Source: {r['title']}\nData: {r['content']}" for r in records]
        )
    
    formatted_history = []
    for msg in request.history[:-1]:
        formatted_history.append({"role":"user" if msg.role == "user" else "assistant", "content":msg.text})
    
    messages_for_llm = [
        {
            "role": "system",
            "content": (
                "You are a precise AI research agent.\n"
                "Use ONLY the provided Sources to answer.\n"
                "When you use information, cite it inline using the source numbers like [1], [2], etc.\n"
                "If the Sources do not contain enough information, say so explicitly and ask for a better query."
            ),
        },
    ]
    messages_for_llm.extend(formatted_history)
    messages_for_llm.append(
        {
            "role": "user",
            "content": (
                f"User Question:\n{latest_user_message}\n\n"
                f"Sources:\n{sources_md}\n\n"
                "Answer in Markdown."
            ),
        }
    )
    async def generate_response():
        try:
            async for chunk in llm.astream(messages_for_llm):
                if chunk.content:
                    yield chunk.content
        except Exception as e:
            # StreamingResponse can't change HTTP status after headers are sent,
            # but we can still stream a readable error marker.
            yield f"\n\n[Error generating response: {str(e)}]"

    return StreamingResponse(generate_response(), media_type="text/plain")
    # query_vector = model.encode(query).tolist()
    # async with db_pool.acquire() as conn:
    #     records = await conn.fetch(
    #         '''select title,content from research_papers order by embedding <=> $1 limit 3''',
    #         str(query_vector)
    #     )
    # if not records:
    #     context_string = "No relevant research found in the Neural Vault."
    # else:
    #     context_string = "\n\n".join([f"Source: {r['title']}\nData: {r['content']}" for r in records])
    
    # groq_prompt = f"""
    # You are an elite scientific research synthesizer. 
    # The user asked: "{query}"
    
    # Synthesize a brilliant, well-formatted Markdown response using ONLY this context:
    # {context_string}
    # """
    
    # async def generate_response():
    #     async for chunk in llm.astream([
    #         {"role": "system", "content": "You are a precise and highly technical AI research agent. Use markdown formatting."},
    #         {"role": "user", "content": groq_prompt}
    #     ]):
    #         if chunk.content:
    #             yield chunk.content
    # return StreamingResponse(generate_response(),media_type="text/plain")
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
    # await task_queue.put(query)
    # result = await result_queue.get()
    # return {
    #     "status":"Success",
    #     "message":"Research paper successfully embedded and saved to Postgres!",
    #     "dimension_saved": len(vector)
    # }
    # return {"result":result}
        
    # sample_text = "Topological qubits utilize non-Abelian anyons to achieve fault-tolerant quantum computation."
    # vector = model.encode(sample_text).tolist()
    # return {"status":"Complete","preview_vector":
    # vector[:5],"total_dimensions": len(vector)}
    


@app.get('/search-research')
async def search_research(query:str,request:Request):
    if not query or not query.strip():
        raise HTTPException(status_code=422, detail="query is required")

    db_pool = app.state.db_pool if hasattr(app, "state") else None
    if not db_pool:
        raise HTTPException(status_code=503, detail="DB not initialized")

    try:
        query_vector = await embed_text(query.strip())
        async with db_pool.acquire() as conn:
            record = await conn.fetchrow(
                '''SELECT TITLE, CONTENT FROM research_papers ORDER BY embedding <=> $1 LIMIT 1''',
                str(query_vector)
            )
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to search research")
    if not record:
        raise HTTPException(status_code=404, detail="No matching research found")
    return {"title":record['title'],"content":record['content']}



    


  




       
       
       
