# PyStreamRTC
![2024-07-1700-28-33-ezgif com-video-to-gif-converter](https://github.com/user-attachments/assets/0868f257-125d-4f2d-8b6b-8d8eb89b053f)

Welcome to PyStreamRTC, versatile media streaming solution leveraging the power of Python, GStreamer, and WebRTC. 

## Instructions
### Install GStreamer
#### Debian/Ubuntu
`sudo apt-get install -y gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav libnice10 libglib2.0-dev`

`pip install -r requirements.txt`

### Play your video
```
cd PyStreamRTC
python streamer.py --video /path/to/your/video.mp4
> Starting pipeline
======== Running on http://0.0.0.0:8080 ========
have fun!
```
