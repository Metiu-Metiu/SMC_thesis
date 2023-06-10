import torch
import torchaudio
from torch.utils.data.dataset import Dataset
import pandas 
import os
import matplotlib.pyplot as plt
import librosa

from Configuration_Dictionary import configDict

######################################################################################################################################################
# DATASET CLASS (extends torch.utils.data.Dataset) 

class Dataset_Wrapper(Dataset):
    def __init__(self,
                audioFiles_Directory_,
                groundTruth_CsvFIlePath_,
                rangeOfColumnNumbers_ToConsiderInCsvFile_, 
                device_, 
                transform = None,
                target_transform = None):
        '''
        For supervised tasks, rangeOfColumnNumbers_ToConsiderInCsvFile_ must not be None. 
        See __getItem()__ documentation for more details.
        '''
        # print(f'Initializing Dataset_Wrapper object.')
        # print(f'    Audio files directory : {audioFiles_Directory_}')
        # print(f'    Ground truth .csv file path : {groundTruth_CsvFIlePath_}')
        # print(f'    Range of column numbers to consider in the .csv file : {rangeOfColumnNumbers_ToConsiderInCsvFile_}')   
        self.device = device_
        self.labels = pandas.read_csv(groundTruth_CsvFIlePath_)
        if rangeOfColumnNumbers_ToConsiderInCsvFile_ is not None:
            self.rangeOfColumnNumbers_ToConsiderInCsvFile = rangeOfColumnNumbers_ToConsiderInCsvFile_
            self.rangeOfColumnNumbers_ToConsiderInCsvFile[1] += 1 # to include the last column
            self.numberOfLabels = (self.rangeOfColumnNumbers_ToConsiderInCsvFile[1] - self.rangeOfColumnNumbers_ToConsiderInCsvFile[0])
            # print(f'    self.numberOfLabels : {self.numberOfLabels}')
        else:
            self.rangeOfColumnNumbers_ToConsiderInCsvFile = None
            self.numberOfLabels = None
        self.audioFiles_Directory = audioFiles_Directory_
        if transform:
            self.transforms = transform
            for transform in self.transforms:
                transform = transform.to(self.device)
        else:
            self.transforms = None
        if target_transform:
            self.target_transform = target_transform.to(self.device)
        else:
            self.target_transform = None

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        '''
        If rangeOfColumnNumbers_ToConsiderInCsvFile_ is not None in the constructor, returns a tuple (audioFile, target) where target is a list of labels
        Else, returns a tuple (audioFile, target) where target is the name of the audioFile
        '''
        verbose = False

        audioFile_path = os.path.join(self.audioFiles_Directory, self.labels.iloc[idx, 0])
        if os.path.exists(audioFile_path):
            assert audioFile_path.endswith(configDict['validation']['nominal_AudioFileExtension']), f"Error while loading {audioFile_path} : Audio file extension is not valid"
            if configDict['validation']['validate_AudioDatasets']:
                audioFile_Metadata = torchaudio.info(audioFile_path)
                assert audioFile_Metadata.sample_rate == configDict['validation']['nominal_SampleRate'], f"Error while loading {audioFile_path} : Sample rate is not valid"
                assert audioFile_Metadata.num_frames == configDict['validation']['nominal_AudioDurationSecs'] * configDict['validation']['nominal_SampleRate'], f"Error while loading {audioFile_path} : Audio duration is not valid"
                assert audioFile_Metadata.num_channels == configDict['validation']['nominal_NumOfAudioChannels'], f"Error while loading {audioFile_path} : Number of audio channels is not valid"
                assert audioFile_Metadata.bits_per_sample == configDict['validation']['nominal_BitQuantization'], f"Error while loading {audioFile_path} : Bit quantization is not valid"
            audioSignal, sample_rate = torchaudio.load(audioFile_path)
            audioSignal = audioSignal / audioSignal.abs().max() # normalize
            if verbose:
                plot_waveform(audioSignal, sample_rate = configDict['validation']['nominal_SampleRate'], title = self.labels.iloc[idx, 0])
            audioSignal = audioSignal.to(self.device)
            if self.rangeOfColumnNumbers_ToConsiderInCsvFile:
                labels = self.labels.iloc[idx, self.rangeOfColumnNumbers_ToConsiderInCsvFile[0]:self.rangeOfColumnNumbers_ToConsiderInCsvFile[1]].to_numpy()
                labels = torch.tensor(list(labels), dtype = configDict['pyTorch_General_Settings']['dtype'])
            else:
                if self.numberOfLabels:
                    labels = torch.empty(self.numberOfLabels)
                else:
                    # labels = torch.empty(0)
                    labels = self.labels.iloc[idx, 0]
            if self.transforms:
                for trans_Num, transform in enumerate(self.transforms):
                    audioSignal = transform(audioSignal)
                    if verbose:
                        if trans_Num == 0:
                            plot_waveform(audioSignal, sample_rate = configDict['inputTransforms_Settings']['resample']['new_freq'], title = self.labels.iloc[idx, 0])
                        elif trans_Num == 1:
                            plot_spectrogram(audioSignal[0], title = self.labels.iloc[idx, 0])
            if self.target_transform and labels:
                labels = self.target_transform(labels)
            # print(f'Audio signal shape : {audioSignal.shape}')
            # print(f'Labels shape : {labels.shape}')
            # print(f'Transforms : {self.transforms}')
            return audioSignal, labels
        else:
            return torch.empty(0), torch.empty(0)
        
    def getAnnotations_ColumnsNames(self):
        # return the column names of the .csv file containing the ground truth
        if self.rangeOfColumnNumbers_ToConsiderInCsvFile is not None:
            return list(self.labels.columns[self.rangeOfColumnNumbers_ToConsiderInCsvFile[0]:self.rangeOfColumnNumbers_ToConsiderInCsvFile[1]])
        else:
            return list()
######################################################################################################################################################

# UTILS
######################################################################################################################################################
def plot_waveform(waveform, sample_rate, title = "waveform"):
    waveform = waveform.numpy()

    num_channels, num_frames = waveform.shape
    time_axis = torch.arange(0, num_frames) / sample_rate

    figure, axes = plt.subplots(num_channels, 1)
    if num_channels == 1:
        axes = [axes]
    for c in range(num_channels):
        axes[c].plot(time_axis, waveform[c], linewidth=1)
        axes[c].grid(True)
        if num_channels > 1:
            axes[c].set_ylabel(f"Channel {c+1}")
    figure.suptitle(str(title + ' sampled at ' +  str(sample_rate) + ' Hz'))
    plt.show(block = True)

def plot_spectrogram(specgram, title=None, ylabel="freq_bin"):
    fig, axs = plt.subplots(1, 1)
    axs.set_title(title or "Spectrogram (db)")
    axs.set_ylabel(ylabel)
    axs.set_xlabel("frame")
    im = axs.imshow(librosa.power_to_db(specgram), origin="lower", aspect="auto")
    fig.colorbar(im, ax=axs)
    plt.show(block = True)


def plot_fbank(fbank, title=None):
    fig, axs = plt.subplots(1, 1)
    axs.set_title(title or "Filter bank")
    axs.imshow(fbank, aspect="auto")
    axs.set_ylabel("frequency bin")
    axs.set_xlabel("mel bin")
    plt.show(block = True)
######################################################################################################################################################