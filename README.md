# Aviation Data Format Decoder
ADFDecoder.py
Take in a stream of data in Garmin's "Aviation Data Format" and decode it.

This decoder is based on Appendix D of the Garmin 500W Series Installation
Manual Rev E. You can find a copy of the manual here:
    <https://static.garmin.com/pumac/GNS530W_InstallationManual_190-00357-02_.pdf>
    
The contents of appendix D are sufficient to decode the messages, though it's
somewhat incomplete on how to interpret some unlikely corner-cases.

ADFStreamer.py [-s delay] <filename>
Read a file containing Aviation Data Format messages, and stream them one-by-one
to stdout, at <delay> intervals. Default is one second intervals.
