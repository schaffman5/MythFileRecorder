#!/usr/bin/python

# External MythTV Recorder Implementation
# https://www.mythtv.org/wiki/ExternalRecorder
#
# To run:
# ./magewell_rec.py > ~/test_video_output.ts
# 
# Then type commands followed by return to trigger events
# e.g. Version? -> StartStreaming -> SendBytes -> SendBytes -> SendBytes -> StopStreaming -> CloseRecorder

import os
import sys
import time
import shlex
import subprocess
import signal
from threading import Event, Thread
from subprocess import call

# TODO add proper logging levels and input handling

recordcmd = '/usr/local/ffmpeg-3.4.1/ffmpeg -loglevel error -thread_queue_size 256 -f alsa -i hw:2,0 -framerate 60 -thread_queue_size 512 -f v4l2 -i /dev/video0 -acodec aac -af "volume=5dB" -vcodec h264_nvenc -b:a 128k -b:v 6M -f mpegts pipe:1'
tunercmd = '/usr/local/bin/change_channel'

version = "0.1"
ready = True
hastuner = True
blocksize = 1000000 # 1MB (~1 seconds of video)

cmdbuffer=[]
blockbuffer=[]
recsubprocess = None
reader=None
DEVNULL = open(os.devnull, 'wb')

def remove_prefix(text, prefix):
	if text.startswith(prefix):
		return text[len(prefix):]
	return text  # or whatever
	
def reader(f, buffer, bytes):
	while True:
		line=f.read(bytes)
		if line:
			buffer.append(line)
		else:
			break

while True:
	cmd = sys.stdin.readline().rstrip('\n')
	if cmd == 'Version?':
		sys.stderr.write("OK:"+version+"\n")
		sys.stderr.flush()
		
	elif cmd == 'IsOpen?':
		if ready == True:
			sys.stderr.write("OK:Open"+"\n")
		else:
			sys.stderr.write("OK:No"+"\n")
		sys.stderr.flush()
		
	elif cmd == 'CloseRecorder':
		sys.stderr.write("OK:Terminating"+"\n")
		sys.stderr.flush()
		break
		
	elif cmd == 'HasTuner?':
		if hastuner == True:
			sys.stderr.write("OK:Yes"+"\n")
		else:
			sys.stderr.write("OK:No"+"\n")
		sys.stderr.flush()
		
	elif cmd == 'HasPictureAttributes?':
		sys.stderr.write("OK:No"+"\n")
		sys.stderr.flush()
		
	elif cmd == 'LockTimeout?':
		sys.stderr.write("OK:5000"+"\n")
		sys.stderr.flush()
		
	elif cmd == 'SignalStrengthPercent?':
		sys.stderr.write("OK:100"+"\n")
		sys.stderr.flush()
		
	elif cmd == 'HasLock?':
		sys.stderr.write("OK:Yes"+"\n")
		sys.stderr.flush()
		
	elif cmd == 'FlowControl?':
		sys.stderr.write("OK:Polling"+"\n")
		sys.stderr.flush()
	
	elif cmd.startswith('BlockSize:'): #  'BlockSize:<value>':
		
		blocksize = int(remove_prefix(cmd, 'BlockSize:'))
		
		sys.stderr.write("OK:BlockSize set to " + str(blocksize) + "\n")
		sys.stderr.flush()
		
	elif cmd == 'StartStreaming':
		# start subprocess with video capture command that sends the transport stream to 
		# the subprocess STDOUT
		recsubprocess = subprocess.Popen(shlex.split(recordcmd),stdout=subprocess.PIPE, stdin=DEVNULL)
		
		# TODO: catch errors from the subprocess and set ready=FALSE until resolved
		
		# start thread to read blocksize bytes from the subprocess STDOUT into blockbuffer
		reader=Thread(target=reader,args=(recsubprocess.stdout, blockbuffer, blocksize))
		reader.daemon=True
		reader.start()
		
		sys.stderr.write("OK:Started"+"\n")
		sys.stderr.flush()
		
	elif cmd == 'StopStreaming':
	
		if(recsubprocess != None):
			recsubprocess.send_signal(signal.SIGINT)
			time.sleep(0.5)
			
			recsubprocess=None
			reader=None
			sys.stderr.write("OK:Stopped"+"\n")
			
		else:
			sys.stderr.write("OK"+"\n")
			
		sys.stderr.flush()
	
	elif cmd == 'SendBytes':

		# When the external module receives the "XON", "XOFF" or "SendBytes" command, it
		# will respond in one of four ways via its STDERR:
		#	"OK"
		#	"OK:   some descriptive text" -- same as just "OK", but allows the external 
		#          module to tell mythbackend to log the external module's 'state'.
		#	"WARN: some descriptive text" -- which may indicates that the external module 
		#          is not able to send any bytes right now, but to try again.
		#	"ERR:  some descriptive text" -- which indicates that the external module is 
		#          in an error state, and the recording needs to abort and possibly 
		#          restart.
		
		if ready==True:
			if blockbuffer:
				out=blockbuffer.pop(0) # leftpop
				sys.stderr.write("OK:Sending "+str(sys.getsizeof(out))+" bytes"+"\n")
				sys.stderr.flush()
				print out
			else:
				sys.stderr.write("OK"+"\n")
		else:
			sys.stderr.write("ERR:Recorder not ready!"+"\n")
			sys.stderr.flush()
		

	elif cmd.startswith('TuneChannel:'): # 'TuneChannel:<value>':
		channel = remove_prefix(cmd, 'TuneChannel:')
		tunersubprocess = subprocess.Popen([tunercmd, channel],stdout=DEVNULL, stdin=DEVNULL)
		sys.stderr.write("OK:Tuning channel to " + channel + "\n")
		sys.stderr.flush()
		
	else:
		cmdbuffer.append(cmd)
