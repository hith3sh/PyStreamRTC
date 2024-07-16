import logging
import asyncio
import argparse
import os
import json
from aiohttp import web

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

Gst.init(None)

class WebRTCClient:
    def __init__(self, pipeline_description, conn):
        self.conn = conn
        self.loop = asyncio.get_running_loop()

        self.pipeline = Gst.parse_launch(pipeline_description)
        self.webrtc = self.pipeline.get_by_name('webrtcbin')

        self.webrtc.connect('on-negotiation-needed', self.on_negotiation_needed)
        self.webrtc.connect('on-ice-candidate', self.send_ice_candidate_message)

        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect('message', self.on_message)
    
    def on_message(self, bus, message):
        if message.type == Gst.MessageType.EOS:
            self.pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, 0)
        elif message.type == Gst.MessageType.ERROR:
            err, debug_info = message.parse_error()
            logging.info(f"Error received from element {message.src.get_name()}: {err.message}")
            logging.info(f"Debugging information: {debug_info}")

    def start(self):
        logging.info("Starting pipeline")
        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            logging.error("Unable to set the pipeline to the playing state")
        else:
            logging.info("Pipeline is now playing")

    def play(self):
        logging.info("Playing pipeline")
        self.pipeline.set_state(Gst.State.PLAYING)

    def pause(self):
        logging.info("Pausing pipeline")
        self.pipeline.set_state(Gst.State.PAUSED)

    def seek(self, time_sec):
        logging.info(f"Seeking to {time_sec} seconds")
        self.pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, time_sec * Gst.SECOND)

    def send_sdp_offer(self, offer):
        text = offer.sdp.as_text()
        logging.info(f"sending SDP offer")
        msg = json.dumps({'event': 'offer', 'data': 
        {
            'type': 'offer',
            'sdp': text
        }
        })
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.conn.send_str(msg))

    def on_offer_created(self, promise,_, __):
        promise.wait()
        reply = promise.get_reply()
        offer = reply.get_value('offer')
        promise = Gst.Promise.new()
        self.webrtc.emit('set-local-description', offer, promise)
        logging.info("set local description")
        promise.interrupt()
        self.send_sdp_offer(offer)

    def on_negotiation_needed(self, element):
        promise = Gst.Promise.new_with_change_func(self.on_offer_created, None, None)
        logging.info("Creating offer")
        element.emit('create-offer', None, promise)

    def send_ice_candidate_message(self, _, mlineindex, candidate):
        icemsg = json.dumps({'event': 'candidate', 'data': 
        {
            'candidate': candidate, 
            'sdpMLineIndex': mlineindex}
        })
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.conn.send_str(icemsg))
    
def create_pipeline(container_path):
    pipeline_str = f"""
    filesrc location={container_path} ! qtdemux name=demux
    webrtcbin name=webrtcbin bundle-policy=max-bundle stun-server=stun://stun.l.google.com:19302
    demux.video_0 ! h264parse ! rtph264pay config-interval=-1 ! queue ! application/x-rtp,media=video,encoding-name=H264,payload=96 ! webrtcbin.
    """
    return pipeline_str


async def websocket_handler(request):
    conn = web.WebSocketResponse()
    await conn.prepare(request)

    # starting the pipeline
    pipeline_str = create_pipeline(container_path)
    pipeline = WebRTCClient(pipeline_str, conn)
    pipeline.start()

    async for msg in conn:
        if msg.type == web.WSMsgType.TEXT:
            data = json.loads(msg.data)
            if data["event"] == "answer":
                answer = data["data"]
                sdp = answer["sdp"]

                answer_type = answer["type"]
                assert answer_type == "answer"

                res, sdpmsg = GstSdp.SDPMessage.new()
                GstSdp.sdp_message_parse_buffer(bytes(sdp.encode()), sdpmsg)
                answer = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.ANSWER, sdpmsg)
                promise = Gst.Promise.new()
                pipeline.webrtc.emit('set-remote-description', answer, promise)
                promise.interrupt()

            elif data["event"] == "candidate":
                candidate = data["data"]
                candidate_val = candidate['candidate']
                pipeline.webrtc.emit('add-ice-candidate', candidate["sdpMLineIndex"], candidate_val)

            elif data["event"] == "play":
                pipeline.play()

            elif data["event"] == "pause":
                pipeline.pause()

            elif data["event"] == "seek":
                seek_time = int(data["data"])
                pipeline.seek(seek_time)

    return conn


async def index(request): 
    return web.FileResponse("index.html")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='WebRTC streaming server')
    parser.add_argument('--video', help='Path to the media container')

    args = parser.parse_args()
    container_path = args.video
    if not container_path:
        raise Exception("Container path must be specified")

    app = web.Application()
    app.add_routes([web.get("/", index), web.get("/ws", websocket_handler)])
    
    logging.info("Starting pipeline")

    web.run_app(app, port=8080)
