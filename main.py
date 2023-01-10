import numpy as np
import soundfile as sf
from datetime import datetime
import keyboard
import threading
import sys
import time
from pathlib import Path
import soundcard as sc
import queue
import pickle
import math
import os
import json

OUTPUT_DIR = "./"
FREQUENCY = 44100
RECS_PER_SEC = 4

configs = None

#TODO how does it act when changing microphone while the program is running ?
#TODO while it uses a lot of CPU when saving a 1hrec, does it still record file on the other threads ?
#TODO: empty buffer once saved ?
def button_is_pressed(key):
	return keyboard.is_pressed(key)

def playSound(fileName):
	if not (os.path.isfile(fileName)):
		return False
	data, fs = sf.read(fileName)
	speaker = sc.default_speaker()
	speaker.play(data, fs)
	return True

#Takes an arr of len n and returns an arr of len n/2.
#Concats 2 indices
#Note: the output array doesn't respect the startIdx
def mergeArrays(arr, startIdx, length):
	# print(f"Start {startIdx} {length}")
	toReturn = []
	amtMerges = math.floor(length / 2)
	for i in range(amtMerges):
		idxA = (startIdx + i * 2) % length
		idxB = (startIdx + 1 + i * 2) % length
		# print(f"{idxA} <- {idxB}")
		toReturn.append(np.concatenate((arr[idxA], arr[idxB])))
	if length % 2 == 1:
		idx = (startIdx + length - 1) % length
		# print(f"since it was uneven I added the idx {idx} of the arr")
		# toReturn[-1] = np.concatenate((toReturn[-1], arr[idx]))
		toReturn.append(arr[idx])
	return toReturn

class InstantReplay():
	def __init__(self):
		self.records = [
			[None] * int((configs["LAST_X_SECONDS"] * RECS_PER_SEC)),
			[None] * int((configs["LAST_X_SECONDS"] * RECS_PER_SEC)),
		]
		self.index = 0
		self.bufferIdx = 0
		self.queueA = queue.Queue()
		self.queueB = queue.Queue()

		self.totalRecs = 0
		self.shouldQuit = False
		self.numThreads = 2
		self.threads = []
		for i in range(self.numThreads):
			self.threads.append(None)
		Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

	def generateOutputName(self):
		return OUTPUT_DIR + "audio_record_" + datetime.now().strftime("%Y-%m-%d_%Hh%Mm%Ss")

	def reset(self):
		self.bufferIdx += 1
		self.index = 0
		self.totalRecs = 0
		while self.queueA.empty() == False:
			self.queueA.get()
		while self.queueB.empty() == False:
			self.queueB.get()

	def saveAudio(self):
		print("Saving...")
		playSound(configs["pathToNotifSoundA"])
		start = time.time()
		lengthVid = min(int(configs["LAST_X_SECONDS"] * RECS_PER_SEC), self.totalRecs)
		startIdx = (self.index - lengthVid) % int(configs["LAST_X_SECONDS"] * RECS_PER_SEC)
		recs = mergeArrays(self.records[self.bufferIdx % 2], startIdx, lengthVid)

		while len(recs) != 1:
			recs = mergeArrays(recs, 0, len(recs))
		end = time.time()
		fileName = self.generateOutputName() + ".mp3"

		print(f"Finished saving P1. ({round(end - start, 2)}s)")
		print(f"{recs[0].shape}")
		sf.write(fileName, recs[0], FREQUENCY)
		print(f"Finished saving P2. (+{round(time.time() - end, 2)}s)")
		playSound(configs["pathToNotifSoundB"])
		self.reset()
		# print("exiting")
		# sys.exit(0)

	def startRecording(self):
		print("Starting to record")
		microphone = sc.get_microphone(id=str(sc.default_microphone().name)).recorder(samplerate=FREQUENCY)
		speaker = sc.get_microphone(id=str(sc.default_speaker().name), include_loopback=True).recorder(samplerate=FREQUENCY)
		self.threads[0] = threading.Thread(target=self.recordingMicThreadFunc, args=(microphone,))
		self.threads[1] = threading.Thread(target=self.recordingSpeakerThreadFunc, args=(speaker,))

		for i in range(self.numThreads):
			self.threads[i].start()
		wasPressed = False
		while self.shouldQuit == False:
			isPressed = button_is_pressed('alt') and button_is_pressed('f9')
			if isPressed and wasPressed == False:
				wasPressed = True
				self.saveAudio()
			if wasPressed and isPressed == False:
				wasPressed = False
			while self.queueA.empty() == False and self.queueB.empty() == False:
				self.records[self.bufferIdx % 2][self.index] = self.queueA.get() + self.queueB.get()
				print(f"saved at idx {self.index}")
				self.index = (self.index + 1) % int(configs["LAST_X_SECONDS"] * RECS_PER_SEC)
				self.totalRecs += 1
			time.sleep(0.05)

	def stopRecording(self):
		print("stopRecording call")
		self.shouldQuit = True
		for i in range(self.numThreads):
			if self.threads[i] != None:
				self.threads[i].join()
		print("stopRecording finish")


	def recordingMicThreadFunc(self, device):
		with device:
			while self.shouldQuit == False:
				rec = device.record(numframes=int(FREQUENCY * (1 / RECS_PER_SEC)))
				self.queueA.put(rec)

	def recordingSpeakerThreadFunc(self, device):
		with device:
			while self.shouldQuit == False:
				rec = device.record(numframes=int(FREQUENCY * (1 / RECS_PER_SEC)))
				self.queueB.put(rec)

def loadConfig():
	fileName = "./instant_replay_config.json"
	global configs
	if not os.path.isfile(fileName):
		print("haha")
		with open(fileName, "w") as f:
			json.dump({
				"pathToNotifSoundA": "",
				"pathToNotifSoundB": "",
				"LAST_X_SECONDS": 600
			}, f)
	with open(fileName, "r") as f:
		configs = json.load(f)


def main():
	loadConfig()
	start = time.time()
	recorder = InstantReplay()
	try:
		recorder.startRecording()
	except KeyboardInterrupt:
		print("Stopping")
		recorder.stopRecording()
	except Exception as e:
		print(str(e))
	finally:
		print("finally")
		recorder.stopRecording()
	print(f"Done ({round(time.time() - start, 2)}s)")




def testSave(records, index, length):
	start = time.time()
	startIdx = (index - length) % int(600 * RECS_PER_SEC)
	recs = mergeArrays(records, startIdx, length)

	while len(recs) != 1:
		recs = mergeArrays(recs, 0, len(recs))
	end = time.time()

	sf.write(file="testfile.mp3", data=recs[0], samplerate=FREQUENCY)
	print(f"{end - start}")

def test():
	rec = None
	# with open("cyka.pickle", "rb") as f:
	# 	rec = pickle.load(f)

	# testSave(rec["recs"], rec["index"], rec["length"])
	while True:
		if button_is_pressed('alt') and button_is_pressed('f9'):
			print("ok")
			break
		print("no")
		time.sleep(0.01)

if __name__ == "__main__":
	main()
	# test()