FROM python:3.9-slim-buster

RUN pip install torch==1.13.1+cpu torchvision==0.14.1+cpu torchaudio==0.13.1 --extra-index-url https://download.pytorch.org/whl/cpu

RUN pip3 install pytorch-lightning==1.2.5 'ray[default]' torchmetrics==0.2.0 \
    tokenizers pytorch-nlp py-term matplotlib scipy \
    librosa==0.8.0 lxml audiomentations pytest event-scheduler \
    onnx sherpa-onnx 

RUN apt-get update && apt-get install  -y --no-install-recommends git ffmpeg

COPY models /opt/models

RUN echo '2022-01-31_16:24' >/dev/null

RUN git clone https://github.com/alumae/online_speaker_change_detector.git /opt/online-speaker-change-detector

RUN mkdir /opt/kiirkirjutaja \
    && cd /opt/kiirkirjutaja && ln -s ../models
    
COPY *.py /opt/kiirkirjutaja/

ENV PYTHONPATH="/opt/online-speaker-change-detector"

WORKDIR /opt/kiirkirjutaja

CMD ["/bin/bash"] 
