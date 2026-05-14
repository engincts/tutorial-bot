import asyncio
import os
from dotenv import load_dotenv

from app.infrastructure.llm.litellm_client import LiteLLMClient
from app.services.knowledge_tracing.kc_mapper import KCMapper

load_dotenv()

async def main():
    llm = LiteLLMClient(model="deepseek/deepseek-v3.2")
    mapper = KCMapper(llm)
    
    res = await mapper.extract("Türev nedir?", course_names=["tyt_matematik"])
    print("Türev nedir? ->", res)

    res2 = await mapper.extract("Egim nedir?", course_names=[])
    print("Egim nedir? ->", res2)

if __name__ == "__main__":
    asyncio.run(main())
