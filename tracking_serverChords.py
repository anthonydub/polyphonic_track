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
cpt = 0

def on_handler(*args):
    global current_note_fft
    current_note_fft = []
    return


def off_handler(*args):
    """
    Send midi off messages to all active notes when we detect guitar string
    is no longer playing sound
    """


def get_relevant_pitches(pitches, c):
	"""
	TODO: Make this method more robust
	This method takes the maximum coefficients of
	a sparse encoding and determines which coefficients correspond to real notes"""
	pitches = pitches[::-1]
	c = c[::-1]
	#print(pitches)
	#print(c)
	rel = [pitches[0]]
	allP = []
	allC = []
	#print("Pitches ", pitches)
	for i in range(0, len(pitches)):
		if pitches[i] in allP: # Si le tab contient la note (harmonie)
			allC[allP.index(pitches[i])] += c[i] # Additione le coeff de la note (harmonie)
		else:
			#print("Note ajoutee ", pitches[i])
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

def sortChord(notes): # Tri les notes pour former les accords
	alphabet = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10 ,'B': 11}
	notes = sorted(notes, key=lambda word: [alphabet.get(c, ord(c)) for c in word])
	return notes

def getDiffNotes(notes): # Retire le numéro des octaves
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
	global cpt
	global baseChord

	#print(notes)

	chord = note_to_chord(notes) # Convert notes to chord
	if len(chord) == 0: # Si c'est pas un accord
		return # Pas de changement de couleur
	chord = str(chord[0]) # Si c'est un accord le passe en String
	
	#print(chord)
	
	chord = list(chord) # Si c'est un accord le passe en list
	"""
	if "/" in chord and chord[-1] != "#" : # Si accord renverse sans # a la fondamentale
		chord[0] = chord[-1] # La fondamentale reprend leur place
	elif  "/" in chord and chord[-1] == "#": # Si accord renverse avec # a la fondamentale
			chord[0] = chord[-2] # La fondamentale et son # reprennent leur place
			chord[1] = chord[-1]
	"""
	if len(chord) > 1 and chord[1] == "#": # Si c'est un accord avec un #
		chord = chord[0]+chord[1] # L'accord prend comme nom sa fondamentale et son #
	else :
		chord = chord[0] # L'accord prend comme non sa fondamentale
	
	if baseChord == "" or baseChord != chord: # Si l'accord n'est pas le meme que l'ancien
		baseChord = chord # L'accord devient l'accord de reference
	print(chord)
	return pickColorChord(chord)


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
		#print(d)
		d = get_relevant_pitches(pitches, coeffs)
		#print(d)
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
        sys.exit()
