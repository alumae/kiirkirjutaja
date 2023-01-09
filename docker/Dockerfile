FROM debian:10.4

ARG KALDI_MKL

RUN sed -i "s/deb.debian.org/ftp.ee.debian.org/g" /etc/apt/sources.list

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wget \
        bzip2 \
        unzip \
        xz-utils \
        g++ \
        make \
        cmake \
        git \
        python3 \
        python3-dev \
        python3-websockets \
        python3-setuptools \
        python3-pip \
        python3-wheel \
        python3-cffi \
        zlib1g-dev \
        automake \
        autoconf \
        libtool \
        pkg-config \
        ca-certificates \
        libsndfile1 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN \
    git clone -b vosk --single-branch https://github.com/alphacep/kaldi /opt/kaldi \
    && cd /opt/kaldi/tools \
    && git clone -b v0.3.13 --single-branch https://github.com/xianyi/OpenBLAS \
    && git clone -b v3.2.1  --single-branch https://github.com/alphacep/clapack \
    && make -C OpenBLAS ONLY_CBLAS=1 DYNAMIC_ARCH=1 TARGET=NEHALEM USE_LOCKING=1 USE_THREAD=0 all \
    && make -C OpenBLAS PREFIX=$(pwd)/OpenBLAS/install install \
    && mkdir -p clapack/BUILD && cd clapack/BUILD && cmake .. && make -j 10 && find . -name "*.a" | xargs cp -t ../../OpenBLAS/install/lib \
    && cd /opt/kaldi/tools \
    && git clone --single-branch https://github.com/alphacep/openfst openfst \
    && cd openfst \
    && autoreconf -i \
    && CFLAGS="-g -O3" ./configure --prefix=/opt/kaldi/tools/openfst --enable-static --enable-shared --enable-far --enable-ngram-fsts --enable-lookahead-fsts --with-pic --disable-bin \
    && make -j 10 && make install \
    && cd /opt/kaldi/src \
    && ./configure --mathlib=OPENBLAS_CLAPACK --shared --use-cuda=no \
    && sed -i 's:-msse -msse2:-msse -msse2:g' kaldi.mk \
    && sed -i 's: -O1 : -O3 :g' kaldi.mk \
    && make -j $(nproc) online2 lm rnnlm \
    && find /opt/kaldi -name "*.o" -exec rm {} \;    
    
ENV PATH="/root/miniconda3/bin:${PATH}"
ARG PATH="/root/miniconda3/bin:${PATH}"

RUN wget \
    https://repo.anaconda.com/miniconda/Miniconda3-py39_22.11.1-1-Linux-x86_64.sh \
    && mkdir /root/.conda \
    && bash Miniconda3-py39_22.11.1-1-Linux-x86_64.sh -b \
    && rm -f Miniconda3-py39_22.11.1-1-Linux-x86_64.sh 
RUN conda --version

RUN \    
    git clone -b intermediate_full_results https://github.com/alumae/vosk-api /opt/vosk-api \
    && cd /opt/vosk-api/src \
    && KALDI_ROOT=/opt/kaldi OPENFST_ROOT=/opt/kaldi/tools/openfst/ OPENBLAS_ROOT=/opt/kaldi/tools/OpenBLAS/install make -j $(nproc) \
    && cd /opt/vosk-api/python \
    && python3 ./setup.py install


RUN conda install -c conda-forge pynini=2.1.3

RUN conda install pytorch=1.10.0 torchvision torchaudio=0.10.0 cpuonly -c pytorch

RUN pip install pytorch-lightning==1.2.5 'ray[default]' torchmetrics==0.2.0 \
    tokenizers pytorch-nlp py-term matplotlib scipy \
    librosa==0.8.0 lxml audiomentations pytest event-scheduler

COPY ./models /opt/models

RUN echo '2022-01-31_16:24' >/dev/null

RUN git clone https://github.com/alumae/streaming-punctuator /opt/streaming-punctuator

RUN git clone https://github.com/alumae/online_speaker_change_detector.git /opt/online-speaker-change-detector

RUN git clone https://github.com/alumae/et-g2p-fst.git /opt/et-g2p-fst

RUN echo '2022-04-11_15:54' >/dev/null \
    && git clone https://github.com/alumae/kiirkirjutaja.git /opt/kiirkirjutaja \
    && cd /opt/kiirkirjutaja && ln -s ../models

ENV PYTHONPATH="/opt/streaming-punctuator:/opt/online-speaker-change-detector:/opt/et-g2p-fst"

WORKDIR /opt/kiirkirjutaja

CMD ["/bin/bash"] 
