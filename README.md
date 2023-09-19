# dane-video-segmentation-worker

Running hecate to extract keyframes
Including code for audio extraction and generating spectrogra


## Installation

```sh
poetry install
```

Installing `python-opencv` in a virtualenv, and thus not as a system package, could cause certain shared-objects to be missing. So far it seems libgl1 might be missing this way. Install it using:

```
sudo apt-get install libgl1
```