## MythFileRecorder

This [ExternalRecoder implementation](https://www.mythtv.org/wiki/ExternalRecorder) is used in conjunction with MythTV's External Recorder capture card type to read directly from an V4L2 video capture card using ffmpeg.  This script is similar to the mythfilerecorder distributed with MythTV but the implementation is a bit simpler and doesn't require compiling.  The embedded capture command is meant for a [Magewell Pro Capture HDMI card](http://www.magewell.com/pro-capture-hdmi) on /dev/video0 but can be modified for any card readable by ffmpeg or any other "black box" command line tool.


### Purpose
The purpose of this script was originally to debug issues I was having using MythTV's built-in MythFileRecorder (especially after updating to v29).  This code has since evolved to a reliable drop-in replacement for MythFileRecorder and has several advantages.  First, because it's Python-based, compiling with the full MythTV source is not necessary.  Second, the code is easily readable and can be adapted quickly to support other hardware.


### Installation
1. Copy script and make executable.
2. Edit the inputcmd and tunercmd commands in the script to fit your card and tuner.
3. In MythTV-Setup, add a new capture card, select "External (black box) recorder".  In the "Command path" field, enter the path to the script.


#### Usage

```
mythfilerecorder.py [-h] [-v LEVEL] [--logpath PATH] [--loglevel LEVEL] [-q] [--syslog LEVEL] [--tunerleadingzero] [--infile INPUTCMD] [--tuner TUNERCMD]
```


| Argument                    | Notes                                                  |
| --------------------------- | ------------------------------------------------------ |
| `-h, --help`                | Show help message and exit                             |
| `-v LEVEL, --verbose LEVEL` | Specify log filtering level. (provided for MythTV compatibility but currently ignored) |
| `--logpath PATH`            | Writes logging messages to a file in the directory logpath with filenames in the format: applicationName.date.pid.log. |
| `--loglevel LEVEL`          | Set the logging level. All log messages at lower levels will be discarded. In descending order: emerg, alert, crit, err, warning, notice, info, debug; defaults to info
| `-q, --quiet`               | Don't log to the console (-q). (provided for MythTV compatibility but currently ignored) |
| `--syslog LEVEL`            | Set the syslog logging facility. Set to "none" to disable, defaults to none. (provided for MythTV compatibility but currently ignored)   |
| `--tuner-leading-zero`      | Append a leading zero to the channel for faster tuning       |
| `--infile INPUTCMD`         | Input command that returns a transport stream on STDOUT (e.g. 'ffmpeg -i /dev/video0 ... pipe:1') |
| `--tuner TUNERCMD`          | Path of another program which will tune the channel requested by MythTV. Must accept the channel number as the last parameter. |


### Recording Command Details
The recording command can be based on any tool that outputs to STDOUT.  FFmpeg is one such flexible tool that has many configuration options (see the [ffmpeg documentation](https://ffmpeg.org/ffmpeg.html) for details).  Below are the ffmpeg switches used and notes for a Magewell Pro Capture card.  These may require modification to work with your card and should be tuned for your system to allow real-time encoding.


| Argument                  | Notes                                                  |
| --------------------------| ------------------------------------------------------ |
| `-loglevel error `        | Keeps the messages limited to errors \(important to prevent spurious messages\) |
| `-thread_queue_size 256 ` | Prevent warning messages about audio thread_queue_size |
| `-f alsa -i hw:2,0 `      | Input audio from ALSA device on hw:2.0                 |
| `-framerate 60 `          | Set video framerate                                    |
| `-thread_queue_size 512 ` | Prevent warning messages about video thread_queue_size |
| `-f v4l2 -i /dev/video0`  | Input video from v4l2 device, /dev/video0              |
| `-acodec aac `            | Use AAC audio encoding                                 |
| `-af "volume=15dB" `      | Increase recorded volume                               |
| `-vcodec h264_nvenc `     | Use Nvidia graphic card h264 hardware encoding         |
| `-b:a 128k `              | Use 128k audio bit rate                                |
| `-b:v 6M `                | Use 6MB video bit rate                                 |
| `-f mpegts `              | Format output as MPEG transport stream                 |
| `pipe:1`                  | Return output to STDOUT                                |


### FFmpeg Custom Options
The default inputcmd utilizes a version of ffmpeg that takes advantage of Nvidia video card hardware encoding and ALSA audio support.  The version installed by your package manager or MythTV may be sufficient for your purposes, however, to build a custom version to explictly support these options, download the FFmpeg source and configure with:

```
./configure --arch=x86_64 --bindir=/usr/bin --datadir=/usr/share/ffmpeg --disable-debug --enable-static --disable-stripping --enable-avfilter --enable-avresample --enable-bzlib --enable-doc --enable-fontconfig --enable-frei0r --enable-gnutls --enable-gpl --enable-iconv --enable-libass --enable-libbluray --enable-libcdio --enable-libdrm --enable-libfdk-aac --enable-libfreetype --enable-libfribidi --enable-libmp3lame --enable-libopenjpeg --enable-libpulse --enable-alsa --enable-indev=alsa --enable-outdev=alsa --enable-librtmp --enable-librubberband --enable-libsoxr --enable-libspeex --enable-libssh --enable-libtesseract --enable-libtheora --enable-libtwolame --enable-libv4l2 --enable-libvorbis --enable-libvpx --enable-libx264 --enable-libx265 --enable-libxcb --enable-libxcb-shm --enable-libxcb-xfixes --enable-libxcb-shape --enable-libxvid --enable-libzvbi --enable-lzma --enable-nonfree --enable-openal --enable-nvenc --enable-opengl --enable-postproc --enable-pthreads --enable-sdl2 --disable-shared --enable-version3 --enable-xlib --enable-zlib --extra-cflags='-I/usr/include/nvenc -I/usr/include/cuda -I/usr/local/include/decklink' --incdir=/usr/include/ffmpeg --libdir=/usr/lib64 --mandir=/usr/share/man --optflags='-O2 -g -pipe -Wall -Wp,-D_FORTIFY_SOURCE=2 -fexceptions -fstack-protector-strong --param=ssp-buffer-size=4 -grecord-gcc-switches -m64 -mtune=native' --prefix=/usr --shlibdir=/usr/lib64 --enable-runtime-cpudetect --enable-vaapi
```


### Logging
Although this script accepts standard MythTV logging parameters, it does not use MythTV's logging service and remains completely independent.  Log files will not automatically be rotated


### Acknowledgements
This script is heavily inspired by an approach and code provided by Dan Wilga based on the C++ implmentation of MythFileRecorder, which is distributed with MythTV.  Dan generously shared many of the necessary details to get this working.
