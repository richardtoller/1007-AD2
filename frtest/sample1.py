"""
   DWF Python Example
   Author:  Digilent, Inc.
   Revision:  2018-07-19

   Requires:
       Python 2.7, 3
"""

from ctypes import *
from dwfconstants import *
import math
import time
import matplotlib.pyplot as plt
import sys
import numpy


def findPeak(buffer):
    # step through buffer and return the index of the first peak after the first rising-edge zero-cross

    max = 0
    zero_cross_index = 0
    buf_index = 0
    max_index = 0
    last_sample = 0
    # find first rising-edge zero cross
    # ... but first find 5 consecutive samples below 0, to act as a kind of filter
    start_index = 0
    window = [0.0, 0.0, 0.0, 0.0, 0.0]
    window_index = 0
    for v in buffer:
        # shift sample into window buffer
        for p in range(len(window)-1):
            window[p] = window[p+1]
        window[4] = v
        if (window[0] < 0.0) and (window[1] < 0.0) and (window[2] < 0.0) and (window[3] < 0.0) and (window[4] < 0.0):
            break
        else:
            start_index = start_index + 1

    buf_index = 0
    for i in range(start_index, len(buffer)):
        if last_sample < 0.0 and buffer[i] > 0.0:
            zero_cross_index = buf_index
            print("last sample = " + str(last_sample) + ", this sample = " + str(buffer[i]))
            break
        last_sample = buffer[i]
        buf_index = buf_index + 1

    print ("Zero cross at " + str(zero_cross_index))

    # now find maximum value in a quarter-of-the-buffer-size samplers after zero cross
    # this will be the peak that we're interested in
    for n in range (zero_cross_index, buf_index + int(len(buffer)/4)):
        if buffer[n] > max:
            max = buffer[n]
            max_index = n

    return max_index



if sys.platform.startswith("win"):
    dwf = cdll.dwf
elif sys.platform.startswith("darwin"):
    dwf = cdll.LoadLibrary("/Library/Frameworks/dwf.framework/dwf")
else:
    dwf = cdll.LoadLibrary("libdwf.so")

#declare ctype variables
hdwf = c_int()
sts = c_byte()
rgdSamples = (c_double*4000)()

version = create_string_buffer(16)
dwf.FDwfGetVersion(version)
print("DWF Version: "+str(version.value))

#open device
print("Opening first device")
dwf.FDwfDeviceOpen(c_int(-1), byref(hdwf))

if hdwf.value == hdwfNone.value:
    szerr = create_string_buffer(512)
    dwf.FDwfGetLastErrorMsg(szerr)
    print(szerr.value)
    print("failed to open device")
    quit()

cBufMax = c_int()
dwf.FDwfAnalogInBufferSizeInfo(hdwf, 0, byref(cBufMax))
print("Device buffer size: "+str(cBufMax.value))

#set up acquisition
dwf.FDwfAnalogInFrequencySet(hdwf, c_double(20000000.0))
dwf.FDwfAnalogInBufferSizeSet(hdwf, c_int(4000))
dwf.FDwfAnalogInChannelEnableSet(hdwf, c_int(-1), c_bool(True))
dwf.FDwfAnalogInChannelRangeSet(hdwf, c_int(-1), c_double(5))
dwf.FDwfAnalogInChannelFilterSet(hdwf, c_int(-1), filterDecimate)

# set up signal source
dwf.FDwfAnalogOutNodeEnableSet(hdwf, c_int(0), AnalogOutNodeCarrier, c_bool(True))
dwf.FDwfAnalogOutNodeAmplitudeSet(hdwf, c_int(0), AnalogOutNodeCarrier, c_double(0.2))
dwf.FDwfAnalogOutNodeOffsetSet(hdwf, c_int(0), AnalogOutNodeCarrier, c_double(0.0))
dwf.FDwfAnalogOutNodeFrequencySet(hdwf, c_int(0), AnalogOutNodeCarrier, c_double(10000.0))
dwf.FDwfAnalogOutNodeFunctionSet(hdwf, c_int(0), AnalogOutNodeCarrier, funcSine)

dwf.FDwfAnalogOutConfigure(hdwf, c_int(0), c_bool(True))

# wait for signal to settle
time.sleep(2)

print("Starting oscilloscope")
dwf.FDwfAnalogInConfigure(hdwf, c_int(1), c_int(1))

while True:
    dwf.FDwfAnalogInStatus(hdwf, c_int(1), byref(sts))
    if sts.value == DwfStateDone.value :
        break
    time.sleep(0.1)
print("Acquisition done")

dwf.FDwfAnalogInStatusData(hdwf, 0, rgdSamples, 4000) # get channel 1 data
#dwf.FDwfAnalogInStatusData(hdwf, 1, rgdSamples, 4000) # get channel 2 data
dwf.FDwfDeviceCloseAll()


peakIndex = findPeak(rgdSamples)
print ("Peak at " + str(peakIndex) + " is: " + str(rgdSamples[peakIndex]))





#plot window
dc = sum(rgdSamples)/len(rgdSamples)
print("DC: "+str(dc)+"V")

plt.plot(numpy.fromiter(rgdSamples, dtype = numpy.float))
plt.show()
