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
    && rm -rf /var/lib/apt/lists/*

RUN \
    git clone -b lookahead-1.8.0 --single-branch https://github.com/alphacep/kaldi /opt/kaldi \
    && cd /opt/kaldi/tools \
    && sed -i 's:status=0:exit 0:g' extras/check_dependencies.sh \
    && sed -i 's:--enable-ngram-fsts:--enable-ngram-fsts --disable-bin:g' Makefile \
    && make -j $(nproc) openfst cub \
    && if [ "x$KALDI_MKL" != "x1" ] ; then \
          extras/install_openblas_clapack.sh; \
       else \
          extras/install_mkl.sh; \
       fi \
    \
    && cd /opt/kaldi/src \
    && if [ "x$KALDI_MKL" != "x1" ] ; then \
          ./configure --mathlib=OPENBLAS_CLAPACK --shared; \
       else \
          ./configure --mathlib=MKL --shared; \
       fi \
    && sed -i 's:-msse -msse2:-msse -msse2:g' kaldi.mk \
    && sed -i 's: -O1 : -O3 :g' kaldi.mk \
    && make -j $(nproc) online2 lm rnnlm
    
ENV PATH="/root/miniconda3/bin:${PATH}"
ARG PATH="/root/miniconda3/bin:${PATH}"

RUN wget \
    https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
    && mkdir /root/.conda \
    && bash Miniconda3-latest-Linux-x86_64.sh -b \
    && rm -f Miniconda3-latest-Linux-x86_64.sh 
RUN conda --version

RUN \    
    git clone -b intermediate_full_results https://github.com/alumae/vosk-api /opt/vosk-api \
    && cd /opt/vosk-api/src \
    && KALDI_MKL=$KALDI_MKL KALDI_ROOT=/opt/kaldi make -j $(nproc) \
    && cd /opt/vosk-api/python \
    && python3 ./setup.py install


RUN conda install -c conda-forge pynini=2.1.3

RUN conda install pytorch=1.8.1 torchvision torchaudio=0.8.1 cpuonly -c pytorch

RUN pip install pytorch-lightning==1.2.5 ray torchmetrics==0.2.0 \
    tokenizers pytorch-nlp py-term matplotlib scipy \
    librosa lxml audiomentations pytest

RUN git clone https://github.com/alumae/streaming-punctuator /opt/streaming-punctuator

RUN git clone https://github.com/alumae/online_speaker_change_detector.git /opt/online-speaker-change-detector

RUN git clone https://github.com/alumae/et-g2p-fst.git /opt/et-g2p-fst

RUN echo '2021-05-07_10:41' >/dev/null && git clone https://github.com/alumae/kiirkirjutaja.git /opt/kiirkirjutaja

COPY ./models /opt/kiirkirjutaja/models

ENV PYTHONPATH="/opt/streaming-punctuator:/opt/online-speaker-change-detector:/opt/et-g2p-fst"

CMD ["/bin/bash"] 