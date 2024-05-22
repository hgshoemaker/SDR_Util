
# This script enables testing NESDRs' noise floor levels, SNR (signal generator required), as well as the levels of the TCXO (oscillator's) harmonics (2nd, 3rd, 4th, etc).
# It supports exporting figures and .CSV files for reference.
# Note that you cannot enable SNR_Mode and Harmonic_Mode at once. Only one of the two modes can be enabled at a time. You can turn them both off to measure the noise floor only.
# You will need to install the necessary Python libraries in your CMD prompt using: pip install pyrtlsdr matplotlib pyvisa statistics numpy scipy
# Next, download the latest Osmocomm drivers for rtl-sdr from https://downloads.osmocom.org/binaries/windows/rtl-sdr/, extract the folder to C:\ then add the full directory path to your "PATH" in the system environment variables

# It is internally used by Nooelec's engineers for design testing and improvement purposes.
# This script is a property of Nooelec Inc and distributed for free use. Please tag Nooelec whenever you share this code.
# We hope this could be of help. Enjoy using the script!

import numpy
import pyvisa
import matplotlib
import os
from pylab import *
from rtlsdr import RtlSdr
import matplotlib.pyplot as plt
import datetime
import math
import csv
import statistics
from scipy.fft import fft, ifft

t = time.time()

################## Inputs ##################

Project_ID = '027_02_04'
Project_Name = 'NESDR Nano 3'
Project_Version = 'v5.0a2'
Project_DUT = 'DUT12_USB hub_no enclosure'
File_Comment = 'Full_Sweep_-100dBm_50dB_2.4MSPS'
Save_Formats = ['png', 'pdf']

# Sweep Parameters
freq_start = 25                  	# Sweep start frequency in MHz. If this is set below freq_ds, direct sampling measurement will be automatically enabled
freq_stop = 1750              	    # Sweep stop frequency in MHz. Direct sampling measurement will be automatically enabled for values lower than freq_ds
freq_ds = 25                        # Frequency below which direct sampling is enabled on Q pair and above which quadrature sampling is enabled. Unit is in MHz
rtlsdr_fs = 2.4                     # RTL-SDR sampling rate in MHz
freq_unit = 'MHz'                   # Frequency Unit
rtlsdr_gain = 50                    # RTL-SDR tuner gain in dB
rtlsdr_agc_mode = 0                 # Set RTL2832U automatic gain control. 0=off, 1=on
rtlsdr_frmlen = 2048                # RTL-SDR output data frame size
rtlsdr_ppm = 0                      # RTL-SDR tuner parts per million correction
Harmonic_Mode = 'off'              	# Harmonics mode will only measure harmonics. Note that you cannot enable SNR_Mode with this mode. Only one of the two modes can be enabled at a time.
                                    # Also note that the frequency range must be at least twice the Harmonic_Freq for it to work. The purpose is to compare levels of multiples of Harmonic_Freq
Harmonic_Freq = 28.8                # The fundemantal Harmonic Frequency (TCXO frequency in MHz)

# SNR Mode
SNR_Mode = 'on'                    # Note that you cannot enable Harmonic_Mode with this mode. Only one of the two modes can be enabled at a time.
SNR_StepSize = 3.6                  # Usually 1.5 times the value of rtlsdr_fs
SigGenPwLvl = -100                   # Power level of the signal generator
SigGenIPAddr = '192.168.1.68'       # Signal Generator's IP Address on the local network (must be connected)

# PARAMETERS (Handle carefully!)
nfft = 1024*8             	        # number of points in FFTs (2^something)
overlap = 0.5                       # FFT overlap to counter rolloff
nfrmdump = 100                      # number of frames to dump after retuning (to clear buffer)
fft_avg = 100                	    # number of times fft results is averaged

################## Calculations ##################

# Frequency unit convertion
if freq_unit == 'MHz':
    Freq_Factor = 1e6
elif freq_unit == 'KHz':
    Freq_Factor = 1e3
elif freq_unit == 'GHz':
    Freq_Factor = 1e9

freq_start = freq_start * Freq_Factor
freq_stop = freq_stop * Freq_Factor
rtlsdr_fs = rtlsdr_fs * Freq_Factor
Harmonic_Freq = Harmonic_Freq * Freq_Factor
SNR_StepSize = SNR_StepSize * Freq_Factor

# Initializing Variables
rm = pyvisa.ResourceManager()

rtlsdr_tunerfreq = numpy.arange(freq_start, freq_stop, rtlsdr_fs*overlap)
rtlsdr_results_ptr = int((rtlsdr_frmlen-rtlsdr_frmlen*overlap)/2)
rtlsdr_results_freq = numpy.zeros((len(rtlsdr_tunerfreq), int(rtlsdr_frmlen*overlap)))
rtlsdr_results_dB = numpy.zeros((len(rtlsdr_tunerfreq), int(rtlsdr_frmlen*overlap)))

if Harmonic_Mode == "on":
    rtlsdr_tunerfreq = numpy.arange(math.ceil(rtlsdr_tunerfreq[0]/Harmonic_Freq)*Harmonic_Freq, floor(rtlsdr_tunerfreq[-1]/Harmonic_Freq)*Harmonic_Freq, Harmonic_Freq)
    rtlsdr_results_dB = numpy.zeros(len(rtlsdr_tunerfreq))
    rtlsdr_results_freq = numpy.zeros(len(rtlsdr_tunerfreq))

if SNR_Mode == "on":
    rtlsdr_tunerfreq = numpy.arange(rtlsdr_tunerfreq[0], rtlsdr_tunerfreq[-1], SNR_StepSize)
    rtlsdr_results_dB = numpy.zeros(len(rtlsdr_tunerfreq))
    rtlsdr_results_freq = numpy.zeros(len(rtlsdr_tunerfreq))
    rtlsdr_SNR_results_dB = numpy.zeros(len(rtlsdr_tunerfreq))

    # Communicating with the signal generator
    #SG = rm.open_resource('TCPIP0::' + str(SigGenIPAddr) + '::inst0::INSTR')
    SG = rm.open_resource('USB0::0x1AB1::0x0992::DSG3A154400080::INSTR')
    SG.timeout = 5000
    SG_Name = SG.query('*IDN?')
    print(SG_Name)
    SG.write(':LEV ' + str(SigGenPwLvl))  # Set amplitude level
    SG.write(':OUTP OFF')  # Turn RF -OFF- initially

# Configuring SDR
try:
    sdr = RtlSdr()
    sdr.center_freq = rtlsdr_tunerfreq[0]     # Hz
    sdr.sample_rate = rtlsdr_fs  # Hz
except:
    print("Could not set center_freq to " + str(rtlsdr_tunerfreq[0]) + "\n Please select a valid start frequency..")
    exit()

# Setting up realtime figure
progress_bar = numpy.chararray((1, 50))
progress_bar[:] = '-'
plt.ion()
if SNR_Mode == 'on' and Harmonic_Mode == 'off': fig, ax = plt.subplots(1, 2)
else: fig, ax = plt.subplots(1, 1)
plt.show()

for k in range(len(rtlsdr_tunerfreq)):

    try:
        sdr.center_freq = rtlsdr_tunerfreq[k]
    except:
        print("Could not set center_freq to " + str(rtlsdr_tunerfreq[k]) + "\n Trying next bin.. \n")
        sdr = RtlSdr()
        continue

    if rtlsdr_tunerfreq[k] < freq_ds*Freq_Factor:
        try:
            sdr.set_direct_sampling(2)
            if rtlsdr_ppm != 0: sdr.freq_correction = rtlsdr_ppm
            sdr.set_agc_mode(rtlsdr_agc_mode)
            sdr.set_manual_gain_enabled(1)
            sdr.gain = rtlsdr_gain
        except:
            print("Could not set one or more of the tuner parameters. Trying next bin.. \n")
            continue

    elif rtlsdr_tunerfreq[k] >= freq_ds*Freq_Factor:
        try:
            if rtlsdr_ppm != 0: sdr.freq_correction = rtlsdr_ppm
            sdr.set_direct_sampling(0)
            sdr.set_agc_mode(rtlsdr_agc_mode)
            sdr.set_manual_gain_enabled(1)
            sdr.gain = rtlsdr_gain
        except:
            print("Could not set one or more of the tuner parameters. Trying next bin.. \n")
            continue

    rtlsdr_data_avg_dB = numpy.zeros((fft_avg, rtlsdr_frmlen))

    os.system('cls')
    if SNR_Mode == "on": print('Using Signal Generator: ' + SG_Name + '\n')
    print('Scanning @ ' + str(rtlsdr_tunerfreq[k]/Freq_Factor) + str(freq_unit))
    progress_bar[0][1:math.ceil((k+1)/len(rtlsdr_tunerfreq)*50)] = 'X'
    bar = progress_bar.astype('|S1').tobytes().decode('utf-8')
    print('\n' + str(bar) + ' ' + str(floor((k+1)/len(rtlsdr_tunerfreq)*100)) + '% \n')
    elapsed = round((time.time() - t),1)
    lineLength = print('Elapsed Time   = ' + str(elapsed) + ' secs')

    SNR_Loop = 1  # number of times the SDR will have the data read. 1 if NF mode 2 if SNR mode

    if SNR_Mode == "on":
        SNR_Loop = 2

    for cycles in range(SNR_Loop):

        if cycles == 1:
            SG.write(':FREQ ' + str(rtlsdr_tunerfreq[k]/1e6+rtlsdr_fs/1e6/10) + 'MHz')
            SG.write(':OUTP ON')
            time.sleep(0.2)

        for j in range(nfrmdump): # fetch and dump #nfrmdump frames from SDR as a first step before taking clean and reliable readings
            try:
                rtlsdr_data = sdr.read_samples(rtlsdr_frmlen)
            except:
                print('Error dumping data from SDR. Skipping step.. \n')
                continue

        for j in range(fft_avg): # fetch clean frames from SDR

            try:
                rtlsdr_data = sdr.read_samples(rtlsdr_frmlen)
            except:
                print('Error dumping data from SDR. Skipping step.. \n')
                continue

            rtlsdr_data = rtlsdr_data - mean(rtlsdr_data)
            rtlsdr_data_fft = fft(rtlsdr_data)
            rtlsdr_data_freq = numpy.linspace(-rtlsdr_fs/2+rtlsdr_tunerfreq[k], rtlsdr_fs/2+rtlsdr_tunerfreq[k], len(rtlsdr_data_fft))
            rtlsdr_data_dB = abs(numpy.fft.fftshift(rtlsdr_data_fft))
            rtlsdr_data_dB = 20 * numpy.log10((rtlsdr_data_dB+0.0000000001)/(rtlsdr_frmlen))
            rtlsdr_data_avg_dB[j] = rtlsdr_data_dB
            rtlsdr_data_avg_dB[rtlsdr_data_avg_dB<-150] = mean(rtlsdr_data_avg_dB[j])

        y = numpy.mean(rtlsdr_data_avg_dB, axis=0)

        if SNR_Mode == 'on' and Harmonic_Mode == 'off':
            ax[cycles].cla()
            ax[cycles].plot(rtlsdr_data_freq/1000000, y)
            if not ax[0].get_label():
                ax[0].set_ylim(-120, 0)
                ax[0].set_xlabel('Frequency (MHz)')
                ax[0].set_ylabel('Noise Floor (dBFS)')
            if not ax[1].get_label():
                ax[1].set_ylim(-120, 0)
                ax[1].yaxis.set_label_position("right")
                ax[1].yaxis.set_ticks_position("right")
                ax[1].set_xlabel('Frequency (MHz)')
                ax[1].set_ylabel('Signal Strength (dBFS)')
            fig.canvas.flush_events()
        
        else:
            ax.cla()
            ax.plot(rtlsdr_data_freq/1000000, y)
            if not ax.get_label():
                ax.set_ylim(-120, 0)
                ax.set_xlabel('Frequency (MHz)')
                ax.set_ylabel('Noise Floor (dBFS)')
            fig.canvas.flush_events()

        if Harmonic_Mode == "on":
            rtlsdr_results_freq[k] = rtlsdr_tunerfreq[k]
            rtlsdr_results_dB[k] = numpy.max(numpy.mean(rtlsdr_data_avg_dB[:, rtlsdr_results_ptr:-1-rtlsdr_results_ptr+1], axis=0))

        elif SNR_Mode == "on" and cycles == 0:
            rtlsdr_results_freq[k] = rtlsdr_tunerfreq[k]
            rtlsdr_results_dB_mean = numpy.mean(rtlsdr_data_avg_dB[:, rtlsdr_results_ptr:-1-rtlsdr_results_ptr+1], axis=0)
            rtlsdr_results_dB_mean[rtlsdr_results_dB_mean<-150] = mean(rtlsdr_results_dB_mean[k])
            rtlsdr_results_dB[k] = mean(rtlsdr_results_dB_mean)

        elif SNR_Mode == "on" and cycles == 1:
            Maximum = numpy.max(numpy.mean(rtlsdr_data_avg_dB[:, rtlsdr_results_ptr:-1-rtlsdr_results_ptr+1], axis=0))
            rtlsdr_SNR_results_dB[k] = Maximum - rtlsdr_results_dB[k]
            SG.write(':OUTP OFF')
            
        else:
            rtlsdr_results_freq[k][:] = rtlsdr_data_freq[rtlsdr_results_ptr:-1-rtlsdr_results_ptr+1]
            rtlsdr_results_dB[k][:] = numpy.mean(rtlsdr_data_avg_dB[:, rtlsdr_results_ptr:-1-rtlsdr_results_ptr+1], axis=0)
            # rtlsdr_results_dB_mean[rtlsdr_results_dB_mean<-150] = mean(rtlsdr_results_dB_mean[k][:])
            #rtlsdr_results_dB[k] = mean(rtlsdr_results_dB)

if SNR_Mode == "on" and Harmonic_Mode == "off":
    SG.write(':OUTP OFF')

################## Processing Results ##################

plt.close()

plt.ion()
plt.figure(1)
if SNR_Mode == 'on' and Harmonic_Mode == 'off':
    plt.plot(rtlsdr_tunerfreq/1000000, rtlsdr_results_dB)
    plt.title(Project_Name + ' - ' + Project_Version + ' - ' + Project_DUT + ' SNR Mode_Noise Floor (dBFS) vs F (MHz)')
    plt.ylabel('SNR Mode_Noise Floor (dBFS)')
elif SNR_Mode == 'off' and Harmonic_Mode == 'off':
    plt.plot(rtlsdr_results_freq.T/1000000, rtlsdr_results_dB.T, linewidth=0.5)
    plt.title(Project_Name + ' - ' + Project_Version + ' - ' + Project_DUT + ' Noise Floor (dBFS) vs F (MHz)')
    plt.ylabel('Noise Floor (dBFS)')
else: 
    plt.plot(rtlsdr_tunerfreq/1000000, rtlsdr_results_dB)
    plt.title(Project_Name + ' - ' + Project_Version + ' - ' + Project_DUT + ' Harmonics Level (dBFS) vs F (MHz)')
    plt.ylabel('Harmonics Level (dBFS)')
plt.ylim(-120, 0)
plt.grid()
plt.xlabel('Frequency in MHz')

current_directory = os.path.dirname(os.path.abspath(__file__))
print(current_directory)
final_directory = os.path.join(current_directory, r'data')
final_directory2 = os.path.join(current_directory, r'plots')
if not os.path.exists(final_directory):
    os.makedirs(final_directory)
if not os.path.exists(final_directory2):
    os.makedirs(final_directory2)

for L in list(Save_Formats):
    plt.savefig(current_directory + '\\plots\\' + Project_ID + '_' + Project_Name + '_' + Project_Version + '_' + Project_DUT + '_' + File_Comment + '_Noise Floor vs F_SNR Mode_' + SNR_Mode + '_Harmonic Mode_' + Harmonic_Mode + '.' + L)

with open(current_directory + '\\data\\' + Project_ID + '_' + Project_Name + '_' + Project_Version + '_' + Project_DUT + '_' + File_Comment + '_Noise Floor vs F_SNR Mode_' + SNR_Mode + '_Harmonic Mode_' + Harmonic_Mode + '.csv', 'w', encoding='UTF8', newline='') as f:
    writer_NF_vs_F = csv.writer(f)
    Data_NF_vs_F = numpy.vstack((rtlsdr_tunerfreq.T, rtlsdr_results_dB.T))
    writer_NF_vs_F.writerows(Data_NF_vs_F.T)

if SNR_Mode == "on":

    plt.figure(2)
    plt.plot(rtlsdr_tunerfreq/1000000, rtlsdr_SNR_results_dB)
    plt.grid()
    plt.ylim(-10, 80)
    xlabel('Frequency in MHz')
    ylabel('SNR (dB)')
    plt.title(Project_Name + ' - ' + Project_Version + ' - ' + Project_DUT + ' - ' + ' SNR (dB) vs F (MHz)')

    for L in list(Save_Formats):
        plt.savefig(current_directory + '\\plots\\' + Project_ID + '_' + Project_Name + '_' + Project_Version + '_' + Project_DUT + '_' + File_Comment + '_SNR vs F_SNR Mode ' + SNR_Mode + '_Harmonic_Mode_' + Harmonic_Mode + '.' + L)

    with open(current_directory + '\\data\\' + Project_ID +'_' + Project_Name + '_' + Project_Version + '_' + Project_DUT + '_' + File_Comment + '_SNR vs F_SNR Mode ' + SNR_Mode + '_Harmonic_Mode_' + Harmonic_Mode + '.csv', 'w', encoding='UTF8', newline='') as f:
        writer_SNR_vs_F = csv.writer(f)
        Data_SNR_vs_F = numpy.vstack((rtlsdr_tunerfreq.T, rtlsdr_SNR_results_dB.T))
        writer_SNR_vs_F.writerows(Data_SNR_vs_F.T)

input("\nAll done! \n\nPress Enter to end...")
plt.close()
SW01_03_RTL_SDR_Sweep_1v8.py
Displaying SW01_03_RTL_SDR_Sweep_1v8.py.