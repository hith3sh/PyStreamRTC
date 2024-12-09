# PyStreamRTC V1.0🥷🏻
![2024-07-1700-28-33-ezgif com-video-to-gif-converter](https://github.com/user-attachments/assets/0868f257-125d-4f2d-8b6b-8d8eb89b053f)

Welcome to PyStreamRTC, versatile media streaming solution leveraging the power of Python, GStreamer, and WebRTC. 

## 🛠 Installation and Setup Instructions

### Install GStreamer and other libraries

I have only checked the workflow for debian based systems. Feel free to check the workflow in any other platform, but below libraries won't be easy to install in others
### For Debian platforms
#### System-level installation
`sudo apt-get install -y gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly libnice-dev gstreamer1.0-nice libglib2.0-dev libcairo2-dev libgirepository1.0-dev pkg-config python3-dev python3-gst-1.0 libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev libgstreamer-plugins-good1.0-dev libgstreamer-plugins-bad1.0-dev gobject-introspection`

#### pip installation
`pip install -r requirements.txt`

### Navigate to the location and start streaming 🚀
`cd PyStreamRTC`

`python streamer.py --video /path/to/your/video.mp4`
```
> Starting pipeline
======== Running on http://0.0.0.0:8080 ========
have fun!
```
### 🗒️ Note
This functionality works seamlessly on Chromium-based browsers. For optimal performance, please test on a Chromium browser first, as there may be occasional issues with WebRTC streaming on Mozilla Firefox.

### 🌱 Contribution
If you have any suggestions on what to improve in PyStreamRTC and would like to share them, feel free to leave an issue or fork project to implement your own ideas
