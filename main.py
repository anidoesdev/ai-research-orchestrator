from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncpg
import redis.asyncio as redis
import asyncio


@asynccontextmanager
async def lifespan(app: FastAPI):
    global task_queue, result_queue
    task_queue = asyncio.Queue()
    result_queue = asyncio.Queue()

    try:
        connected_postgres = await asyncpg.connect(user="admin",password="postpass",database="research_memory",host="127.0.0.1",port=5432)
        print("successfully connected to postgres")
        client = redis.from_url("redis://localhost:6379")
        if await client.ping():
                print("Connected to Redis")
        asyncio.create_task(research_worker())
        await connected_postgres.close()
        yield
        
    except Exception as e:
        print(f"this is the error: {e}")

app = FastAPI(lifespan=lifespan)

async def research_worker():
   while True:
        try:
            task = await task_queue.get()
            print(f"Worker: Researching {task}")
            await asyncio.sleep(3)
            raise ValueError("The AI API crashed!")
            await result_queue.put("Success")
        except Exception as e:
            await result_queue.put(f"Failed:{e}")
        finally:
            task_queue.task_done()
        
@app.get("/trigger-research")
async def trigger_research():
    await task_queue.put("")
    result = await result_queue.get()
    return {"status":"Complete","agent_message":result}
        




       
       
       
