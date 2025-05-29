#!/bin/bash

GECKODRIVER_VERSION="v0.34.0"
DOWNLOAD_URL="https://github.com/mozilla/geckodriver/releases/download/${GECKODRIVER_VERSION}/geckodriver-${GECKODRIVER_VERSION}-linux64.tar.gz"
INSTALL_DIR="/usr/local/bin"
GECKODRIVER_EXEC="${INSTALL_DIR}/geckodriver"

# Check if running as root
if [ "$(id -u)" -ne 0 ]; then
  echo "This script needs to be run as root to install geckodriver to ${INSTALL_DIR}."
  echo "Please run with sudo: sudo ./setup_geckodriver.sh"
  exit 1
fi

# Check if geckodriver is already installed
if [ -f "${GECKODRIVER_EXEC}" ]; then
  echo "geckodriver is already installed at ${GECKODRIVER_EXEC}."
  current_version=$(${GECKODRIVER_EXEC} --version | head -n1 | awk '{print $2}')
  echo "Installed version: ${current_version}"
  # Simple version comparison (assumes GECKODRIVER_VERSION is like "vX.Y.Z")
  if [[ "${GECKODRIVER_VERSION}" == "v${current_version}" ]]; then
    echo "Latest specified version ${GECKODRIVER_VERSION} is already installed. Exiting."
    exit 0
  else
    echo "Consider removing the existing version if you want to install ${GECKODRIVER_VERSION}."
    # exit 0 # or allow re-installation by not exiting here
  fi
fi

echo "Downloading geckodriver ${GECKODRIVER_VERSION}..."
TEMP_DIR=$(mktemp -d)
if ! curl -SL "${DOWNLOAD_URL}" -o "${TEMP_DIR}/geckodriver.tar.gz"; then
  echo "Failed to download geckodriver. Please check the URL or your internet connection."
  rm -rf "${TEMP_DIR}"
  exit 1
fi

echo "Extracting geckodriver..."
if ! tar -xzf "${TEMP_DIR}/geckodriver.tar.gz" -C "${TEMP_DIR}"; then
  echo "Failed to extract geckodriver."
  rm -rf "${TEMP_DIR}"
  exit 1
fi

echo "Installing geckodriver to ${INSTALL_DIR}..."
if ! mv "${TEMP_DIR}/geckodriver" "${GECKODRIVER_EXEC}"; then
  echo "Failed to move geckodriver to ${INSTALL_DIR}. Check permissions."
  rm -rf "${TEMP_DIR}"
  exit 1
fi

echo "Setting execute permissions..."
if ! chmod +x "${GECKODRIVER_EXEC}"; then
  echo "Failed to set execute permissions on ${GECKODRIVER_EXEC}."
  # Attempt to remove the moved file if chmod fails, to avoid partial install
  rm -f "${GECKODRIVER_EXEC}" 
  rm -rf "${TEMP_DIR}"
  exit 1
fi

echo "Cleaning up..."
rm -rf "${TEMP_DIR}"

echo "geckodriver ${GECKODRIVER_VERSION} installed successfully to ${GECKODRIVER_EXEC}."
${GECKODRIVER_EXEC} --version

exit 0
