from fastapi import FastAPI,Request
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
from sentence_transformers import SentenceTransformer
import asyncpg
import redis.asyncio as redis
import asyncio
from fastapi.middleware.cors import CORSMiddleware 
from model import llm
import arxiv

# load_dotenv()
# groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

model = SentenceTransformer("all-MiniLM-L6-v2")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global task_queue, result_queue, ingest_queue, db_pool
    task_queue = asyncio.Queue()
    result_queue = asyncio.Queue()
    ingest_queue = asyncio.Queue()
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
            # print("Ingecting knowledge into memory banks")
            # papers = [
            #     ("Quantum Topology", "Topological qubits utilize non-Abelian anyons to achieve fault-tolerant quantum computation."),
            #     ("AI Transformers", "Transformer architectures rely on self-attention mechanisms to process sequential data in parallel, eliminating the need for recurrent loops."),
            #     ("CRISPR Gene Editing", "Cas9 proteins use guide RNA to locate and cleave specific DNA sequences, allowing for highly targeted genetic modifications.")
            # ]
            # for title,content in papers:
            #     vec = model.encode(content).tolist()
            #     await conn.execute(
            #         "insert into research_papers (title, content, embedding) values ($1, $2, $3)",
            #         title, content, str(vec)
            #     )
            # print("Memory banks fully populated.")
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
        # asyncio.create_task(research_worker())
        asyncio.create_task(ingestion_worker())
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

async def ingestion_worker():
    while True:
        try:
            topic = await ingest_queue.get()
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
                summary = paper.summary.replace('\n',' ')
                print(f"Found papers: {title[:60]}")
                summary_vectors = model.encode(summary).tolist()
                
                async with db_pool.acquire() as conn:
                    await conn.execute(
                        '''
                        insert into research_papers (title, content, embedding) values ($1, $2, $3)
                        ''',
                        title, summary, str(summary_vectors)
                    )
            print(f"Agent: Successfully saved  '{topic}' data to neural vault.")
        except Exception as e:
            print(f"API error: {str(e)}")
        finally:
            ingest_queue.task_done()

@app.get("/fetch-papers")
async def fetch_papers(topic:str):
    await ingest_queue.put(topic)
    return {"status":"Ingestionn started in the background."}


        
@app.get("/trigger-research")
async def trigger_research(query:str):
    query_vector = model.encode(query).tolist()
    async with db_pool.acquire() as conn:
        records = await conn.fetch(
            '''select title,content from research_papers order by embedding <=> $1 limit 3''',
            str(query_vector)
        )
    if not records:
        context_string = "No relevant research found in the Neural Vault."
    else:
        context_string = "\n\n".join([f"Source: {r['title']}\nData: {r['content']}" for r in records])
    
    groq_prompt = f"""
    You are an elite scientific research synthesizer. 
    The user asked: "{query}"
    
    Synthesize a brilliant, well-formatted Markdown response using ONLY this context:
    {context_string}
    """
    
    async def generate_response():
        async for chunk in llm.astream([
            {"role": "system", "content": "You are a precise and highly technical AI research agent. Use markdown formatting."},
            {"role": "user", "content": groq_prompt}
        ]):
            if chunk.content:
                yield chunk.content
    return StreamingResponse(generate_response(),media_type="text/plain")
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
    query_vector = model.encode(query).tolist()
    async with db_pool.acquire() as conn:
        record = await conn.fetchrow(
            '''SELECT TITLE, CONTENT FROM research_papers ORDER BY embedding <=> $1 LIMIT 1''',
            str(query_vector)
        )
    return {"title":record['title'],"content":record['content']}



    


  




       
       
       
