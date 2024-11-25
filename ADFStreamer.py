#!/usr/bin/env python

"""
    Read a file of messages in Aviation Data Format, and stream them out
    at a periodic rate. Default is one message per second, can be tuned with
    "-s <sec>", with sec expressed as a non-negative float.

    Based on Appendix D of the Garmin 500W Series Installation
    Manual Rev E

"""

import argparse
import signal
import sys
import time


__author__ = "Mark A. Matthews"
__copyright__ = "Copyright 2024 Mark A. Matthews"
__license__ = "Public Domain"
__version__ = "1.0"


def handler(signum, frame):  # pylint: disable=unused-argument
    """ Catch a control-C """
    print("Quitting...", file=sys.stderr)
    sys.exit(0)


STX = b'\x02'
ETX = b'\x03'

# Tell pylint to shutup about the  module variables it thinks should be
# constant.
# pylint: disable-msg=C0103

if __name__ == "__main__":
    # Handle command-line arguments
    parser = argparse.ArgumentParser(description="Stream Aviation Data Format "
                                                 "messages with controlled "
                                                 "delay.")
    parser.add_argument("filename", type=str, help="Input file containing "
                                                   "ADF messages.")
    parser.add_argument("-s", "--delay", type=float, default=1.0,
                        help="Delay between messages in seconds "
                             "(default: 1.0).")
    args = parser.parse_args()

    if args.delay < 0.0:
        print("-s delay must not be negative", file=sys.stderr)
        sys.exit(1)

    buffer = bytearray()
    isBuffering = False
    preBufferEnd = 0
    messages = []

    signal.signal(signal.SIGINT, handler)

    # Read messages from the specified file
    try:
        with open(args.filename, "rb") as file:
            # Peek at the first byte in the file
            byte = file.read(1)
            if byte == b'':
                # End of input stream (e.g., Ctrl+D), stop processing
                print("File is empty", file=sys.stderr)
                sys.exit(1)

            if byte == STX:
                # File starts with STX. We'll assume it's truly the
                # beginning of a message. Head back to the start.
                file.seek(0)
            else:
                print("Waiting for a full message to go by....",
                      file=sys.stderr)

                while True:
                    # Read one byte at a time from standard input
                    byte = file.read(1)

                    if byte == b'':
                        # End of input stream (e.g., Ctrl+D), stop processing
                        print("Exiting...", file=sys.stderr)
                        sys.exit(1)

                    if byte == ETX:
                        break

                print("Found first ETX.", file=sys.stderr)

            while True:
                # Read one byte at a time from standard input
                byte = file.read(1)

                if byte == b'':
                    # End of input stream (e.g., Ctrl+D), stop processing
                    print("No more messages...", file=sys.stderr)
                    break

                if byte == STX and not isBuffering:
                    # Start buffering when STX is detected
                    buffer = bytearray()
                    buffer += byte
                    isBuffering = True
                    continue

                if isBuffering:
                    if preBufferEnd == 2:
                        if byte == ETX:
                            buffer += byte
                            # Stop buffering this message
                            preBufferEnd = 0
                            isBuffering = False
                            messages.append(buffer)
                            continue

                        preBufferEnd = 0

                    if byte == b'\r' and preBufferEnd == 0:
                        # Potential end of record coming up
                        preBufferEnd = 1

                    if byte == b'\n' and preBufferEnd == 1:
                        # Now its really coming up
                        preBufferEnd = 2

                    # Accumulate data into the buffer
                    buffer += byte
    except FileNotFoundError:
        print(f"Error: File '{args.filename}' not found.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file '{args.filename}': {e}", file=sys.stderr)
        sys.exit(1)

    # Now emit messages[] one element at a time, to stdout
    print(f"Stream {len(messages)} messages at {args.delay} messages/second",
          file=sys.stderr)

    for msg in messages:
        sys.stdout.buffer.write(msg)
        sys.stdout.buffer.flush()
        time.sleep(args.delay)
