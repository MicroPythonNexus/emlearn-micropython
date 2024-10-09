
import math
import struct
import array

from iir_python import IIRFilter
import emliir
import eml_iir_q15

class IIRFilterEmlearn:

    def __init__(self, coefficients):
        c = array.array('f', coefficients)
        self.iir = emliir.new(c)
    def process(self, samples):
        self.iir.run(samples)

class IIRFilterEmlearnFixed:

    def __init__(self, coefficients):
        c = eml_iir_q15.convert_coefficients(coefficients)
        self.iir = eml_iir_q15.new(c)
    def process(self, samples):
        self.iir.run(samples)


# A method for computing A weighting filters etc for any sample-rate
# https://www.dsprelated.com/thread/10546/a-weighting-filter

def assert_array_typecode(arr, typecode):
    actual_typecode = str(arr)[7:8]
    assert actual_typecode == typecode, (actual_typecode, typecode)

a_filter_16k = [
    1.0383002230320646, 0.0, 0.0, 1.0, -0.016647242439959593, 6.928267021369795e-05,
    1.0, -2.0, 1.0, 1.0, -1.7070508390293027, 0.7174637059318595,
    1.0, -2.0, 1.0, 1.0, -1.9838868447331497, 0.9839517531763131
]

@micropython.native
def rms_micropython_native(arr):
    acc = 0.0
    for i in range(len(arr)):
        v = arr[i]
        p = (v * v)
        acc += p
    mean = acc / len(arr)
    out = math.sqrt(mean)
    return out

# Using a limited-precision aware approach based on Cumulative Moving Average
# https://www.codeproject.com/Articles/807195/Precise-and-safe-calculation-method-for-the-averag
@micropython.viper
def rms_micropython_viper(arr) -> object:
    buf = ptr16(arr) # XXX: input MUST BE h/uint16 array
    l = int(len(arr))
    cumulated_average : int = 0
    cumulated_remainder : int = 0
    addendum : int = 0
    n_values : int = 0
    for i in range(l):
        v = int(buf[i])
        value = (v * v) # square it
        n_values += 1
        addendum = value - cumulated_average + cumulated_remainder
        cumulated_average += addendum // n_values
        cumulated_remainder = addendum % n_values

    # sqrt it
    out = math.sqrt(cumulated_average)
    return out

@micropython.native
def time_integrate_native(arr, initial, time_constant, samplerate):
    acc = initial
    dt = 1.0/samplerate
    a = dt / (time_constant + dt)
    #print('a', a)

    for i in range(len(arr)):
        v = arr[i]
        p = (v * v) # power is amplitude squared
        # exponential time weighting aka 1st order low-pass filter
        #acc = (a*p) + ((1-a)*acc) 
        acc = acc + a*(p - acc) # exponential time weighting aka 1st order low-pass filter
        #acc += p

    return acc

# Use C module for data conversion
# @micropython.native with a for loop is too slow
from emlearn_arrayutils import linear_map
def int16_to_float(inp, out):
    return linear_map(inp, out, -2**15, 2**15, -1.0, 1.0)

def float_to_int16(inp, out):
    return linear_map(inp, out, -1.0, 1.0, -2**15, 2**15)

class SoundlevelMeter():

    def __init__(self, buffer_size,
        samplerate,
        mic_sensitivity,
        time_integration=0.125,
        frequency_weighting='A',
        ):

        self._buffer_size = buffer_size
        self._sensitivity_dbfs = mic_sensitivity

        buffer_duration = buffer_size / samplerate
        assert buffer_duration <= 0.125

        self._power_integrated_fast = 0.0
        self._samplerate = samplerate
        self._time_integration = time_integration

        if not frequency_weighting:
            self.frequency_filter = None
        elif frequency_weighting == 'A':
            #self.frequency_filter = IIRFilter(a_filter_16k)
            self.frequency_filter = IIRFilterEmlearn(a_filter_16k)
            #self.frequency_filter = IIRFilterEmlearnFixed(a_filter_16k)

            self.float_array = array.array('f', (0 for _ in range(buffer_size)))
        else:
            raise ValueError('Unsupported frequency_weighting')

    def process(self, samples):
        assert len(self.float_array) == self._buffer_size
        assert len(samples) == self._buffer_size
        assert_array_typecode(samples, 'h')

        # Apply frequency weighting
        if self.frequency_filter:
            int16_to_float(samples, self.float_array)
            self.frequency_filter.process(self.float_array)
            float_to_int16(self.float_array, samples)

            #self.frequency_filter.process(samples)


        #print(self.float_array)
        #print(samples)

        spl_max = 94 - self._sensitivity_dbfs
        ref = 2**15

        # no integration - "linear"
        if self._time_integration is None:
            rms = rms_micropython_native(samples)
            # FIXME: causes math domain error
            #rms = rms_micropython_viper(samples)
        else:
            p = time_integrate_native(samples,
                self._power_integrated_fast,
                self._time_integration,
                self._samplerate,
            )
            self._power_integrated_fast = p
            rms = math.sqrt(p)

        level = 20*math.log10(rms/ref)
        level += (spl_max)

        return level

def read_wave_header(wav_file):
    # based on https://github.com/miketeachman/micropython-i2s-examples/blob/master/examples/wavplayer.py
    # Copyright (c) 2022 Mike Teachman

    chunk_ID = wav_file.read(4)
    if chunk_ID != b"RIFF":
        raise ValueError("WAV chunk ID invalid")
    chunk_size = wav_file.read(4)
    format = wav_file.read(4)
    if format != b"WAVE":
        raise ValueError("WAV format invalid")
    sub_chunk1_ID = wav_file.read(4)
    if sub_chunk1_ID != b"fmt ":
        raise ValueError("WAV sub chunk 1 ID invalid")
    sub_chunk1_size = wav_file.read(4)
    audio_format = struct.unpack("<H", wav_file.read(2))[0]
    num_channels = struct.unpack("<H", wav_file.read(2))[0]

    sample_rate = struct.unpack("<I", wav_file.read(4))[0]
    byte_rate = struct.unpack("<I", wav_file.read(4))[0]
    block_align = struct.unpack("<H", wav_file.read(2))[0]
    bits_per_sample = struct.unpack("<H", wav_file.read(2))[0]

    # usually the sub chunk2 ID ("data") comes next, but
    # some online MP3->WAV converters add
    # binary data before "data".  So, read a fairly large
    # block of bytes and search for "data".

    binary_block = wav_file.read(200)
    offset = binary_block.find(b"data")
    if offset == -1:
        raise ValueError("WAV sub chunk 2 ID not found")

    first_sample_offset = 44 + offset

    return num_channels, sample_rate, bits_per_sample, first_sample_offset

    
def int16_from_bytes(buf, endianness='<'):
    
    fmt = endianness + 'h'
    gen = (struct.unpack(fmt, buf[i:i+3])[0] for i in range(0, len(buf), 2))
    arr = array.array('h', gen)
    assert len(arr) == len(buf)//2
    return arr


def read_wav(file, samplerate, frames):
    """
    """

    file_channels, file_sr, file_bitdepth, data_offset = read_wave_header(file)
    assert samplerate == file_sr, (samplerate, file_sr)
    # only int16 mono is supported
    assert file_channels == 1, file_channels
    assert file_bitdepth == 16, file_bitdepth

    #samples = array.array('h', (0 for _ in range(frames)))
    file.seek(data_offset)

    while True:
        data = file.read(2*frames)
        read_frames = len(data)//2
        samples = int16_from_bytes(data)
        yield samples


def test_soundlevel():

    SR = 16000
    chunk_size = 128
    mic_dbfs = -25
    fast_meter = SoundlevelMeter(chunk_size, SR, mic_dbfs, time_integration=0.125)
    linear_meter = SoundlevelMeter(chunk_size, SR, mic_dbfs, time_integration=None)

    with open('out.csv', 'w') as out:
        with open('test_burst.wav', 'rb') as f:
            t = 0.0
            for chunk in read_wav(f, SR, frames=chunk_size):
                #print(min(chunk), max(chunk))

                lf = fast_meter.process(chunk)
                level = linear_meter.process(chunk)

                t += ( len(chunk)/SR )

                line = '{0:.3f},{1:.1f},{2:.1f}'.format(t, level, lf)
                print(line)
                out.write(line+'\n')


if __name__ == '__main__':
    test_soundlevel()
    

