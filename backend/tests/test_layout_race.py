import asyncio, os, copy
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
import listen


def test_stale_status_write_keeps_saved_wiim_ips():
    async def go():
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])["race_test_db"]
        await db.listen.delete_many({})
        listen.D.update(db=db, state_key="race", log_limit=50)
        stale = await listen.load()  # status poll reads, then waits on the slow amp
        v = listen.view(await listen.load())
        wiims = copy.deepcopy(v["wiims"]); wiims[0]["ip"] = "192.168.0.201"; wiims[1]["ip"] = "192.168.0.202"
        rooms = [{k: x for k, x in r.items() if k not in ("status", "in_party")} for r in v["rooms"]]
        await listen.put_layout(listen.LayoutReq(rooms=rooms, party_sources=v["party_sources"], wiims=wiims))
        stale["status"]["living"]["volume"] = 42
        await listen.store(stale)  # poll finishes and writes its old copy
        after = await listen.load()
        await db.client.drop_database("race_test_db")
        return after
    after = asyncio.run(go())
    assert [w["ip"] for w in after["wiims"]] == ["192.168.0.201", "192.168.0.202"]
    assert after["status"]["living"]["volume"] == 42
