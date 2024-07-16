import logging
import websockets
import asyncio
import sys
import json
import argparse

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
gi.require_version('GstWebRTC', '1.0')
from gi.repository import GstWebRTC
gi.require_version('GstSdp', '1.0')
from gi.repository import GstSdp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

FILE_DESC = """filesrc location={} ! qtdemux name=demux
     webrtcbin name=sendrecv bundle-policy=max-bundle stun-server=stun://stun.l.google.com:19302
     demux.video_0 ! h264parse ! rtph264pay config-interval=-1 ! queue ! application/x-rtp,media=video,encoding-name=H264,payload=96 ! sendrecv.
     """

class WebRTCClient:
    def __init__(self, source):
        self.conn = None
        self.pipe = None
        self.webrtc = None
        self.source = source
        self.server = 'ws://127.0.0.1:8765/'

    async def connect(self):
        self.conn = await websockets.connect(self.server)
        await self.conn.send(f'HELLO')

    async def setup_call(self):
        await self.conn.send(f'SESSION')

    def send_sdp_offer(self, offer):
        text = offer.sdp.as_text()
        logging.debug(f'[webrtc] - Sending offer:\n{text}')
        msg = json.dumps({'sdp': {'type': 'offer', 'sdp': text}})
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.conn.send(msg))

    def on_offer_created(self, promise, _, __):
        promise.wait()
        reply = promise.get_reply()
        offer = reply.get_value('offer')
        promise = Gst.Promise.new()
        self.webrtc.emit('set-local-description', offer, promise)
        logging.info(f"[webrtc] - Setting local streaming description")
        promise.interrupt()
        self.send_sdp_offer(offer)

    def on_negotiation_needed(self, element):
        promise = Gst.Promise.new_with_change_func(self.on_offer_created, element, None)
        logging.info(f"[webrtc] - Creating offer for streaming")
        element.emit('create-offer', None, promise)

    def send_ice_candidate_message(self, _, mlineindex, candidate):
        icemsg = json.dumps({'ice': {'candidate': candidate, 'sdpMLineIndex': mlineindex}})
        logging.info(f"[webrtc] - sending ICE canditate")
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.conn.send(icemsg))

    def on_incoming_stream(self, _, pad):
        return False

    def start_pipeline(self):
        logging.info(f"[webrtc] - launching stream")
        self.pipe = Gst.parse_launch(FILE_DESC.format(self.source))
        self.webrtc = self.pipe.get_by_name('sendrecv')
        self.webrtc.connect('on-negotiation-needed', self.on_negotiation_needed)
        self.webrtc.connect('on-ice-candidate', self.send_ice_candidate_message)
        self.webrtc.connect('pad-added', self.on_incoming_stream)
        self.pipe.set_state(Gst.State.PLAYING)

    async def handle_sdp(self, message):
        assert (self.webrtc)
        msg = json.loads(message)
        if 'sdp' in msg:
            sdp = msg['sdp']
            assert(sdp['type'] == 'answer')
            sdp = sdp['sdp']
            logging.info(f"[webrtc] - Received answer from webapp")
            logging.info(f"[webrtc] - Received answer:\n {sdp}")
            res, sdpmsg = GstSdp.SDPMessage.new()
            GstSdp.sdp_message_parse_buffer(bytes(sdp.encode()), sdpmsg)
            answer = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.ANSWER, sdpmsg)
            promise = Gst.Promise.new()
            self.webrtc.emit('set-remote-description', answer, promise)
            promise.interrupt()
        elif 'ice' in msg:
            ice = msg['ice']
            candidate = ice['candidate']
            sdpmlineindex = ice['sdpMLineIndex']
            logging.info(f"[webrtc] - Received ICE candidate")
            self.webrtc.emit('add-ice-candidate', sdpmlineindex, candidate)
        elif 'play' in msg:
            logging.info("Playing pipeline")
            self.pipe.set_state(Gst.State.PLAYING)
        elif 'pause' in msg:
            logging.info("Pausing pipeline")
            self.pipe.set_state(Gst.State.PAUSED)
        elif 'seek' in msg:
            seek_time = int(msg["seek"])
            logging.info(f"Seeking to {seek_time} seconds")
            self.pipe.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, seek_time * Gst.SECOND)

    async def loop(self):
        assert self.conn
        async for message in self.conn:
            if message == 'HELLO':
                await self.setup_call()
            elif message == 'SESSION_OK':
                self.start_pipeline()
            elif message.startswith('ERROR'):
                logging.error(f"[webrtc] - [nogotiation] - {message}")
                return 1
            else:
                await self.handle_sdp(message)
        return 0


if __name__=='__main__':
    Gst.init(None)
    parser = argparse.ArgumentParser()
    parser.add_argument('--src', required=True, help='Input video source')
    args = parser.parse_args()
    c = WebRTCClient(args.src)
    asyncio.get_event_loop().run_until_complete(c.connect())
    res = asyncio.get_event_loop().run_until_complete(c.loop())
    sys.exit(res)