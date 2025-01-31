FROM ubuntu:focal-20210416
MAINTAINER Chidi Ugonna<chidi_ugonna@hotmail.com>

ENV DEBIAN_FRONTEND noninteractive


##########################
# CREATE BIND and CUSTOM FOLDERS
###########################
RUN mkdir -p /src /xdisk /groups /opt/data /opt/bin /opt/tmp /opt/work /opt/input /opt/output /opt/config /opt/ohpc /cm/shared /cm/local

##########################
# BASE PACKAGES and LOCALE
###########################

RUN apt-get update && \
    apt-get install -y nano \
	               apt-utils \
	               wget \
	               curl \
                   dc \
	               lsb-core \
                   unzip \
                   git \
                   locales

ENV TZ=America/Phoenix
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
ENV LC_CTYPE="en_US.UTF-8"  
ENV LC_ALL="en_US.UTF-8"
ENV LANG="en_US.UTF-8"
ENV LANGUAGE=en_US.UTF-8
RUN echo "LC_ALL=en_US.UTF-8" >> /etc/environment
RUN echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen
RUN echo "LANG=en_US.UTF-8" > /etc/locale.conf
RUN locale-gen en_US.UTF-8
RUN export LC_ALL=en_US.UTF-8


############################
# MINICONDA and Python
############################
WORKDIR /opt/tmp
ENV MINICONDA_HOME=/opt/miniconda
ENV PATH=${MINICONDA_HOME}/bin:${PATH}

RUN wget https://repo.anaconda.com/miniconda/Miniconda3-py311_24.11.1-0-Linux-x86_64.sh && \
    chmod +x Miniconda3-py311_24.11.1-0-Linux-x86_64.sh && \
    /bin/bash ./Miniconda3-py311_24.11.1-0-Linux-x86_64.sh -b -p ${MINICONDA_HOME} -f && \
    conda install -y pip && \
    conda install -y -c conda-forge dicomifier==2.5.3 && \
    pip install nipype==1.8.3 \
                jupyterlab==3.4.4 \ 
                notebook==6.4.12 \
                brkraw==0.3.11 \
                xnat==0.6.2

############################
# HOME DIRECTORY
###########################
# Replace 1000 with your user / group id
RUN export uid=1000 gid=1000 && \
    mkdir -p /home/aacazxnat && \
    mkdir -p /etc/sudoers.d && \
    echo "aacazxnat:x:${uid}:${gid}:aacazxnat,,,:/home/aacazxnat:/bin/bash" >> /etc/passwd && \
    echo "aacazxnat:x:${uid}:" >> /etc/group && \
    echo "aacazxnat ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/aacazxnat && \
    chmod 0440 /etc/sudoers.d/aacazxnat && \
    chown ${uid}:${gid} -R /home/aacazxnat

ENV HOME="/home/aacazxnat"
ENV USER=aacazxnat

RUN mkdir -p /home/aacazxnat/matlab


############################
# STARTUP and CLEANUP and CONFIG
###########################
COPY ./src/startup.sh /opt/bin
COPY ./src/license.txt ${FREESURFER_HOME}
COPY ./src/readme /opt/bin
COPY ./src/version /opt/bin 
COPY ./src/startup.m /home/aacazxnat/matlab/
COPY ./src/uploadraw.py /src
ENV PATH=/opt/bin:$PATH
ENV PATH=/src:$PATH

RUN rm -rf /tmp/*
RUN rm -rf /opt/tmp/*


RUN ldconfig
WORKDIR /opt/work
RUN chmod -R +x /opt/bin
ENTRYPOINT ["/opt/bin/startup.sh"]


