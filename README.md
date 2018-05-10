## MythFileRecorder

This [ExternalRecoder implementation](https://www.mythtv.org/wiki/ExternalRecorder) is used in conjunction with MythTV's External Recorder capture card type to read directly from an V4L2 video capture card using ffmpeg.  This script is similar to the mythfilerecorder distributed with MythTV but the implementation is a bit simpler and complete.  The embedded capture command is meant for a [Magewell Pro Capture HDMI card](http://www.magewell.com/pro-capture-hdmi) on /dev/video0 but can be modified for any card readable by ffmpeg.


### Installation
1. Copy script and make executable.
2. Edit the inputcmd and tunercmd commands in the script to fit your card and tuner.
3. In MythTV-Setup, add a new capture card, select "External (black box) recorder".  In the "Command path" field, enter the path to the script.


### FFmpeg Notes
The default inputcmd utilizes a version of ffmpeg with Nvidia card hardware encoding support.  To compile ffmpeg with this support, try:

```
./configure --arch=x86_64 --bindir=/usr/bin --datadir=/usr/share/ffmpeg --disable-debug --enable-static --disable-stripping --enable-avfilter --enable-avresample --enable-bzlib --enable-doc --enable-fontconfig --enable-frei0r --enable-gnutls --enable-gpl --enable-iconv --enable-libass --enable-libbluray --enable-libcdio --enable-libdrm --enable-libfdk-aac --enable-libfreetype --enable-libfribidi --enable-libmp3lame --enable-libopenjpeg --enable-libpulse --enable-alsa --enable-indev=alsa --enable-outdev=alsa --enable-librtmp --enable-librubberband --enable-libsoxr --enable-libspeex --enable-libssh --enable-libtesseract --enable-libtheora --enable-libtwolame --enable-libv4l2 --enable-libvorbis --enable-libvpx --enable-libx264 --enable-libx265 --enable-libxcb --enable-libxcb-shm --enable-libxcb-xfixes --enable-libxcb-shape --enable-libxvid --enable-libzvbi --enable-lzma --enable-nonfree --enable-openal --enable-nvenc --enable-opengl --enable-postproc --enable-pthreads --enable-sdl2 --disable-shared --enable-version3 --enable-xlib --enable-zlib --extra-cflags='-I/usr/include/nvenc -I/usr/include/cuda -I/usr/local/include/decklink' --incdir=/usr/include/ffmpeg --libdir=/usr/lib64 --mandir=/usr/share/man --optflags='-O2 -g -pipe -Wall -Wp,-D_FORTIFY_SOURCE=2 -fexceptions -fstack-protector-strong --param=ssp-buffer-size=4 -grecord-gcc-switches -m64 -mtune=native' --prefix=/usr --shlibdir=/usr/lib64 --enable-runtime-cpudetect --enable-vaapi
```


### Acknowledgements
This script is heavily inspired by the C++ implmentation of MythFileRecorder distributed with MythTV and critical modifications to that code and ffmpeg configuration details by Dan Wilga.
