## Magewell Recorder For MythTV

This [ExternalRecoder implementation](https://www.mythtv.org/wiki/ExternalRecorder) is used in conjunction with MythTV's External Recorder capture card type to read directly from an V4L2 video capture card using ffmpeg.  This script is similar to the mythfilerecorder distributed with MythTV but the implementation is a bit simpler and complete.  The embedded capture command is meant for a [Magewell Pro Capture HDMI card](http://www.magewell.com/pro-capture-hdmi) on /dev/video0 but can be modified for any card readable by ffmpeg.
