#!/usr/bin/env python

"""
    Read a data stream from stdin, write a series of decoded sentences to
    stdout.
"""

import re
import signal
import sys

__author__ = "Mark A. Matthews"
__copyright__ = "Copyright 2024 Mark A. Matthews"
__license__ = "Public Domain"
__version__ = "1.0"


TYPE1_SENTENCE_IDS = (b'z', b'A', b'B', b'C', b'D', b'E', b'G', b'I', b'K',
                      b'L', b'Q', b'S', b'T', b'l')


def decodeGarmin500SeriesData(dataStream):
    '''
    Decodes a buffered Garmin 500 Series RS-232 data message.

    This decoder is based on Appendix D of the Garmin 500W Series Installation
    Manual Rev E

    :param dataStream: The RS-232 data stream as a single buffered message
    string.
    :return: List of decoded sentences with their fields.

    '''

    decodedSentences = []

    # Split the data stream into individual sentences
    lines = dataStream.splitlines()

    for line in lines:
        # Check for Type 1 sentences
        if line.startswith(TYPE1_SENTENCE_IDS):
            try:
                decodedSentence = decodeType1Sentence(line.decode('ascii'))
            except UnicodeDecodeError:
                print("Error: Non-ASCII characters encountered. "
                      "Skipping sentence.")

        # Check for Type 2 sentences
        elif re.match(rb'^w[0-9][0-9].*', line):
            decodedSentence = decodeType2Sentence(line)

        else:
            print(f"Unknown sentence format: '{line}'")
            continue

        decodedSentences.append(decodedSentence)

    return decodedSentences


def decodeType1Sentence(sentence):
    '''
    Type 1 Sentences deal with the current 3D position, and course details to
    the next waypoint.

    :param sentence:  An individual sentence within a particular message
    :return: Dictionary of the decoded sentence.

    '''

    data = {"Type": "Type 1"}

    # Check sentence type based on the initial character and decode accordingly

    match sentence[0]:
        case  "z":
            # GPS altitude in feet . Format is "z<feet>"
            data["GPS Altitude (ft)"] = int(sentence[1:])

        case  "A":
            # Latitude: Format is "A<direction><degrees>.<minutes>"
            data["Latitude"] = \
               f"{sentence[1]} {sentence[3:5]}°{sentence[6:8]}.{sentence[8:]}'"

        case  "B":
            # Longitude: Format is "B<direction><degrees>.<minutes>"
            data["Longitude"] = \
               f"{sentence[1]} {sentence[3:6]}°{sentence[7:9]}.{sentence[9:]}'"

        case  "C":
            # Track in degrees (assuming it's the rest of the string as a float)
            data["Track (degrees)"] = float(sentence[1:])

        case  "D":
            # Ground Speed: Format is "D<knots>"
            data["Ground Speed (knots)"] = int(sentence[1:])

        case  "E":
            if sentence[1:3] == "--":
                # Waypoint not defined
                data["Distance to Wpt (nm)"] = sentence[1:]
            else:
                # Distance to next waypoint: Format is "E<deci-nm>"
                data["Distance to Wpt (nm)"] = float(sentence[1:]) / 10.0

        case  "G":
            if sentence[1:3] == "--":
                # Waypoint not defined
                data["XTK Error (nm)"] = sentence[1:]
            else:
                # Cross track error: Format is G<L|R><centi-nm>
                data["XTK Error (nm)"] = sentence[1] + \
                                          str(float(sentence[2:]) / 100.0)

        case  "I":
            if sentence[1:3] == "--":
                # Waypoint not defined
                data["TRK (degrees)"] = sentence[1:]
            else:
                # Desired track (degrees): Format is I<deci-degrees>"
                data["TRK (degrees)"] = float(sentence[1:]) / 10.0

        case  "K":
            # Next waypoint: Format is "K<ccccc>" The documentation calls this
            # the "destination" waypoint, but it's actually the name for the
            # waypoint in the active leg.
            data["Wpt"] = sentence[1:]

        case  "L":
            if sentence[1:3] == "--":
                # Waypoint not defined
                data["BRG (degrees)"] = sentence[1:]
            else:
                # Bearing to next waypoint: Format is "L<deci-degrees>"
                data["BRG (degrees)"] = float(sentence[1:]) / 10.0

        case  "Q":
            # Magnetic Variation: Format is "Q<E|W><deci-degrees>"
            data["Mag Var (degrees)"] = sentence[1] + \
                                         str(float(sentence[2:]) / 10.0)

        case  "S":
            # NAV valid flag: Format is "S----<N|->"
            data["NAV Valid"] = sentence[5] == "-"

        case  "T":
            # Warning status: Format is always "T<--------->"
            data["Warning Status"] = sentence[1:]

        case  "l":
            if sentence[1:3] == "--":
                # Waypoint not defined
                data["Distance to Dest (nm)"] = sentence[1:]
            else:
                # Distance to destination: Format is "l<deci-nm>". This really
                # is the destination waypoint.
                data["Distance to Dest (nm)"] = float(sentence[1:]) / 10.0

    return data


ACTIVE_LEG = 0x20
LAST_LEG = 0x40
LEG_NUM_MASK = 0x1f
SOUTH_NORTH = 0x80
EAST_WEST = 0x80
LAT_DEG_MASK = 0x7f
MIN_MASK = 0x3f
CENTIMIN_MASK = 0x7f


def decodeType2Sentence(sentence):
    '''

    Type 2 messages address the active flight plan. Each sentence describe a
    waypoint and it's 2d position. Within each sentence is a flag that
    indicates which one is the active leg, and which one is the final leg.

    :param sentence:  An individual sentence within a particular message
    :return: Dictionary of the decoded sentence.

    '''

    data = {"Type": "Type 2"}

    data["Id"] = sentence[0:3].decode('ascii')
    lastLeg = (sentence[3]) & LAST_LEG != 0
    activeLeg = (sentence[3]) & ACTIVE_LEG != 0
    legNo = (sentence[3]) & LEG_NUM_MASK
    data["Seq"] = str(legNo)
    if activeLeg and lastLeg:
        data["Seq"] += " Active Last"
    elif activeLeg:
        data["Seq"] += " Active     "
    elif lastLeg:
        data["Seq"] += "        Last"
    else:
        data["Seq"] += "            "

    if len(sentence) < 5:
        # No waypoints defined
        return data

    data["Wpt"] = sentence[4:9].decode('ascii')
    latDir = "S" if (sentence[9]) & SOUTH_NORTH else "N"
    latDeg = (sentence[9]) & LAT_DEG_MASK
    latMin = (sentence[10]) & MIN_MASK
    latCentiMin = (sentence[11]) & CENTIMIN_MASK
    data["Lat"] = latDir + str(latDeg) + "° " + str(float(latMin) +
                                                    float(latCentiMin) / 10.0)
    lonDir = "W" if (sentence[12]) & EAST_WEST else "E"
    lonDeg = sentence[13]
    lonMin = sentence[14] & MIN_MASK
    lonCentiMin = (sentence[15]) & CENTIMIN_MASK
    data["Lon"] = lonDir + str(lonDeg) + "° " + str(float(lonMin) +
                                                    float(lonCentiMin) / 10.0)

    # Magnetic Variation is encoded as 16 bits twos-compliment, in 16ths of
    # degrees. Here we swizzle it into an int, then a float.
    mv = sentence[16] << 8 | sentence[17]
    mvNeg = -1 if mv & 0x8000 else 1
    if mvNeg == -1:
        mv = ((0xffff - mv) + 1) * mvNeg
    data["Mag Var"] = mv / 16.0

    return data


def handler(signum, frame):  # pylint: disable=unused-argument
    print("Quitting...")
    sys.exit(0)


STX = b'\x02'
ETX = b'\x03'


if __name__ == "__main__":
    buffer = bytearray()
    isBuffering = False
    preBufferEnd = 0

    signal.signal(signal.SIGINT, handler)

    print("Waiting for a full message to go by....")

    while True:
        # Read one byte at a time from standard input
        byte = sys.stdin.buffer.read(1)

        if byte == b'':
            # End of input stream (e.g., Ctrl+D), stop processing
            print("Exiting...")
            sys.exit(1)

        if byte == ETX:
            break

    print("Listening for Garmin 500 Series data (STX/ETX delimited)...")

    while True:
        # Read one byte at a time from standard input
        byte = sys.stdin.buffer.read(1)

        if byte == b'':
            # End of input stream (e.g., Ctrl+D), stop processing
            print("Exiting...")
            sys.exit(0)

        if byte == STX and not isBuffering:
            # Start buffering when STX is detected
            buffer = bytearray()
            isBuffering = True
            continue

        # Weirdly, Type 2 messages include binary values buried within
        # otherwise ASCII messages - because of this we treat the incoming
        # values as a bytearray. Also, since there's binary values in the
        # Type 2 messages, we have to watch out for embedded ETX values. This
        # can happen if the degrees/mins/centimin values coincidentally
        # equal 3. We mitigate this a bit by looking for a linefeed (0x0a)
        # before a valid ETX, but even that is vulnerable to a false detection
        # of a degree/min happens to be 10 deg 03 min, or 10 min 03 centimin.
        # We try to mitigate that a bit more by trying to scan for
        # carraige return, then linefeed, and then STX, but even that can
        # falsely trigger when 13 deg 10 min 3 centimin is encountered.
        # So just be careful when operating around the west coast of equitorial
        # Africa.

        if isBuffering:
            if preBufferEnd == 2:
                if byte == ETX:
                    # Stop buffering and decode when ETX is detected
                    preBufferEnd = 0
                    isBuffering = False
                    decoded_data = decodeGarmin500SeriesData(buffer)

                    # Output the decoded data
                    print("\nDecoded Garmin 500 Series Data:")
                    for entry in decoded_data:
                        print(entry)

                    # Reset buffer and wait for next STX
                    buffer = bytearray()
                else:
                    preBufferEnd = 0

            if byte == b'\r' and preBufferEnd == 0:
                # Potential end of record coming up
                preBufferEnd = 1

            if byte == b'\n' and preBufferEnd == 1:
                # Now its really coming up
                preBufferEnd = 2

            # Accumulate data into the buffer
            buffer += byte
