FROM python:3.11-slim-bullseye as builder

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



FROM python:3.11-slim-bullseye

ARG CHROME_VERSION=131
ARG UID
ARG GID=0
ARG UNAME=uuu

ENV PACKAGES_DIR=/packages
ENV CHROME_VERSION=${CHROME_VERSION}

# Copy dummy packages
COPY --from=builder ${PACKAGES_DIR} ${PACKAGES_DIR}

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

COPY utils/linux_chrome_installer.py /opt/flare_bypasser/bin/linux_chrome_installer.py

COPY . flare_bypasser
RUN pip install flare_bypasser/

COPY rootfs /

USER ${UID}

ENV PYTHONPATH "${PYTHONPATH}:/opt/flare_bypasser/lib/"

# dumb-init avoids zombie chromium processes
ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["/bin/bash", "-c", "/opt/flare_bypasser/bin/FlareBypasserRun.sh"]
