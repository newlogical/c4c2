import asyncio, re
Z = {z: dict(pa=0, pw=0, mu=0, dnd=0, vo=11, tr=7, ba=7, bal=10, src=1, kp=1) for z in range(11, 17)}
IGNORE_SOURCE = set()
async def h(r, w):
    buf = b""
    while True:
        d = await r.read(100)
        if not d: break
        buf += d
        while b"\r" in buf:
            line, buf = buf.split(b"\r", 1); line = line.decode().strip()
            m = re.match(r"<(\d\d)(PR|MU|VO|CH)(\d\d)", line)
            if m:
                z, k, v = int(m[1]), m[2], int(m[3])
                if k == "CH" and z in IGNORE_SOURCE: continue
                Z[z][{"PR": "pw", "MU": "mu", "VO": "vo", "CH": "src"}[k]] = v
                w.write(f"#{line}\r\n".encode())
            m = re.match(r"\?(\d\d)", line)
            if m:
                s = Z[int(m[1])]
                w.write(("#>%d" % int(m[1]) + "".join("%02d" % s[k] for k in ("pa","pw","mu","dnd","vo","tr","ba","bal","src","kp")) + "\r\r\n#").encode())
            await w.drain()
async def main():
    srv = await asyncio.start_server(h, "127.0.0.1", 8080)
    async with srv: await srv.serve_forever()
asyncio.run(main())
