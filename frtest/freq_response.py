"""
   freq_response.py
   Author:  Hatherstone
   Revision:  2020-05-26

   Requires:
       Python 2.7, 3
   Desciption:
   - generates swept frequency sine wave on AWG1
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


def FreqResponseTest(console, freqs, gains):
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
    max_sample_freq = 100000000

    console.log(logging.DEBUG, "Frequency response start")

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
    dwf.FDwfAnalogOutNodeFunctionSet(hdwf, c_int(0), AnalogOutNodeCarrier, funcSine)
    dwf.FDwfAnalogOutNodeAmplitudeSet(hdwf, c_int(0), AnalogOutNodeCarrier, c_double(amplitude_v))
    dwf.FDwfAnalogOutNodeOffsetSet(hdwf, c_int(0), AnalogOutNodeCarrier, c_double(offset_v))
    dwf.FDwfAnalogOutNodeFrequencySet(hdwf, c_int(0), AnalogOutNodeCarrier, c_double(freqs[0]))
    dwf.FDwfAnalogOutConfigure(hdwf, c_int(0), c_bool(True))
    # wait at least 2 seconds for the offset to stabilize
    time.sleep(2)

    # set up acquisition
    sample_freq = sample_buffer_size * freqs[0] / 2.0
    dwf.FDwfAnalogInFrequencySet(hdwf, c_double(sample_freq))
    dwf.FDwfAnalogInBufferSizeSet(hdwf, c_int(sample_buffer_size))
    dwf.FDwfAnalogInChannelEnableSet(hdwf, c_int(-1), c_bool(True))
    dwf.FDwfAnalogInChannelRangeSet(hdwf, c_int(-1), c_double(5))
    dwf.FDwfAnalogInChannelFilterSet(hdwf, c_int(-1), filterDecimate)

    for freq in freqs:
        # set up signal source
        dwf.FDwfAnalogOutNodeFrequencySet(hdwf, c_int(0), AnalogOutNodeCarrier, c_double(freq))
        dwf.FDwfAnalogOutConfigure(hdwf, c_int(0), c_bool(True))

        # wait for signal to settle
        if freq < 10:
            time.sleep(1.0)
        elif freq < 200:
            time.sleep(0.2)
        else:
            time.sleep(0.01)

        # set sample frequency so we get at least two full cycles of the sine wave in the buffer
        sample_freq = sample_buffer_size * freq / 2.0
        if sample_freq > max_sample_freq:
            sample_freq = max_sample_freq
        print("Freq = " + str(freq) + "Hz, Sample freq = " + str(sample_freq) + "Hz")

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

        if timeout_count > 100:
            break

        dwf.FDwfAnalogInStatusData(hdwf, 0, rgdSamples, sample_buffer_size)  # get channel 1 data
        # dwf.FDwfAnalogInStatusData(hdwf, 1, rgdSamples, 4000) # get channel 2 data

        dc = sum(rgdSamples) / len(rgdSamples)
        print("DC: " + str(dc) + "V")
        max_v = max(rgdSamples)
        min_v = min(rgdSamples)
        pk_pk_v = max_v - min_v
        pk_v = pk_pk_v / 2.0
        dc_v = max_v + min_v
        if pk_pk_v != 0.0:
            gain_db = 20.0 * math.log(pk_v / amplitude_v, 10)
        else:
            gain_db = -10000.0

        h_str = f'{gain_db:.1f}'
        pk_str = f'{pk_v:.3f}'
        dc_str=f'{dc_v:.3f}'
        console.log(logging.INFO, "H:" + h_str + ", pk:" + pk_str + ", dc:" + dc_str + " f="+ str(freq/1000) + "kHz")

        gains.append(gain_db)

    dwf.FDwfAnalogOutReset(hdwf, c_int(0))
    dwf.FDwfDeviceCloseAll()

    print(" done")
    console.log(logging.DEBUG, "Frequency response complete")
    return
