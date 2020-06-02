"""
   transient.py
   Author:  Hatherstone
   Revision:  2020-05-26

   Requires:
       Python 2.7, 3
   Desciption:
   - generates 1kHz sin, tri and square wave
   - records data on Scope channel 1
   - ....
"""

from ctypes import *
from dwfconstants import *
import math
import time
import matplotlib.pyplot as plt
import sys
import numpy
import wave
import datetime
import os
import array
import tkinter as tk
import logging


def TransientTest(console, sample_period, waveform, sine_not_square ):
    if sys.platform.startswith("win"):
        dwf = cdll.dwf
    elif sys.platform.startswith("darwin"):
        dwf = cdll.LoadLibrary("/Library/Frameworks/dwf.framework/dwf")
    else:
        dwf = cdll.LoadLibrary("libdwf.so")

    # instrument states decoded
    decode_instrument_state = [
        "DwfStateReady",
        "DwfStateArmed",
        "DwfStateDone",
        "DwfStateTriggered or DwfStateRunning",
        "DwfStateConfig",
        "DwfStatePrefill",
        "6 - undefined",
        "DwfStateWait"
    ]

    # declare ctype variables
    hdwf = c_int()
    sts = c_byte()
    sample_buffer_size = 8000
    rgdSamples = (c_double * sample_buffer_size)()
    amplitude_v = 0.2  # peak, not pk-pk
    offset_v = 0.0
    freq_hz = 1000
    max_sample_freq = 100000000

    console.log(logging.DEBUG, "Transient start")

    # get DWF version
    version = create_string_buffer(16)
    dwf.FDwfGetVersion(version)
    print("DWF Version: " + str(version.value))
    console.log(logging.DEBUG, "DWF Version: " + str(version.value))

    # open device
    print("Opening first device")
    console.log(logging.DEBUG, "Opening first device")
    dwf.FDwfDeviceOpen(c_int(-1), byref(hdwf))

    if hdwf.value == hdwfNone.value:
        szerr = create_string_buffer(512)
        dwf.FDwfGetLastErrorMsg(szerr)
        print(str(szerr.value))
        print("failed to open device")
        console.log(logging.ERROR, "failed to open device")
        quit()

    cBufMax = c_int()
    dwf.FDwfAnalogInBufferSizeInfo(hdwf, 0, byref(cBufMax))
    print("Device buffer size: " + str(cBufMax.value))

    # set up signal source
    dwf.FDwfAnalogOutNodeEnableSet(hdwf, c_int(0), AnalogOutNodeCarrier, c_bool(True))
    dwf.FDwfAnalogOutNodeAmplitudeSet(hdwf, c_int(0), AnalogOutNodeCarrier, c_double(amplitude_v))
    dwf.FDwfAnalogOutNodeOffsetSet(hdwf, c_int(0), AnalogOutNodeCarrier, c_double(offset_v))
    dwf.FDwfAnalogOutNodeFrequencySet(hdwf, c_int(0), AnalogOutNodeCarrier, c_double(freq_hz))
    if sine_not_square == 1:
        console.log(logging.DEBUG, "Sine...")
        dwf.FDwfAnalogOutNodeFunctionSet(hdwf, c_int(0), AnalogOutNodeCarrier, funcSine)
    else:
        console.log(logging.DEBUG, "Square...")
        dwf.FDwfAnalogOutNodeFunctionSet(hdwf, c_int(0), AnalogOutNodeCarrier, funcSquare)

    dwf.FDwfAnalogOutConfigure(hdwf, c_int(0), c_bool(True))
    # wait for signal to settle
    time.sleep(2)

    # set up acquisition
    sample_freq = sample_buffer_size * freq_hz / 2.0
    dwf.FDwfAnalogInFrequencySet(hdwf, c_double(sample_freq))
    dwf.FDwfAnalogInBufferSizeSet(hdwf, c_int(sample_buffer_size))
    dwf.FDwfAnalogInChannelEnableSet(hdwf, c_int(-1), c_bool(True))
    dwf.FDwfAnalogInChannelRangeSet(hdwf, c_int(-1), c_double(5))
    dwf.FDwfAnalogInChannelFilterSet(hdwf, c_int(-1), filterDecimate)

    # set sample frequency so we get at least two full cycles of the waveform in the buffer
    sample_freq = sample_buffer_size * freq_hz / 2.0
    if sample_freq > max_sample_freq:
        sample_freq = max_sample_freq
    print("Freq = " + str(freq_hz) + "Hz, Sample freq = " + str(sample_freq) + "Hz")
    sample_period[0] = 1.0 / sample_freq

    dwf.FDwfAnalogInFrequencySet(hdwf, c_double(sample_freq))
    dwf.FDwfAnalogInConfigure(hdwf, c_int(1), c_int(1))

    timeout_count = 0
    while True:
        time.sleep(0.05)
        success = dwf.FDwfAnalogInStatus(hdwf, c_int(1), byref(sts))
        if success == 0:
            #console.log(logging.ERROR, "FDwfAnalogInStatus failed!")
            szerr = create_string_buffer(512)
            dwf.FDwfGetLastErrorMsg(szerr)
            print(szerr.value)
            console.log(logging.ERROR, "FDwfAnalogInStatus failed! " + str(szerr.value) )

        if sts.value == DwfStateDone.value:
            break
        timeout_count = timeout_count + 1
        if timeout_count > 100: # 5 second timeout
            console.log(logging.ERROR, "TIMEOUT WT FOR FDwfAnalogInStatus=DwfStateDone")
            console.log(logging.ERROR, "FDwfAnalogInStatus=" + decode_instrument_state[sts.value])
            break

    dwf.FDwfAnalogInStatusData(hdwf, 0, rgdSamples, sample_buffer_size)  # get channel 1 data
    # dwf.FDwfAnalogInStatusData(hdwf, 1, rgdSamples, 4000) # get channel 2 data

    for r in rgdSamples:
        waveform.append(r)

    dc = sum(rgdSamples) / len(rgdSamples)

    max_v = max(rgdSamples)
    min_v = min(rgdSamples)

    print("DC: " + str(dc) + "V, max: " + str(max_v) + "V, min:" + str(min_v))

    dwf.FDwfAnalogOutReset(hdwf, c_int(0))
    dwf.FDwfDeviceCloseAll()

    print(" done")
    console.log(logging.DEBUG, "Transient test complete")
    return
