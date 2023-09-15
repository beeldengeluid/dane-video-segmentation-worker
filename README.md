# dane-video-segmentation-worker
Running hecate to extract keyframes
Including code for audio extraction and generating spectrogram

## dane-audio-extraction-worker


`src/util` bevat twee classes, waarvan `AudioExtractorUtil.py` de file is met specifieke functies voor VisXP. Daarnaast
is er de `FfMpegUtil.py` met daarin de meer generieke ffMpeg functies.
De `Pipfile` is wellicht niet volledig, maar kan gebruikt worden om het juiste ffmpeg python package te installeren. 

Daarnaast moet er op de container ffmpeg worden geïnstalleerd, zoals bijv. (in mijn WSL/Ubuntu): `sudo apt install ffmpeg`

Contact: wmelder@beeldengeluid.nl
