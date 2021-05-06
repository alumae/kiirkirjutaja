# About

Kiirkirjutaja is a realtime speech-to-text tool designed for real-time subtitling of TV broadcasts
and streaming media.

It's architecture is almost monolithic and therefore quite ugly, as the different components are hardwired to each other.

Some of the components are specific to Estonian, but it should be relatively easy to adapt this tool
to other languages.

It consists of the following components:

  * Speech activity detector (https://github.com/snakers4/silero-vad)
  * Online speaker change detector (https://github.com/alumae/online_speaker_change_detector)
  * Speech recognition: we use a forked version of Vosk API (https://github.com/alphacep/vosk-api), which is in turn based on Kaldi
  * Unknown word reconstuctor (words not in the speech recognition vocabulary are reconstructed using a phoneme-to-grapheme tool, which is based on FSTs and an n-gram model)
  * Compound word recognizer: for glueing together compound word tokens, using an n-gram model
  * Puncutator, LSTM-based (https://github.com/alumae/streaming-punctuator)
  * Words-to-numbers converter (FST-based, using Pynini)

