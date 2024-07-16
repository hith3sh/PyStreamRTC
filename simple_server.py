import sys
import logging
import asyncio
import websockets
import argparse
import http
import concurrent

class WebRTCSimpleServer(object):

    def __init__(self, loop, options):
        self.peers = dict()  # Format: {id: (WebSocket, remote_address)}
        self.session_peer1 = None
        self.session_peer2 = None

        self.loop = loop
        self.server = None

        self.addr = options.addr
        self.port = options.port
        self.keepalive_timeout = options.keepalive_timeout
        self.health_path = options.health

    async def health_check(self, path, request_headers):
        if path == self.health_path:
            return http.HTTPStatus.OK, [], b"OK\n"
        return None

    async def recv_msg_ping(self, ws, raddr):
        msg = None
        while msg is None:
            try:
                msg = await asyncio.wait_for(ws.recv(), self.keepalive_timeout)
            except (asyncio.TimeoutError, concurrent.futures._base.TimeoutError):
                print(f'Sending keepalive ping to {raddr!r} in recv')
                await ws.ping()
        return msg

    async def remove_peer(self, peer_id):
        if peer_id in self.peers:
            ws, _ = self.peers[peer_id]
            del self.peers[peer_id]
            await ws.close()
        if peer_id in (self.session_peer1, self.session_peer2):
            self.session_peer1 = None
            self.session_peer2 = None
        print(f"Disconnected from peer {peer_id!r}")

    async def connection_handler(self, ws, peer_id):
        raddr = ws.remote_address
        self.peers[peer_id] = (ws, raddr)
        print(f"Registered peer {peer_id!r} at {raddr!r}")
        try:
            while True:
                msg = await self.recv_msg_ping(ws, raddr)
                if peer_id in (self.session_peer1, self.session_peer2):
                    other_id = self.session_peer2 if peer_id == self.session_peer1 else self.session_peer1
                    other_ws, _ = self.peers[other_id]
                    print(f"{peer_id} -> {other_id}: {msg}")
                    await other_ws.send(msg)
                elif msg == 'SESSION':
                    if self.session_peer1 is None:
                        self.session_peer1 = peer_id
                        await ws.send('WAIT')
                    elif self.session_peer2 is None:
                        self.session_peer2 = peer_id
                        await ws.send('SESSION_OK')
                        await self.peers[self.session_peer1][0].send('SESSION_OK')
                        print(f'Session established between {self.session_peer1!r} and {self.session_peer2!r}')
                    else:
                        await ws.send('ERROR session already in progress')
                else:
                    print(f'Ignoring unknown message {msg!r} from {peer_id!r}')
        finally:
            await self.remove_peer(peer_id)

    async def hello_peer(self, ws):
        raddr = ws.remote_address
        hello = await ws.recv()
        if not hello.startswith('HELLO'):
            await ws.close(code=1002, reason='invalid protocol')
            raise Exception(f"Invalid hello from {raddr!r}")
        peer_id = str(len(self.peers) + 1)
        await ws.send(f'HELLO {peer_id}')
        return peer_id

    def run(self):
        async def handler(ws, path):
            raddr = ws.remote_address
            print(f"Connected to {raddr!r}")
            peer_id = await self.hello_peer(ws)
            try:
                await self.connection_handler(ws, peer_id)
            except websockets.ConnectionClosed:
                print(f"Connection to peer {raddr!r} closed, exiting handler")
            finally:
                await self.remove_peer(peer_id)

        print(f"Listening on https://{self.addr}:{self.port}")
        wsd = websockets.serve(handler, self.addr, self.port, 
                               process_request=self.health_check if self.health_path else None,
                               max_queue=16)

        logger = logging.getLogger('websockets')
        logger.setLevel(logging.INFO)
        logger.addHandler(logging.StreamHandler())

        self.server = self.loop.run_until_complete(wsd)

    async def stop(self):
        print('Stopping server... ', end='')
        self.server.close()
        await self.server.wait_closed()
        self.loop.stop()
        print('Stopped.')

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--addr', default='', help='Address to listen on (default: all interfaces, both ipv4 and ipv6)')
    parser.add_argument('--port', default=8443, type=int, help='Port to listen on')
    parser.add_argument('--keepalive-timeout', dest='keepalive_timeout', default=30, type=int, help='Timeout for keepalive (in seconds)')
    parser.add_argument('--health', default='/health', help='Health check route')

    options = parser.parse_args(sys.argv[1:])

    loop = asyncio.get_event_loop()

    server = WebRTCSimpleServer(loop, options)

    print('Starting server...')
    while True:
        server.run()
        loop.run_forever()
        print('Restarting server...')

if __name__ == "__main__":
    main()