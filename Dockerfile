ARG PYTHON_VERSION=3.11

FROM python:${PYTHON_VERSION}-slim-bullseye AS builder

ARG CHROME_VERSION=131

WORKDIR /app/

ENV PACKAGES_DIR=/packages

# Build dummy packages to skip installing them and their dependencies
RUN mkdir -p "${PACKAGES_DIR}" \
  && apt-get update \
  && apt-get install -y --no-install-recommends equivs \
  && equivs-control libgl1-mesa-dri \
  && printf 'Section: misc\nPriority: optional\nStandards-Version: 3.9.2\nPackage: libgl1-mesa-dri\nVersion: 99.0.0\nDescription: Dummy package for libgl1-mesa-dri\n' >> libgl1-mesa-dri \
  && equivs-build libgl1-mesa-dri \
  && mv libgl1-mesa-dri_*.deb ${PACKAGES_DIR}/libgl1-mesa-dri.deb \
  && equivs-control adwaita-icon-theme \
  && printf 'Section: misc\nPriority: optional\nStandards-Version: 3.9.2\nPackage: adwaita-icon-theme\nVersion: 99.0.0\nDescription: Dummy package for adwaita-icon-theme\n' >> adwaita-icon-theme \
  && equivs-build adwaita-icon-theme \
  && mv adwaita-icon-theme_*.deb ${PACKAGES_DIR}/adwaita-icon-theme.deb

# Install gost proxy (for process requests with proxy, that require authorization)
RUN apt-get install -y --no-install-recommends curl  # gost-install.sh requirement
COPY utils/gost-install.sh ./gost-install.sh
RUN ./gost-install.sh --install

COPY utils/linux_chrome_installer.py /opt/flare_bypasser/bin/linux_chrome_installer.py
RUN python3 /opt/flare_bypasser/bin/linux_chrome_installer.py \
  --version-prefix="$CHROME_VERSION" \
  --install-root=/opt/flare_bypasser/installed_chrome/ \
  --arch=$(arch) || \
  { echo "Can't install chrome (required version '$CHROME_VERSION')" >&2 ; exit 1 ; }


FROM python:${PYTHON_VERSION}-slim-bullseye

ARG UID=1111
ARG GID=0
ARG UNAME=flare_bypasser
ARG CHECK_SYSTEM=false
ARG CHROME_DISABLE_GPU=false

ENV PACKAGES_DIR=/packages
ENV CHROME_VERSION=${CHROME_VERSION}
ENV CHECK_SYSTEM=${CHECK_SYSTEM}
ENV CHROME_DISABLE_GPU=${CHROME_DISABLE_GPU}

# Copy dummy packages
COPY --from=builder ${PACKAGES_DIR} ${PACKAGES_DIR}
COPY --from=builder /usr/local/bin/gost /usr/local/bin/gost

# Copy installed chrome
COPY --from=builder /opt/flare_bypasser/installed_chrome /usr/bin/

# Install dependencies and create user
# You can test Chromium running this command inside the container:
#    xvfb-run -s "-screen 0 1600x1200x24" chromium --no-sandbox
# The error traces is like this: "*** stack smashing detected ***: terminated"
# To check the package versions available you can use this command:
#    apt-cache madison chromium

# Install dummy packages
RUN dpkg -i ${PACKAGES_DIR}/*.deb \
  # Install dependencies
  && apt-get update \
  && apt-get install -y --no-install-recommends \
    $(apt-cache depends chromium | grep Depends | sed "s/.*ends:\ //" | grep -v -E '^<.*>$' | tr '\n' ' ') \
  && apt-get install -y --no-install-recommends \
    xvfb dumb-init procps curl vim xauth sudo git \
  # Remove temporary files and hardware decoding libraries
  && rm -rf /var/lib/apt/lists/* \
  && rm -f /usr/lib/x86_64-linux-gnu/libmfxhw* \
  && rm -f /usr/lib/x86_64-linux-gnu/mfx/* \
  && mkdir -p /app/bin/

RUN mkdir -p "/app/.config/chromium/Crash Reports/pending"

RUN echo '%sudo ALL=(ALL:ALL) NOPASSWD:ALL' >/etc/sudoers.d/nopasswd \
  && adduser --disabled-password --gecos '' --uid "${UID}" --gid "${GID}" --shell /bin/bash ${UNAME} \
  && adduser ${UNAME} sudo \
  && chown -R ${UNAME} /app/ \
  && mkdir -p /opt/flare_bypasser/var/ \
  && chown -R ${UNAME} /opt/flare_bypasser/var/

WORKDIR /app

RUN apt-get update && apt install -y python3-opencv

COPY . flare_bypasser
RUN pip install flare_bypasser/

COPY rootfs /

USER ${UID}

ENV PYTHONPATH "${PYTHONPATH}:/opt/flare_bypasser/lib/"

# dumb-init avoids zombie chromium processes
ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["/bin/bash", "-c", "/opt/flare_bypasser/bin/FlareBypasserRun.sh"]
