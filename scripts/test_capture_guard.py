"""Deterministic test of the lead-capture guard (no LLM). Runs the tool handler
directly with good/bad inputs and checks the DB outcome."""
import asyncio
import psycopg
from app.config import settings
from app.services import chatbot_service as c
from app.database.queries import lead_queries

GYM_ID = 3


async def main():
    dsn = (f"host={settings.db_host} port={settings.db_port} dbname={settings.db_name} "
           f"user={settings.db_user} password={settings.db_password}")
    async with await psycopg.AsyncConnection.connect(dsn) as db:
        async def count(phone_digits):
            async with db.cursor() as cur:
                await cur.execute(
                    "SELECT count(*) FROM chat_leads WHERE gym_id=%s AND "
                    "right(regexp_replace(phone,'\\D','','g'),10)=right(%s,10)",
                    (GYM_ID, phone_digits))
                return (await cur.fetchone())[0]

        cases = [
            ("invalid short phone", {"name": "Junk", "phone": "123"}, "9999999123", False),
            ("valid phone",        {"name": "Zoya", "phone": "9812345600"}, "9812345600", True),
            ("duplicate phone",    {"name": "Zoya2", "phone": "+91 98123 45600"}, "9812345600", "dupe"),
            ("letters as phone",   {"name": "Bad", "phone": "abcdefghij"}, "0000000000", False),
            ("landline-ish 5-start",{"name": "Land", "phone": "5000000000"}, "5000000000", False),
        ]
        for label, args, digits, expect in cases:
            before = await count(digits)
            res = await c._run_capture_lead(db, GYM_ID, args, "test msg", [])
            after = await count(digits)
            created = after - before
            verdict = "OK"
            if expect is False and (res["saved"] or created):
                verdict = "FAIL (should have been rejected)"
            if expect is True and not (res["saved"] and created == 1):
                verdict = "FAIL (should have saved exactly 1)"
            if expect == "dupe" and (res["saved"] and created):  # dedup returns existing, no new row
                verdict = "FAIL (created a duplicate)"
            print(f"[{verdict}] {label:22} -> saved={res['saved']} new_rows={created}")

        # cleanup
        async with db.cursor() as cur:
            await cur.execute("DELETE FROM chat_leads WHERE gym_id=%s AND lead_name IN ('Zoya','Zoya2','Junk','Bad','Land')", (GYM_ID,))
        await db.commit()
        print("cleanup done")


if __name__ == "__main__":
    asyncio.run(main())
