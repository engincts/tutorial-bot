import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://postgres.maffqoqbjcoxaqritqol:tutorial-bot-123@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require')
    
    # List sessions
    rows = await conn.fetch("SELECT id, title FROM chat_sessions")
    print("Sessions before delete:")
    for r in rows:
        print(f"{r['id']} -> {r['title']}")
    
    if rows:
        target_id = rows[0]['id']
        print(f"\nDeleting session: {target_id}")
        res1 = await conn.execute("DELETE FROM chat_messages WHERE session_id = $1", target_id)
        res2 = await conn.execute("DELETE FROM chat_sessions WHERE id = $1", target_id)
        print(f"Messages deleted: {res1}")
        print(f"Sessions deleted: {res2}")
    
    await conn.close()

asyncio.run(main())
