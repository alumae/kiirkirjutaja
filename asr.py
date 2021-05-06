from vosk import Model, KaldiRecognizer, SetLogLevel
import sys
import os
import sys
import torch
import torchaudio
import json
from queue import Queue
import threading

class TurnDecoder():
    def __init__(self, model, chunk_generator):
        self.model = model
        self.rec = KaldiRecognizer(model, 16000)
        self.chunk_generator = chunk_generator
        self.send_chunk_length = 16000 # how big are the chunks that we send to Kaldi
        self.result_queue = Queue(10)
        thread = threading.Thread(target=self.run)
        thread.daemon = True
        thread.start()

    def decode_results(self):
        while True:
            result = self.result_queue.get()
            if result is not None:
                yield result
            else:
                return

    def run(self):
        buffer = torch.tensor([])

        for chunk in self.chunk_generator:
            buffer = torch.cat([buffer, chunk])
            if len(buffer) >= self.send_chunk_length:
                bytes = (buffer * torch.iinfo(torch.int16).max).short().numpy().tobytes()
                if self.rec.AcceptWaveform(bytes):           
                    res = self.rec.Result()
                    jres = json.loads(res)
                    jres["final"] = True
                    self.result_queue.put(jres)
                else:
                    res = self.rec.PartialResult()                    
                    jres = json.loads(res)
                    jres["final"] = False
                    self.result_queue.put(jres)
                buffer = torch.tensor([])                    

        
        if len(buffer) > 0:
            bytes = (buffer * torch.iinfo(torch.int16).max).short().numpy().tobytes()
            self.rec.AcceptWaveform(bytes)           

        res = self.rec.FinalResult()
        jres = json.loads(res)
        jres["final"] = True
        self.result_queue.put(jres)
        self.result_queue.put(None)

