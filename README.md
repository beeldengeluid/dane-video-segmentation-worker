[![main branch](https://github.com/beeldengeluid/dane-video-segmentation-worker/actions/workflows/main-branch.yml/badge.svg)](https://github.com/beeldengeluid/dane-video-segmentation-worker/actions/workflows/main-branch.yml)

# dane-video-segmentation-worker

Running hecate to detect shots and keyframes.
Including code for extracting keyframes,  extracting audio, and generating spectrograms.


## Installation

Install Hecate following the instructions in https://github.com/yahoo/hecate.

```sh
poetry install
```

Installing `python-opencv` in a virtualenv, and thus not as a system package, could cause certain shared-objects to be missing. So far it seems libgl1 might be missing this way. Install it using:

```
apt-get install libgl1
```

To make sure the unit-test work as well

```
apt-get install ffmpeg
```


### Config

For local testing, make sure to put a config.yml in the root of this repo:

```
cp ./config/config.yml config.yml
```


## Relevant links

Also see:
https://stackoverflow.com/questions/64664094/i-cannot-use-opencv2-and-received-importerror-libgl-so-1-cannot-open-shared-obj

https://docs.opencv.org/4.x/d2/de6/tutorial_py_setup_in_ubuntu.html
