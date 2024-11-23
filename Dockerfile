ARG PYTHON_VERSION=3.11

FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ARG CHROME_VERSION=""

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
RUN chmod +x ./gost-install.sh && bash -c "./gost-install.sh --install"

COPY utils/linux_chrome_archive_installer.py ./linux_chrome_archive_installer.py
COPY utils/linux_chrome_deb_repo_installer.sh ./linux_chrome_deb_repo_installer.sh

# If CHROME_VERSION ins't defined obviously use tested version by platform.
# TODO: for arm64 (mac m1) check: m.b. chromium 130 is available - in this case use equal versions for arm64,aarch64.
RUN if [ "$CHROME_VERSION" = "" ] ; then \
  BUILD_ARCH="$(arch)" ; \
  if [ "$BUILD_ARCH" = "arm64" ] ; then echo 'CHROME_VERSION="120."' >>/tmp/build.env ; \
  elif [ "$BUILD_ARCH" = "aarch64" -o "$BUILD_ARCH" = "armv7l" ] ; then echo 'CHROME_VERSION="130."' >>/tmp/build.env ; \
  else echo 'CHROME_VERSION="131."' >>/tmp/build.env ; \
  fi ; \
  else echo 'CHROME_VERSION="'"$CHROME_VERSION"'"' >>/tmp/build.env ; \
  fi

# We prefer version from archive, because it is more productive (faster start),
# but for ARM's here no available versions in archive
RUN . /tmp/build.env ; if [ "$(arch)" != "x86_64" ] ; then \
    echo "To install chrome($CHROME_VERSION) from google repository (no archive versions for ARM)" ; \
    chmod +x ./linux_chrome_deb_repo_installer.sh ; \
    bash -c "./linux_chrome_deb_repo_installer.sh /opt/flare_bypasser/installed_chrome/ '$CHROME_VERSION'" || \
    { echo "Can't install chrome (required version '$CHROME_VERSION')" >&2 ; exit 1 ; } ; \
  else \
    echo "To install chrome($CHROME_VERSION) from archive" ; \
    mkdir -p /opt/flare_bypasser/installed_chrome/usr/bin/ ; \
    python3 ./linux_chrome_archive_installer.py \
      --version-prefix="$CHROME_VERSION" \
      --install-root=/opt/flare_bypasser/installed_chrome/usr/bin/ \
      --arch=$(arch) || \
    { echo "Can't install chrome (required version '$CHROME_VERSION')" >&2 ; exit 1 ; } ; \
  fi


FROM python:${PYTHON_VERSION}-slim-bookworm

ARG UID=1111
ARG GID=0
ARG UNAME=flare_bypasser
ARG CHECK_SYSTEM=false
ARG CHROME_DISABLE_GPU=false

ENV PACKAGES_DIR=/packages
ENV CHECK_SYSTEM=${CHECK_SYSTEM}
ENV CHROME_DISABLE_GPU=${CHROME_DISABLE_GPU}
ENV DEBUG=false
ENV VERBOSE=false
ENV FORKS=
ENV PYTHONPATH=/usr/lib/python3/dist-packages/
#< trick for use apt installed packages on package installation with using pip.

# Copy dummy packages
COPY --from=builder ${PACKAGES_DIR} ${PACKAGES_DIR}
COPY --from=builder /usr/local/bin/gost /usr/local/bin/gost

# Copy installed chrome
COPY --from=builder /opt/flare_bypasser/installed_chrome /

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
  && find /usr/lib/ -type f -name 'libmfxhw*' -delete \
  && find /usr/lib/ -type d -name mfx -exec rm -rf {} \; \
  && mkdir -p /app/bin/

RUN mkdir -p "/app/.config/chromium/Crash Reports/pending"

RUN echo '%sudo ALL=(ALL:ALL) NOPASSWD:ALL' >/etc/sudoers.d/nopasswd \
  && adduser --disabled-password --gecos '' --uid "${UID}" --gid "${GID}" --shell /bin/bash ${UNAME} \
  && adduser ${UNAME} sudo \
  && chown -R ${UNAME} /app/ \
  && mkdir -p /opt/flare_bypasser/var/ \
  && chown -R ${UNAME} /opt/flare_bypasser/var/

WORKDIR /app

# for armv7l install additional packages for build python modules (no binary distribution for some python packages).
RUN apt-get update && apt install -y --no-install-recommends python3-opencv python3-numpy

RUN echo "Install python package for arch: $(arch)"

COPY . flare_bypasser
RUN ADDITIONAL_PYTHONPATH="$PYTHONPATH" pip install --prefer-binary flare_bypasser/

COPY rootfs /

# Cleanup environment - decrease image size.
RUN pip cache purge && apt clean

USER ${UID}

# dumb-init avoids zombie chromium processes
ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["/bin/bash", "-c", "/opt/flare_bypasser/bin/FlareBypasserRun.sh"]
