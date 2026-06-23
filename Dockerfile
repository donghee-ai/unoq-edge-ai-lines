FROM ubuntu:22.04

# 1) 환경변수 (apt 대화형 차단, pip 캐시 비활성화 등)
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 2) 시스템 패키지 (Python + OpenCV/ffmpeg 의존성 + 개발 도구)
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-dev \
        python-is-python3 \
        build-essential \
        git \
        wget \
        curl \
        ca-certificates \
        openssh-client \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        sudo \
    && rm -rf /var/lib/apt/lists/*

# 3) 호스트 UID/GID 받아서 non-root 유저 만들기
ARG USER_UID=1000
ARG USER_GID=1000
ARG USERNAME=dev

RUN if getent group ${USER_GID} >/dev/null; then \
        existing=$(getent group ${USER_GID} | cut -d: -f1); \
        groupmod -n ${USERNAME} ${existing}; \
    else \
        groupadd -g ${USER_GID} ${USERNAME}; \
    fi \
    && useradd -m -u ${USER_UID} -g ${USER_GID} -s /bin/bash ${USERNAME} \
    && echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/${USERNAME} \
    && chmod 0440 /etc/sudoers.d/${USERNAME}

# 4) 이후로는 이 유저로 동작
USER ${USERNAME}
WORKDIR /work

# 5) Python 패키지 설치 — requirements.lock 우선 (byte-exact 재현)
#    requirements.txt는 사람 친화적 의도 표현용으로 보관 (실제 설치는 lock 기준)
COPY --chown=${USER_UID}:${USER_GID} requirements.txt /tmp/requirements.txt
COPY --chown=${USER_UID}:${USER_GID} requirements.lock /tmp/requirements.lock
RUN pip3 install --user --upgrade pip setuptools wheel \
    && pip3 install --user -r /tmp/requirements.lock

# 6) ~/.local/bin을 PATH에 추가 (pip --user로 깐 명령어가 잡히게)
ENV PATH="/home/${USERNAME}/.local/bin:${PATH}"

# 7) 컨테이너 시작 시 기본으로 bash 실행
CMD ["/bin/bash"]
