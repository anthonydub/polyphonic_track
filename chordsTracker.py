"""
If executing this script returns an 'Address already in use' error
make sure there are no processes running on the ports already.
To do that run 'sudo lsof -i:9997' 'sudo lsof -i:9998'
(9997 and 9998 are the default ports used here, so adjust accordingly
if using different ports) This commands brings up list of processes using these ports,
and gives their PID. For each process type, 'kill XXXX' where XXXX is PID.
Also, make sure the pure data patch is disconnected when you do this, otherwise
it will show up in the list and killing the process will quit the patch.
"""


import argparse
import sys
import pickle
import numpy as np
from sklearn.decomposition import sparse_encode
from pythonosc import dispatcher
from pythonosc import osc_server
from pythonosc import osc_message_builder
from pythonosc import udp_client
from random import *
import mido
from utilities_globals import *
from pychord import note_to_chord
import socket
import os

NONZERO_COEFS = 6 # corresponds to maximum possible notes at once
current_note_fft = []
colors = [[1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [1.0, 1.0, 1.0], [0.0, 1.0, 1.0], [0.0, 0.0, 1.0], [1.0, 0.0, 1.0], [0.0, 0.5, 1.0], [0.0, 1.0, 0.5], [0.0, 0.5, 0.5], [0.0, 0.0, 7.0], [0.0, 0.7, 0.7]]
hashMapChord = {}
hashMapNote = {}
index = 0
baseChord = ""

def on_handler(*args):
    global current_note_fft
    print("on") # just for sanity checking
    current_note_fft = []
    return


def off_handler(*args):
    """
    Send midi off messages to all active notes when we detect guitar string
    is no longer playing sound
    """
    midiout.reset()


def get_relevant_pitches(pitches, c):
	"""
	TODO: Make this method more robust
	This method takes the maximum coefficients of
	a sparse encoding and determines which coefficients correspond to real notes"""
	pitches = pitches[::-1]
	midi = note_to_midi(pitches)
	c = c[::-1]
	#print(pitches)
	#print(c)
	rel = [pitches[0]]
	allP = []
	allC = []
	#print("Pitches ", pitches)
	for i in range(0, len(pitches)):
		
		if pitches[i] in allP: # Si le nv tab contient la note (harmonie)
			#print("Note ajoutee ", pitches[i])
			allC[allP.index(pitches[i])] += c[i] # Additione le coeff de la note (harmonie)
		else:
			allP.append(pitches[i]) # Sinon ajoute la note au tableau
			allC.append(c[i])
		#print("Pitches ", allP)
		#print("Coeffs ", allC)
	for i in range(0, len(pitches)):			
		if c[i] > .17:
			pass
		else:
			break
		
		rel += [pitches[i]]
	rel = list(set(rel))
	return rel

def sortChord(notes):
	alphabet = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10 ,'B': 11}
	notes = sorted(notes, key=lambda word: [alphabet.get(c, ord(c)) for c in word])
	return notes

def getDiffNotes(notes):
	for i in range(0, len(notes)):
		if len(notes[i]) == 2:
			notes[i] = notes[i][0:1]
		if len(notes[i]) == 3:
			notes[i] = notes[i][0:2]
	return notes


def pickColorChord(chord):
	global colors
	global hashMapChord
	global index
	global baseChord
	
	if len(chord) > 1 and chord[1] == "#":
		chord = chord[0]+chord[1]
	else :
		chord = chord[0]
	if baseChord == "" or baseChord != chord:
		baseChord = chord
		print(baseChord)
	if not chord in hashMapChord.keys():
		hashMapChord[chord] = colors[index]
		index += 1
	return hashMapChord[chord]

def pickColorNote(note):
	global colors
	global hashMapNote
	
	if not note in hashMapNote.keys():
		hashMapNote[note] = colors[randint(0, len(colors)-1)]
	return hashMapNote[note]
		
def getChords(notes):
	if len(notes) > 1: # If two notes or more know the chord
		if len(note_to_chord(notes)) != 0:
			return pickColorChord(str(note_to_chord(notes)[0]))
	#else: # If only one note returns the note
		#return pickColorNote(str(notes[0]))
	

def sendMIDI_out(data):
    #print('sending notes:', data)
    midi = [int(m) for m in note_to_midi(data)]
    for m in midi:
        midiout.send(mido.Message('note_on', note=m, velocity=100))

"""
def sendOSC_for_PD_synth(comps):
    n = 1
    topones = []
    ampsum = 0
    for i in indices[:3]:
        freq = comps[i]
        freqi = np.argsort(freq)
        topamp = np.max(freq)
        topfreq = freqs[freqi[-1]]
        topones += [(topfreq, topamp)]
        ampsum += topamp
    print("Top 3 freq/amp outputs")
    for i, (freq,amp) in enumerate(topones):
        msgf = '/freq'+str(i+1)
        msga = '/amp'+str(i+1)
        print(msgf)
        print(freq, amp)
        print(pitch(freq))
        client.send_message(msgf, freq)
        client.send_message(msga, amp)
"""

def send(color):
	if color :
		#print("SENDING", str(color))
		#byte_message = bytes(str(color), "utf-8")
		#opened_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		#opened_socket.sendto(byte_message, ("127.0.0.1", 9996))
		client.send_message("/couleur", color)

def fft_handler(*args):
	global current_note_fft
	#print(len(current_note_fft))
	fft = args[1].split()
	fft = np.array([float(i) for i in fft])
	n = normalize_vector(fft.reshape(1, -1))[0]
	if n is None:
		return
	current_note_fft += [n]
	if len(current_note_fft)%7 == 0:
		s = sparse_encode(n.reshape(1, -1), data_per_fret, algorithm='lars',
			n_nonzero_coefs=NONZERO_COEFS)
		s = s[0]
		a = np.argsort(s)
		coeffs = [s[i] for i in a[-NONZERO_COEFS:]]
		pitches = [guitar_notes[i] for i in a[-NONZERO_COEFS:]]
		d = getDiffNotes(pitches)
		d = get_relevant_pitches(pitches, coeffs)
		d = sortChord(d)
		color = getChords(d)
		send(color)

if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip",
        default="127.0.0.1", help="The ip to listen on")
    parser.add_argument("--serverport",
        type=int, default=9997, help="The port for server listen on")
    parser.add_argument("--clientport",
        type=int, default=9994, help="The client port")
    parser.add_argument("--datafile", default="guitare.p",
        help="File to write data to (extension should be '.p')")
    parser.add_argument("--max_notes_per_chord", type=int, default=6)
    parser.add_argument("--midi_port", default='MIDI 1')
    parser.add_argument("--minnote", default='E2')
    parser.add_argument("--maxnote", default='C#6')
    args = parser.parse_args()
    try:
        midiout = mido.open_output(args.midi_port)
    except:
        print("The midi port {} could not be found".format(args.midi_port))
        print("To run with a different midi port, rerun this program with the command line"+
            "argument '--midi_port 'port name goes here' ")
        print("Where 'port name goes here' corresponds to one of the following recognized midi ports:")
        print(mido.get_output_names())
        sys.exit()

    min_note = args.minnote
    max_note = args.maxnote
    guitar_notes = create_notebins(min_note, max_note)
    NONZERO_COEFS = args.max_notes_per_chord
    datafilename = args.datafile
    dispatcher = dispatcher.Dispatcher()
    dispatcher.map("/fftmag", fft_handler)
    dispatcher.map("/on", on_handler)
    dispatcher.map("/off", off_handler)

    try:
        data_per_fret = pickle.load(open(datafilename, "rb"))
    except:
        print("file {} not found".format(datafilename))
        sys.exit()
    data_per_fret = data_to_dict_matrix(data_per_fret)
    client = udp_client.SimpleUDPClient(args.ip, args.clientport)
    #print(data_per_fret.shape)
    server = osc_server.ThreadingOSCUDPServer(
        (args.ip, args.serverport), dispatcher)
    print("Serving on {}".format(server.server_address))
    print("Ctrl+C to quit")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        midiout.close();
        sys.exit()
