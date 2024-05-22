import numpy as np
import csv

from rtlsdr import RtlSdr

sdr = RtlSdr()

# Get user input
center_freq = float(input("Enter center frequency in Hz: "))
power_level = int(input("Enter power level (1-5): "))

# Configure device
sdr.sample_rate = 2040000  # Hz
sdr.center_freq = center_freq
sdr.freq_correction = 56   # PPM
sdr.gain = 'auto'

samples = sdr.read_samples(512)


# Calculate signal power and noise power
signal_power = np.abs(np.mean(samples))**2
noise_power = np.var(samples)

# Calculate SNR
epsilon = 1e-10  # small constant to avoid division by zero
snr = 10 * np.log10((signal_power + epsilon) / (noise_power + epsilon))

print(f'SNR: {snr} dB')

# Store results and user input to a CSV file
with open('results.csv', 'a', newline='') as file:
    writer = csv.writer(file)
    writer.writerow([center_freq, power_level, snr])