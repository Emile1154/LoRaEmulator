
FROM ubuntu:jammy

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Yekaterinburg

# Set hostname
RUN echo "docker" > /etc/hostname

# Set locales
RUN apt-get update && apt-get install -y locales
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen
RUN sed -i '/ru_RU.UTF-8/s/^# //g' /etc/locale.gen
RUN locale-gen
RUN update-locale LANG=ru_RU.UTF-8

ENV LANG ru_RU.UTF-8

# Install required packages
RUN apt-get update && apt-get install -y \
    python-is-python3 sudo nano vim \
    adwaita-icon-theme adwaita-icon-theme-full libnotify4 libsdl2-2.0-0 \
    build-essential automake flex bison \
    libgtk-3-dev libgl1-mesa-dev libglu1-mesa-dev \
    libpython3.10-dev libssl-dev unzip \
    python3.10 virtualenv cmake git wget libsecret-1-0 \
    libgpiod-dev libyaml-cpp-dev libbluetooth-dev libusb-1.0-0-dev libi2c-dev libuv1-dev libxkbcommon-dev libinput-dev libsqlite3-dev \
    openssl libssl-dev libulfius-dev liborcania-dev libsdl2-dev uwsc


# Create user
ARG USER=user
RUN useradd -ms /bin/bash ${USER}
RUN echo "${USER} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers
RUN echo "PS1='\[\033[01;32m\]\u@\h\[\033[00m\] \[\033[01;34m\]\W\[\033[00m\]$ '" >> /home/${USER}/.bashrc


USER root


RUN pip install platformio

# COPY 99-platformio-udev.rules /etc/udev/rules.d/99-platformio-udev.rules
USER ${USER}
WORKDIR /home/${USER}
HEALTHCHECK NONE