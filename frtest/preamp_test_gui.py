import datetime
import queue
import logging
import signal
import time
import os
import threading
import tkinter as tk
from tkinter import filedialog
import matplotlib.pyplot as plt
from matplotlib.ticker import (MultipleLocator, FormatStrFormatter,
                               AutoMinorLocator)
import numpy as np
from tkinter.scrolledtext import ScrolledText
from tkinter import ttk, VERTICAL, HORIZONTAL, N, S, E, W
from functools import partial
from freq_response import FreqResponseTest
from transient import TransientTest
import getpass
import csv

console = logging.getLogger(__name__)

def CreateResultsFolder(results_path, serial):
    if serial == "":
        serial = "00000000"
    # Create target drectory
    try:
        os.mkdir(results_path)
    except FileExistsError:
        print("Folder exists, no problem...")
    dir_name = results_path + "/" + serial
    try:
        # Create target Directory
        os.mkdir(dir_name)
        console.log(logging.DEBUG,"Directory " + dir_name + " created ")
    except FileExistsError:
        console.log(logging.DEBUG,"Directory " + dir_name + " already exists ")
    return dir_name

def RunFRTest(results_path, serial_number):

    # array of frequencies to test
    freqs = []

    # 10Hz to 1kHz in 10Hz steps
    for f in range(10, 1000, 10):
        freqs.append(f)

    # 1.1kHz to 20kHz in 100Hz steps
    for f in range(1100, 20000, 100):
        freqs.append(f)

    freqs.append(25000)
    freqs.append(30000)
    freqs.append(35000)

    # 40kHz to 200kHz in 10kHz steps
    for f in range(40000, 200000, 10000):
        freqs.append(f)

    if serial_number == "":
        serial_number = "00000000"

    console.log(logging.DEBUG, "FR test started for " + serial_number)
    gains = list()
    starttime = datetime.datetime.now()
    FreqResponseTest(console, freqs, gains)

    # create folder for output
    results_folder_name = CreateResultsFolder(results_path, serial_number) + "/"

    # disable debug output from matplotlib font manager, which otherwise swamps console
    logging.getLogger('matplotlib.font_manager').disabled = True

    fig, ax = plt.subplots()
    ax.plot(freqs, gains, color='#1b598f')
    ax.set_xscale('log')
    ax.set(xlabel='f (Hz)', ylabel='gain (dB)', title=serial_number + ' frequency response')
    # Customize the major grid
    ax.grid(which='major', linestyle='-', linewidth='0.4', color='gray')
    # Customize the minor grid
    ax.grid(which='minor', linestyle=':', linewidth='0.2', color='gray')
    # Minor ticks on the y axis are every 1 unit, use no labels; default NullFormatter.
    ax.yaxis.set_minor_locator(MultipleLocator(1))

    #plt.show()

    file_name_stem = results_folder_name + "FR_" + "{:04d}".format(starttime.year) + "{:02d}".format(starttime.month) + "{:02d}".format(
        starttime.day) + "_" + "{:02d}".format(starttime.hour) + "{:02d}".format(starttime.minute) + "{:02d}".format(
        starttime.second)

    plt.savefig(file_name_stem + '.png')

    # write results to csv file
    with open(file_name_stem + '.csv', 'w', newline='') as csvfile:
        spamwriter = csv.writer(csvfile, delimiter=',',
                                quotechar='|', quoting=csv.QUOTE_MINIMAL)
        spamwriter.writerow(['serial number:', serial_number])
        spamwriter.writerow(['freq (Hz)', 'gain (dB)'])
        gain_index = 0
        for freq in freqs:
            spamwriter.writerow([freq, gains[gain_index]])
            gain_index = gain_index + 1

    return

def RunTransientTest(results_path, serial_number):

    # array of frequencies to test
    freq = 1000 #  1kHz

    if serial_number == "":
        serial_number = "00000000"

    console.log(logging.DEBUG, "Transient test started for " + serial_number)
    sine_waveform = list()
    square_waveform = list()
    x_axis = list()
    sample_period = [0.1]

    starttime = datetime.datetime.now()

    TransientTest(console, sample_period, sine_waveform, 1) # sine
    TransientTest(console, sample_period, square_waveform, 0) # square

    print("sample period: ", sample_period)
    print("length=" + str(len(sine_waveform)))

    # populate x axis times
    sample_index = 0
    for v in sine_waveform:
        x_axis.append(sample_period[0] * sample_index * 1000.0)
        sample_index = sample_index + 1

    # create folder for output
    results_folder_name = CreateResultsFolder(results_path, serial_number) + "/"

    # disable debug output from matplotlib font manager, which otherwise swamps console
    logging.getLogger('matplotlib.font_manager').disabled = True

    fig, ax = plt.subplots()
    ax.plot(x_axis, sine_waveform, color='#1b598f')
    ax.plot(x_axis, square_waveform, color='#ab433a')

    ax.set(xlabel='t (ms)', ylabel='V', title=serial_number + ' transient response')
    # Customize the major grid
    ax.grid(which='major', linestyle='-', linewidth='0.4', color='gray')
    # Customize the minor grid
    ax.grid(which='minor', linestyle=':', linewidth='0.2', color='gray')
    # Minor ticks on the y axis are every 1 unit, use no labels; default NullFormatter.
    ax.yaxis.set_minor_locator(MultipleLocator(1))

    #plt.show()

    file_name_stem = results_folder_name + "TR_sine_" + "{:04d}".format(starttime.year) + "{:02d}".format(starttime.month) + "{:02d}".format(
        starttime.day) + "_" + "{:02d}".format(starttime.hour) + "{:02d}".format(starttime.minute) + "{:02d}".format(
        starttime.second)

    plt.savefig(file_name_stem + '.png')

    # write results to csv file
    with open(file_name_stem + '.csv', 'w', newline='') as csvfile:
        spamwriter = csv.writer(csvfile, delimiter=',',
                                quotechar='|', quoting=csv.QUOTE_MINIMAL)
        spamwriter.writerow(['serial number:', serial_number])
        spamwriter.writerow(['freq (Hz)', 'gain (dB)'])
        sample_index = 0
        for sample in sine_waveform:
            spamwriter.writerow([x_axis[sample_index], sample, square_waveform[sample_index]])
            sample_index = sample_index + 1

    return



class QueueHandler(logging.Handler):
    """Class to send logging records to a queue
    It can be used from different threads
    The ConsoleUi class polls this queue to display records in a ScrolledText widget
    """
    # Example from Moshe Kaplan: https://gist.github.com/moshekaplan/c425f861de7bbf28ef06
    # (https://stackoverflow.com/questions/13318742/python-logging-to-tkinter-text-widget) is not thread safe!
    # See https://stackoverflow.com/questions/43909849/tkinter-python-crashes-on-new-thread-trying-to-log-on-main-thread
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(record)

class ConsoleUi:
    """Poll messages from a logging queue and display them in a scrolled text widget"""

    def __init__(self, frame):
        self.frame = frame
        # Create a ScrolledText wdiget
        self.scrolled_text = ScrolledText(frame, state='disabled', height=12)
        self.scrolled_text.grid(row=0, column=0, sticky=(N, S, W, E))
        self.scrolled_text.configure(font='TkFixedFont')
        self.scrolled_text.tag_config('INFO', foreground='black')
        self.scrolled_text.tag_config('DEBUG', foreground='green')
        self.scrolled_text.tag_config('WARNING', foreground='orange')
        self.scrolled_text.tag_config('ERROR', foreground='red')
        self.scrolled_text.tag_config('CRITICAL', foreground='red', underline=1)
        # Create a logging handler using a queue
        self.log_queue = queue.Queue()
        self.queue_handler = QueueHandler(self.log_queue)
        formatter = logging.Formatter('%(asctime)s: %(message)s')
        self.queue_handler.setFormatter(formatter)
        console.addHandler(self.queue_handler)
        # Start polling messages from the queue
        self.frame.after(100, self.poll_log_queue)

    def display(self, record):
        msg = self.queue_handler.format(record)
        self.scrolled_text.configure(state='normal')
        self.scrolled_text.insert(tk.END, msg + '\n', record.levelname)
        self.scrolled_text.configure(state='disabled')
        # Autoscroll to the bottom
        self.scrolled_text.yview(tk.END)

    def poll_log_queue(self):
        # Check every 100ms if there is a new message in the queue to display
        while True:
            try:
                record = self.log_queue.get(block=False)
            except queue.Empty:
                break
            else:
                self.display(record)
        self.frame.after(100, self.poll_log_queue)

class FormUi:

    def __init__(self, frame):
        self.frame = frame
        # Create a text field to enter the serial number
        self.serialNumber = tk.StringVar()
        self.serialNumber.set("00000000")
        ttk.Label(self.frame, text='Serial no:').grid(column=0, row=1, sticky=W)
        ttk.Entry(self.frame, textvariable=self.serialNumber, width=25).grid(column=1, row=1, sticky=(W, E))

        # Add a button to start the FR test
        self.buttonFRTest = tk.Button(self.frame, text='FR test...', bg='#6da66c', command=self.do_fr_test)
        self.buttonFRTest.grid(column=1, row=5, sticky=W)

        # Add a button to start the transient test
        self.buttonTrTest = tk.Button(self.frame, text='trans test...', bg='#6da66c', command=self.do_transient_test)
        self.buttonTrTest.grid(column=1, row=6, sticky=W)

        # Add select results folder
        self.buttonFolder = ttk.Button(self.frame, text='results:', command=lambda:self.do_set_results_path(self.results_file_path.get()))
        self.buttonFolder.grid(column=0, row=4, sticky=W)

        # Create a text field for the results file path, with some default text
        self.results_file_path = tk.StringVar()
        self.results_file_path.set("/home/" + getpass.getuser() + "/test_results")
        ttk.Label(self.frame, textvariable='results folder:').grid(column=1, row=4, sticky=(W, E))
        ttk.Entry(self.frame, textvariable=self.results_file_path, width=25).grid(column=1, row=4, sticky=(W, E))

    def do_set_results_path(self, initial_path):
        file_path = filedialog.askdirectory(initialdir=initial_path)
        self.results_file_path.set(file_path)

    def do_fr_test(self):
        x=threading.Thread(target=RunFRTest, args=(self.results_file_path.get(),self.serialNumber.get()))
        x.start()

    def do_transient_test(self):
        x=threading.Thread(target=RunTransientTest, args=(self.results_file_path.get(),self.serialNumber.get()))
        x.start()


class App:

    def __init__(self, root):
        self.root = root
        root.title('Hatherstone pre-amp test program')
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        # Create the panes and frames
        vertical_pane = ttk.PanedWindow(self.root, orient=VERTICAL)
        vertical_pane.grid(row=0, column=0, sticky="nsew")
        horizontal_pane = ttk.PanedWindow(vertical_pane, orient=HORIZONTAL)
        vertical_pane.add(horizontal_pane)
        form_frame = ttk.Labelframe(horizontal_pane, text="Unit Under Test")
        form_frame.columnconfigure(1, weight=1)
        horizontal_pane.add(form_frame, weight=1)
        console_frame = ttk.Labelframe(horizontal_pane, text="Console")
        console_frame.columnconfigure(0, weight=1)
        console_frame.rowconfigure(0, weight=1)
        horizontal_pane.add(console_frame, weight=1)
        #third_frame = ttk.Labelframe(vertical_pane, text="Third Frame")
        #vertical_pane.add(third_frame, weight=1)
        # Initialize all frames
        self.form = FormUi(form_frame)
        self.console = ConsoleUi(console_frame)
        self.root.protocol('WM_DELETE_WINDOW', self.quit)
        self.root.bind('<Control-q>', self.quit)
        signal.signal(signal.SIGINT, self.quit)

    def quit(self, *args):
        self.root.destroy()

def main():
    logging.basicConfig(level=logging.DEBUG)
    root = tk.Tk()
    app = App(root)
    app.root.mainloop()

if __name__ == '__main__':
    main()