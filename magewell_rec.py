#!/usr/bin/python

# External MythTV Recorder Implementation
# https://www.mythtv.org/wiki/ExternalRecorder
#
# To run:
# ./magewell_rec.py --logpath=/var/log/mythtv > ~/test_video_output.ts
# 
# Then type commands followed by return to trigger events
# e.g. Version? -> StartStreaming -> SendBytes -> SendBytes -> SendBytes -> StopStreaming -> CloseRecorder

import os
import sys
import time
import datetime
import getopt
import shlex
import subprocess
import signal
from threading import Event, Thread
from subprocess import call
import logging


def remove_prefix(text, prefix):
	if text.startswith(prefix):
		return text[len(prefix):]
	return text  # or whatever
	
def reader(f, buffer, bytes):
	#print "Reader thread started...\n"
	while True:
		line=f.read(bytes)
		if line:
			buffer.append(line)
		else:
			break

def streamer(f, buffer):
	while True:
		if(buffer):
			f.write(buffer.pop(0))

def main(argv):

	recordcmd = '/usr/local/ffmpeg-3.4.1/ffmpeg -loglevel error -thread_queue_size 256 -f alsa -i hw:2,0 -framerate 60 -thread_queue_size 512 -f v4l2 -i /dev/video0 -acodec aac -af "volume=20dB" -vcodec h264_nvenc -b:a 128k -b:v 6M -f mpegts pipe:1'
	# tunercmd = '/usr/local/bin/change_channel' # use a script to tune channel
	# tunercmd = '/usr/local/bin/6200ch -m -q; sleep 2; /usr/local/bin/6200ch -4 -n0 -e' # in case we want to send a menu command to wake up, then tune channel
	tunercmd = '/usr/local/bin/6200ch -4 -n0 -e' # quickest tuning
	
	version = "0.1"
	ready = True
	hastuner = True
	blocksize = 1000000 # 1MB (~1 seconds of video)
	
	quiet = False
	
	# Logging
	logger = logging.getLogger('Magewell Recorder')
	logfilepath = "/var/log/mythtv/" + os.path.splitext(os.path.basename(__file__))[0] + "." + str(datetime.datetime.now().strftime('%Y%m%d%H%M%S')) + "." + str(os.getpid()) + ".log" # logging messages to a file in the directory logpath with filenames in the format: applicationName.date.pid.log
	loglevel = "debug" # In descending order: emerg, alert, crit, err, warning, notice, info, debug -> mapped to python log levels: debug(), info(), warning(), error() and critical()
	logging.basicConfig(filename=logfilepath, level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
	logger.debug("Received arguments: " + str(argv))
	
	
	blockbuffer=[]
	recsubprocess = None
	readerthread=None
	streamerthread=None
	sendbytesrequestcount=0
	totalbytes=0
	
	DEVNULL = open(os.devnull, 'wb')
	
	# read command line arguments
# 	try:
# 		logger.debug("Received arguments: " + str(argv))
# 		
# 		opts, args = getopt.getopt(argv,"hqv",["quiet","loglevel=","logpath=", "syslog="])
# 	except getopt.GetoptError as err:
# 		logger.debug("Fatal option error: " + str(err))
# 		sys.stderr.write("Fatal option error: " + str(err))
# 		sys.exit(2)
# 		
# 	for opt, arg in opts:
# 		if opt == '-h':
# 			print 'magewell.py -i <inputfile> -o <outputfile>'
# 			sys.exit()
# 		elif opt in ("-q", "--quiet"):
# 			quiet = True
# 		elif opt in ("--loglevel"):
# 			loglevel = arg
# 		elif opt in ("--logpath"):
# 			logpath = arg
# 	
# 	if logpath != "" and quiet==False:
# 		logfilepath = logpath + "/" + os.path.basename(__file__) + str(datetime.datetime.now().strftime('%Y%m%d%H%M%S')) + str(os.getpid()) + ".log"
# 		
# 		# translate MythTV log levels to Python logging levels
# 		if loglevel in ["emerg", "alert", "crit"]:
# 			pythonloglevel = logging.CRITICAL
# 			
# 		elif loglevel=="err":
# 			pythonloglevel = logging.ERROR
# 		
# 		elif loglevel=="warning":
# 			pythonloglevel = logging.WARNING
# 		
# 		elif loglevel in ["notice", "info"]:
# 			pythonloglevel = logging.INFO
# 		
# 		elif loglevel=="debug":
# 			pythonloglevel = logging.DEBUG
# 		
# 		logging.basicConfig(filename=logfilepath, level=pythonloglevel, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
		
	
	while True:
		cmd = sys.stdin.readline().rstrip('\n')
		if cmd == 'Version?':
			logger.info("Received: 'Version?' Returning: " + "'OK:"+version+"'")
			sys.stderr.write("OK:"+version+"\n")
			sys.stderr.flush()
		
		elif cmd == 'IsOpen?':
			if ready == True:
				logger.debug("Received: 'IsOpen?' returning: " + "'OK:Open'")
				sys.stderr.write("OK:Open"+"\n")
			else:
				logger.debug("Received: 'IsOpen?' returning: " + "'OK:No'")
				sys.stderr.write("OK:No"+"\n")
			sys.stderr.flush()
		
		elif cmd == 'CloseRecorder':
			logger.info("Received: 'CloseRecorder'")
			
			# empty remaining buffer
			bufferbytes=0
			while blockbuffer:
				out=blockbuffer.pop(0) # leftpop
				bufferbytes += sys.getsizeof(out)
				sys.stderr.write("OK:Sending "+str(sys.getsizeof(out))+" bytes"+"\n")
				sys.stderr.flush()
				sys.stdout.write(out)
			
			logger.debug("Flushing remaining buffer ("+ str(bufferbytes) +" bytes)")
			logger.info("Returning: 'OK:Terminating'")
			logger.info("Summary: " + str(sendbytesrequestcount) + " 'SendBytes' requests made from server (" + str(totalbytes + bufferbytes) +" total bytes)")
			
			sys.stderr.write("OK:Terminating"+"\n")
			sys.stderr.flush()
			break
		
		elif cmd == 'HasTuner?':
			if hastuner == True:
				logger.debug("Received: 'HasTuner?' Returning: " + "'OK:Yes'")
				sys.stderr.write("OK:Yes"+"\n")
			else:
				logger.debug("Received: 'HasTuner?' Returning: " + "'OK:No'")
				sys.stderr.write("OK:No"+"\n")
			sys.stderr.flush()
		
		elif cmd == 'HasPictureAttributes?':
			logger.debug("Received: 'HasPictureAttributes?' Returning: " + "'OK:No'")
			
			sys.stderr.write("OK:No"+"\n")
			sys.stderr.flush()
		
		elif cmd == 'LockTimeout?':
			logger.debug("Received: 'LockTimeout?' Returning: " + "'OK:20000'")
			
			sys.stderr.write("OK:20000"+"\n")
			sys.stderr.flush()
		
		elif cmd == 'SignalStrengthPercent?':
			logger.debug("Received: 'SignalStrengthPercent?' Returning: " + "'OK:100'")
			
			sys.stderr.write("OK:100"+"\n")
			sys.stderr.flush()
		
		elif cmd == 'HasLock?':
			logger.debug("Received: 'HasLock?' Returning: " + "'OK:Yes'")
			
			sys.stderr.write("OK:Yes"+"\n")
			sys.stderr.flush()
		
		elif cmd == 'FlowControl?':
			logger.debug("Received: 'FlowControl?' Returning: " + "'OK:Polling'")
			
			sys.stderr.write("OK:Polling"+"\n")
			sys.stderr.flush()
	
		elif cmd.startswith('BlockSize:'): #  'BlockSize:<value>':
			logger.debug("Received: '" + cmd + "' Returning: " + "'OK'")
			
			blocksize = int(remove_prefix(cmd, 'BlockSize:'))
			
			sys.stderr.write("OK:BlockSize set to " + str(blocksize) + "\n")
			sys.stderr.flush()
		
		elif cmd == 'StartStreaming':
			# start subprocess with video capture command that sends the transport stream to 
			# the subprocess STDOUT
		
			recsubprocess = subprocess.Popen(shlex.split(recordcmd), stdout=subprocess.PIPE, stdin=DEVNULL)
		
			# TODO: catch errors from the subprocess and set ready=FALSE until resolved
		
			# start thread to read blocksize bytes from the subprocess STDOUT into blockbuffer
			readerthread=Thread(target=reader,args=(recsubprocess.stdout, blockbuffer, blocksize))
			readerthread.daemon=True
			readerthread.start()
			
			logger.info("Received: 'StartStreaming' Returning: " + "'OK:Started'")
			
			sys.stderr.write("OK:Started"+"\n")
			sys.stderr.flush()
		
			# start thread to push the buffer contents to the main process STDOUT
# 			streamerthread=Thread(target=streamer,args=(sys.stdout, blockbuffer))
# 			streamerthread.daemon=True
# 			streamerthread.start()
		
		elif cmd == 'StopStreaming':

			if(recsubprocess != None):
				recsubprocess.terminate()
				# recsubprocess.send_signal(signal.SIGINT)
				time.sleep(0.5)
			
				recsubprocess=None
				readerthread=None
				streamerthread=None
				
				logger.info("Received: 'StopStreaming'")
			
				sys.stderr.write("OK:Stopped"+"\n")
			
				# empty remaining buffer
				bufferbytes=0
				while blockbuffer:
					out=blockbuffer.pop(0) # leftpop
					bufferbytes += sys.getsizeof(out)
					totalbytes += sys.getsizeof(out)
					sys.stderr.write("OK:Sending "+str(sys.getsizeof(out))+" bytes"+"\n")
					sys.stderr.flush()
					sys.stdout.write(out)
					
				logger.debug("Flushing remaining buffer ("+ str(bufferbytes) +" bytes)")
				logger.info("Returning: 'OK:Stopped'")
			
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
			
			sendbytesrequestcount += 1
			
			if ready==True:
				if blockbuffer:
					out=blockbuffer.pop(0) # leftpop
					totalbytes += sys.getsizeof(out)
					
					logger.debug("Received: 'SendBytes' Returning: " + "'OK:Sending "+str(sys.getsizeof(out))+" bytes'")
										
					sys.stderr.write("OK:Sending "+str(sys.getsizeof(out))+" bytes"+"\n")
					sys.stderr.flush()
					sys.stdout.write(out)
				else:
					sys.stderr.write("OK"+"\n")
			else:
				sys.stderr.write("ERR:Recorder not ready!"+"\n")
				sys.stderr.flush()
		

		elif cmd.startswith('TuneChannel:'): # 'TuneChannel:<value>':
			logger.info("Received: '" + cmd + "' Returning: " + "'OK'")
			
			channel = remove_prefix(cmd, 'TuneChannel:')
			tunersubprocess = subprocess.Popen(tunercmd + " 0" + channel, shell=True, stdout=DEVNULL, stdin=DEVNULL)
			sys.stderr.write("OK:Tuning channel to " + channel + "\n")
			sys.stderr.flush()
		
		else:
			sys.stderr.write("ERR:Unknown command '" + cmd + "'" + "\n")
			sys.stderr.flush()
		
		
		
if __name__ == "__main__":
	main(sys.argv[1:])
