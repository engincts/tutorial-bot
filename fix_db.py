import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://postgres.maffqoqbjcoxaqritqol:tutorial-bot-123@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require')
    
    # Update Math
    res = await conn.execute("UPDATE mastery_scores SET subject = 'tyt_matematik' WHERE kc_id LIKE 'matematik_%'")
    print(f'Math updated: {res}')
    
    # Update Chem
    res2 = await conn.execute("UPDATE mastery_scores SET subject = 'tyt_kimya' WHERE kc_id LIKE 'kimya_%'")
    print(f'Chem updated: {res2}')
    
    # Fix Genel
    res3 = await conn.execute("UPDATE mastery_scores SET subject = 'tyt_matematik' WHERE subject = 'Genel' AND kc_id LIKE 'matematik_%'")
    print(f'Genel Math updated: {res3}')
    
    await conn.close()

asyncio.run(main())
