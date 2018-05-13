#!/usr/bin/python

# MythTV External Recorder Implementation for Magewell Capture Card
# https://www.mythtv.org/wiki/ExternalRecorder
#
# To run:
# ./mythfilerecorder.py --logpath=/var/log/mythtv > ~/test_video_output.ts
# 
# Then type commands followed by return to trigger events
# e.g. Version? -> StartStreaming -> SendBytes -> SendBytes -> SendBytes -> StopStreaming -> CloseRecorder

import os
import sys
import argparse
import logging
import time
import datetime
import shlex
import subprocess
from threading import Event, Thread
from subprocess import call

#########
# Setup #
#########

inputcmd = '/usr/local/ffmpeg-3.4.1/ffmpeg -loglevel error -thread_queue_size 256 -f alsa -i hw:2,0 -framerate 60 -thread_queue_size 512 -f v4l2 -i /dev/video0 -acodec aac -af "volume=15dB" -vcodec h264_nvenc -b:a 128k -b:v 6M -f mpegts pipe:1'
tunercmd = '/usr/local/bin/6200ch -4 -n0 -e'

version = "0.3"
hastuner = True
blocksize = 1000000 # default 1MB blocksize

blockbuffer=[]
streamsubprocess=None
readerthread=None
sendbytesrequestcount=0
totalbytes=0
tunerleadingzero=False

DEVNULL = open(os.devnull, 'wb')


def remove_prefix(text, prefix):
	if text.startswith(prefix):
		return text[len(prefix):]
	return text
	
def reader(f, buffer, bytes):
	currentbytes=2000000 # start with a small value and progressively increase the buffer size
	while True:
		line=f.read(currentbytes)
		if line:
			buffer.append(line)
			currentbytes = min(int(currentbytes * 1.25), bytes)
		else:
			break

# subclass argparse so we can continue if unexpected arguments are passed in
class ArgumentParserError(Exception): pass

class ThrowingArgumentParser(argparse.ArgumentParser):
    def error(self, message):
    	sys.stderr.write("ERR:Parsing argv: " + message + "\n")
    	return


################## 
# Initialization #
##################

parser = ThrowingArgumentParser(description='MythTV External Recorder Python implementation for capture from black box cards')

parser.add_argument('-v', '--verbose', metavar='LEVEL', help='Specify log filtering level. (provided for MythTV compatibility but currently ignored)', dest='verbose', default='general')
parser.add_argument('--logpath', metavar='PATH', help='Writes logging messages to a file in the directory logpath with filenames in the format: applicationName.date.pid.log.', dest='logpath', default='')
parser.add_argument('--loglevel', metavar='LEVEL', help='Set the logging level.  All log messages at lower levels will be discarded.\nIn descending order: emerg, alert, crit, err, warning, notice, info, debug\ndefaults to info', dest='loglevel', default='info')
parser.add_argument('-q', '--quiet', help='Don\'t log to the console (-q). (provided for MythTV compatibility but currently ignored)', dest='quiet', default=False, action='store_true')
parser.add_argument('--syslog', metavar='LEVEL', help='Set the syslog logging facility.\nSet to "none" to disable, defaults to none. (provided for MythTV compatibility but currently ignored)', dest='syslog', default='none')
parser.add_argument('--tuner-leading-zero', help='Append a leading zero to the channel for faster tuning', dest='tunerleadingzero', default=False, action='store_true')
parser.add_argument('--infile', metavar='INPUTCMD', help='Input command that returns a transport stream on STDOUT (e.g. \'ffmpeg -i /dev/video0 ... pipe:1\')', dest='inputcmd', default=inputcmd)
parser.add_argument('--tuner', metavar='TUNERCMD', help='Path of another program which will tune the channel requested by MythTV. Must accept the channel number as the last parameter.', dest='tunercmd', default=tunercmd)


args = parser.parse_args()
logpath = vars(args).get('logpath')
loglevel = vars(args).get('loglevel')
inputcmd = vars(args).get('inputcmd')
tunercmd = vars(args).get('tunercmd')
tunerleadingzero = vars(args).get('tunerleadingzero')


#loglevel = 'debug' # force a level

# MythTV to Python log level table
logleveltable = {
	'emerg': logging.CRITICAL,
	'alert': logging.CRITICAL,
	'crit': logging.CRITICAL,
	'err': logging.ERROR,
	'warning': logging.WARNING,
	'notice': logging.INFO,
	'info': logging.INFO,
	'debug': logging.DEBUG
}

logger = logging.getLogger('Magewell Recorder')

if logpath != '':
	logfilepath = logpath + "/" + os.path.splitext(os.path.basename(__file__))[0] + "." + str(datetime.datetime.now().strftime('%Y%m%d%H%M%S')) + "." + str(os.getpid()) + ".log" # format: applicationName.date.pid.log
	level = logleveltable[loglevel]
	logging.basicConfig(filename=logfilepath, level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

logger.info("Starting : " + os.path.realpath(__file__) + " (v" + version + ")")
logger.info("Received arguments: " + str(sys.argv[1:]))


#############
# Main Loop #
#############

while True:
	cmd = sys.stdin.readline().rstrip('\n')
	if cmd == 'Version?':
		logger.info("Received: 'Version?' Returning: " + "'OK:"+version+"'")
		sys.stderr.write("OK:"+version+"\n")
		sys.stderr.flush()
	
	elif cmd == 'IsOpen?':
		logger.info("Received: 'IsOpen?' returning: " + "'OK:Open'")
		sys.stderr.write("OK:Open"+"\n")
		sys.stderr.flush()
	
	elif cmd == 'CloseRecorder':
		logger.info("Received: 'CloseRecorder' Returning: " + "'OK:Terminating'")
		sys.stderr.write("OK:Terminating"+"\n")
		sys.stderr.flush()
		
		if streamsubprocess != None:
			if streamsubprocess.poll() == None:
				streamsubprocess.terminate()
				time.sleep(0.5)
				streamsubprocess=None
				readerthread=None
				blockbuffer=[] # clear buffer
				
		logger.info("Recorder Closed - Summary: " + str(sendbytesrequestcount) + " 'SendBytes' requests made from server (" + str(totalbytes) +" total bytes)")
		
		break
	
	elif cmd == 'HasTuner?':
		if hastuner == True:
			logger.info("Received: 'HasTuner?' Returning: " + "'OK:Yes'")
			sys.stderr.write("OK:Yes"+"\n")
		else:
			logger.info("Received: 'HasTuner?' Returning: " + "'OK:No'")
			sys.stderr.write("OK:No"+"\n")
		sys.stderr.flush()
	
	elif cmd == 'HasPictureAttributes?':
		logger.info("Received: 'HasPictureAttributes?' Returning: " + "'OK:No'")
		
		sys.stderr.write("OK:No"+"\n")
		sys.stderr.flush()
	
	elif cmd == 'LockTimeout?':
		logger.info("Received: 'LockTimeout?' Returning: " + "'OK:20000'")
		
		sys.stderr.write("OK:20000"+"\n")
		sys.stderr.flush()
	
	elif cmd == 'SignalStrengthPercent?':
		logger.info("Received: 'SignalStrengthPercent?' Returning: " + "'OK:100'")
		
		sys.stderr.write("OK:100"+"\n")
		sys.stderr.flush()
	
	elif cmd == 'HasLock?':
		logger.info("Received: 'HasLock?' Returning: " + "'OK:Yes'")
		
		sys.stderr.write("OK:Yes"+"\n")
		sys.stderr.flush()
	
	elif cmd == 'FlowControl?':
		logger.info("Received: 'FlowControl?' Returning: " + "'OK:Polling'")
		
		sys.stderr.write("OK:Polling"+"\n")
		sys.stderr.flush()

	elif cmd.startswith('BlockSize:'): #  'BlockSize:<value>':
		logger.info("Received: '" + cmd + "' Returning: " + "'OK'")
		
		blocksize = int(remove_prefix(cmd, 'BlockSize:'))
		
		sys.stderr.write("OK:BlockSize set to " + str(blocksize) + "\n")
		sys.stderr.flush()
	
	elif cmd == 'StartStreaming':
		
		logger.info("Received: 'StartStreaming' Returning: " + "'OK:Started'")
		sys.stderr.write("OK:Started"+"\n")
		sys.stderr.flush()
		
		# start subprocess with video capture command that sends the transport stream to 
		# the subprocess STDOUT
		
		if streamsubprocess == None:
			streamsubprocess = subprocess.Popen(shlex.split(inputcmd), stdout=subprocess.PIPE, stdin=DEVNULL, stderr=subprocess.PIPE)
			
			# start thread to read blocksize bytes from the subprocess STDOUT into blockbuffer
			readerthread=Thread(target=reader,args=(streamsubprocess.stdout, blockbuffer, blocksize))
			readerthread.daemon=True
			readerthread.start()
		else:
			logger.info("Received: 'StartStreaming' but streaming already started.")
		
	elif cmd == 'StopStreaming':
	
		logger.info("Received: 'StopStreaming' Returning: " + "'OK:Stopped'")
		sys.stderr.write("OK:Stopped"+"\n")
		sys.stderr.flush()
		
		if streamsubprocess != None:
			if streamsubprocess.poll() == None:
				streamsubprocess.terminate()
				time.sleep(0.5)
				streamsubprocess=None
				readerthread=None
				# blockbuffer=[] # clear buffer
			
		else:
			msg="ERR:Streaming subprocess not started!"
			logger.error(msg)
			sys.stderr.write(msg + "\n")
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
		
		sendbytesrequestcount += 1 # keep count of server requests for data
		
		if streamsubprocess == None:
			msg="ERR:Streaming subprocess not started!  Use 'StartStreaming' command first."
			logger.error(msg)
			sys.stderr.write(msg + "\n")
			sys.stderr.flush()
		
		elif streamsubprocess.poll() == 1:
			err=""
			for line in streamsubprocess.stderr:
				err += line.strip() + "; "
    		
			msg="ERR:Streaming subprocess exited with error: " + err
			logger.error(msg)
			sys.stderr.write(msg + "\n")
			sys.stderr.flush()
			
		elif streamsubprocess.poll() == 0:
			msg="ERR:Streaming subprocess exited without errors(s)!"
			logger.error(msg)
			sys.stderr.write(msg + "\n")
			sys.stderr.flush()
			
		elif blockbuffer:
			out=blockbuffer.pop(0) # leftpop
			totalbytes += sys.getsizeof(out)
			
			logger.debug("Received: 'SendBytes' Returning: " + "'OK:Sending "+str(sys.getsizeof(out))+" bytes'")
			sys.stderr.write("OK:Sending "+str(sys.getsizeof(out))+" bytes"+"\n")
			sys.stderr.flush()
			sys.stdout.write(out)
			sys.stdout.flush()
			
		else:
			logger.debug("Received: 'SendBytes' Returning: WARN:No buffered bytes to send.")
			sys.stderr.write("WARN:No buffered bytes to send."+"\n")
			sys.stderr.flush()
	
	elif cmd.startswith('TuneChannel:'): # 'TuneChannel:<value>':
		channel = remove_prefix(cmd, 'TuneChannel:')
		if tunerleadingzero == True:
			channel = "0" + channel
		
		logger.info("Received: '" + cmd + "' Returning: " + "'OK:Tuning channel to " + channel + "'")
		sys.stderr.write("OK:Tuning channel to " + channel + "\n")
		sys.stderr.flush()
		
		tunersubprocess = subprocess.Popen(shlex.split(tunercmd + " " + channel), stdout=DEVNULL, stdin=DEVNULL)

	else:
		logger.error("Received: Unknown command '" + cmd + "'")
		sys.stderr.write("ERR:Unknown command '" + cmd + "'" + "\n")
		sys.stderr.flush()
