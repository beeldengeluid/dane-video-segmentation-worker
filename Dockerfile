FROM debian:buster-slim

# System packages
RUN apt-get clean && apt-get update -y && apt-get upgrade -y

# install dependencies
RUN apt-get install -y git wget vim build-essential cmake pkg-config libavcodec-dev libavformat-dev libswscale-dev libv4l-dev libxvidcore-dev libx264-dev libgtk-3-dev libatlas-base-dev gfortran ffmpeg

# install opencv_contrib
RUN git clone https://github.com/opencv/opencv_contrib.git && \
    cd opencv_contrib && \
    git checkout 3.3.1 && \
    cd ..

# install opencv
RUN git clone https://github.com/opencv/opencv.git && \
    cd opencv && \
    git checkout 3.3.1 && \
    sed -i "43i #define AV_CODEC_FLAG_GLOBAL_HEADER (1 << 22)\n#define CODEC_FLAG_GLOBAL_HEADER AV_CODEC_FLAG_GLOBAL_HEADER\n#define AVFMT_RAWPICTURE 0x0020" modules/videoio/src/cap_ffmpeg_impl.hpp && \
    mkdir build
    
RUN cd /opencv/build && \
    cmake -D CMAKE_BUILD_TYPE=RELEASE \
    -D CMAKE_INSTALL_PREFIX=/usr/local \
    -D INSTALL_C_EXAMPLES=ON \
    -D OPENCV_EXTRA_MODULES_PATH=/opencv_contrib/modules \
    -D BUILD_EXAMPLES=ON \
    -D WITH_FFMPEG=1 \
    -D ENABLE_FAST_MATH=1 \
    -D WITH_LAPACK=OFF .. && \
    make -j2 && \
    make install && export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib>>~/.bashrc

# install hecate
RUN git clone https://github.com/yahoo/hecate.git && \
    cd hecate && \
    make all && \
    make distribute 


## above this line: copied from https://github.com/yahoo/hecate/blob/master/docker/base.Dockerfile


# install Python 3.10 from source

RUN wget https://www.python.org/ftp/python/3.10.12/Python-3.10.12.tgz && \
    tar -xf Python-3.10.*.tgz && \
    cd Python-3.10.*/ && \
    ./configure --prefix=/usr/local --enable-optimizations --enable-shared LDFLAGS="-Wl,-rpath /usr/local/lib" && \
    make -j $(nproc) && \
    make altinstall



## under this line: copied form https://github.com/beeldengeluid/dane-asr-worker/blob/main/Dockerfile


COPY ./ /src

# override this config in Kubernetes with a ConfigMap mounted as a volume to /root/.DANE
RUN mkdir /root/.DANE

# create the mountpoint for storing /input-files and /asr-output dirs
RUN mkdir /mnt/dane-fs

WORKDIR /src

RUN pip install poetry
RUN poetry config virtualenvs.create false && poetry install --no-dev --no-interaction --no-ansi

CMD [ "python", "worker.py" ]

# references
# # ref: https://cerebrumedge.com/blog/entry/compiling-opencv-with-cuda-and-ffmpeg-on-ubuntu-16.04#:~:text=FFMpeg%20and%20OpenCV,OPENCV_SOURCE_CODE%2F3rdparty%2Fffmpeg%2F.
# https://stackoverflow.com/questions/46884682/error-in-building-opencv-with-ffmpeg
# https://stackoverflow.com/questions/12335848/opencv-program-compile-error-libopencv-core-so-2-4-cannot-open-shared-object-f