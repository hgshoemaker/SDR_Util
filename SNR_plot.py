from rtlsdr import RtlSdr
from matplotlib.pyplot import psd, xlabel, ylabel, show
import numpy as np

sdr = RtlSdr()

# configure device
sdr.sample_rate = 2.4e6
sdr.center_freq = 4995e4
sdr.gain = 0
sdr.freq_correction = 56   # PPM

samples = sdr.read_samples(256*1024)
sdr.close()

# Remove DC spike
#samples = samples - np.mean(samples)

# use matplotlib to estimate and plot the PSD
psd(samples, NFFT=1024, Fs=sdr.sample_rate/1e6, Fc=sdr.center_freq/1e6)
xlabel('Frequency (MHz)')
ylabel('Relative power (dB)')

show()