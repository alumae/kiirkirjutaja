import sys
import torch
import torch.nn.functional as F
from itertools import repeat
from collections import deque
from queue import Queue
import threading
import logging
import numpy as np
import ray
import subprocess


# Based on https://github.com/snakers4/silero-vad/blob/master/utils_vad.py
 
class VADiterator:
    def __init__(self,
                 trig_sum: float = 0.25,
                 neg_trig_sum: float = 0.05,
                 num_steps: int = 8,
                 num_samples_per_window: int = 4000):
        self.num_samples = num_samples_per_window
        self.num_steps = num_steps
        assert self.num_samples % num_steps == 0
        self.step = int(self.num_samples / num_steps)   # 500 samples is good enough
        self.prev = torch.zeros(self.num_samples)
        self.last = False
        self.triggered = False
        self.buffer = deque(maxlen=num_steps)
        self.num_frames = 0
        self.trig_sum = trig_sum
        self.neg_trig_sum = neg_trig_sum
        self.current_name = ''

    def refresh(self):
        self.prev = torch.zeros(self.num_samples)
        self.last = False
        self.triggered = False
        self.buffer = deque(maxlen=self.num_steps)
        self.num_frames = 0

    def prepare_batch(self, wav_chunk, name=None):
        if (name is not None) and (name != self.current_name):
            self.refresh()
            self.current_name = name
        assert len(wav_chunk) <= self.num_samples
        self.num_frames += len(wav_chunk)
        if len(wav_chunk) < self.num_samples:
            wav_chunk = F.pad(wav_chunk, (0, self.num_samples - len(wav_chunk)))  # short chunk => eof audio
            self.last = True

        stacked = torch.cat([self.prev, wav_chunk])
        self.prev = wav_chunk

        overlap_chunks = [stacked[i:i+self.num_samples].unsqueeze(0)
                          for i in range(self.step, self.num_samples+1, self.step)]
        return torch.cat(overlap_chunks, dim=0)

    def state(self, model_out):
        current_speech = {}
        speech_probs = model_out[:, 1]  # this is very misleading        
        for i, predict in enumerate(speech_probs):
            self.buffer.append(predict)
            if ((sum(self.buffer) / len(self.buffer)) >= self.trig_sum) and not self.triggered:
                self.triggered = True
                current_speech[self.num_frames - (self.num_steps-i) * self.step] = 'start'
            if ((sum(self.buffer) / len(self.buffer)) < self.neg_trig_sum) and self.triggered:
                current_speech[self.num_frames - (self.num_steps-i) * self.step] = 'end'
                self.triggered = False
        if self.triggered and self.last:
            current_speech[self.num_frames] = 'end'
        if self.last:
            self.refresh()
        return current_speech


def speech_chunk_generator(chunk_queue):
    while True:
        value = chunk_queue.get()
        if value is not None:
            yield value
        else:
            return

class SpeechSegment:
    def __init__(self, start_sample, chunk_queue):
        self.start_sample = start_sample
        self.chunk_queue = chunk_queue

    def chunks(self):
        while True:
            value = self.chunk_queue.get()
            if value is not None:
                yield value
            else:
                return

@ray.remote
class VadModelWrapper():
    def __init__(self):
        self.model = torch.jit.load("models/snakers4_silero-vad/files/model.jit")

    def forward(self, batch):
        return self.model(batch)


class SpeechSegmentGenerator:
    def __init__(self, input_file):
        trig_sum = 0.26
        neg_trig_sum = 0.07
        self.num_steps = 8
        self.num_samples_per_window = 4000
        self.model_wrapper = VadModelWrapper.remote()
        self.vad_iter = VADiterator()
        self.speech_segment_queue = Queue(10)

        if input_file == "-":
            self.stream = sys.stdin.buffer
        else:
            self.stream = subprocess.Popen(['ffmpeg', '-loglevel', 'quiet', '-i',
                                            sys.argv[1],
                                            '-ar', '16000' , '-ac', '1', '-f', 's16le', '-'],
                                            stdout=subprocess.PIPE).stdout

        thread = threading.Thread(target=self.run)
        thread.daemon = True
        thread.start()

    def speech_segments(self):
        while True:
            speech_segment = self.speech_segment_queue.get()
            if speech_segment is not None:
                yield speech_segment
            else:
                return

    def run(self):

        sample_pos = 0
        chunk_queue = None
        # we'll start sending chunks 8 frames before speech is actually detected
        num_rewind_steps = 8
        speech_rewind_buffer = deque(maxlen=num_rewind_steps)

        while True:
            bytes = self.stream.read(self.num_samples_per_window * 2)

            chunk = np.frombuffer(bytes, dtype=np.int16).astype(np.float32) / torch.iinfo(torch.int16).max

            if len(chunk) == 0:
                break
            chunk = torch.from_numpy(chunk)

            batch = self.vad_iter.prepare_batch(chunk)
            with torch.no_grad():
                #vad_outs = self.model(batch)

                vad_outs = ray.get(self.model_wrapper.forward.remote(batch))

            change_points = self.vad_iter.state(vad_outs)

            for j in range(len(vad_outs)):                
                current_frame = sample_pos + j * self.vad_iter.step
                if current_frame in change_points:
                    if change_points[current_frame] == 'start':
                        chunk_queue = Queue(100)
                        speech_segment = SpeechSegment(sample_pos + (j - len(speech_rewind_buffer)) * self.vad_iter.step, chunk_queue)
                        self.speech_segment_queue.put(speech_segment)                                                    
                        for rewind_chunk in speech_rewind_buffer:
                            chunk_queue.put(rewind_chunk)                                                        
                        chunk_queue.put(chunk[j * self.vad_iter.step : (j+1) * self.vad_iter.step])

                    elif change_points[current_frame] == 'end':
                        chunk_queue.put(None)
                        chunk_queue = None
                elif chunk_queue is not None:
                    chunk_queue.put(chunk[j * self.vad_iter.step : (j+1) * self.vad_iter.step])
                speech_rewind_buffer.append(chunk[j * self.vad_iter.step : (j+1) * self.vad_iter.step])
            sample_pos += self.num_samples_per_window

        if chunk_queue is not None:
            chunk_queue.put(None)
        self.speech_segment_queue.put(None)                                                    