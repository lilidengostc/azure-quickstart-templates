#!/usr/bin/env bash

if [[ $# -ne 1 || -z "$1" ]]; then
    echo "Usage: ./update-china-storage-account.sh <template-version>. For example: ./update-china-storage-account.sh v1-0-0"
    exit 1
fi

set -e

# The template version should be same as variables('templateVersion') in azuredeploy.json
template_version="$1"

azure storage blob upload scripts/create_cert.sh bosh-setup ${template_version}/scripts/create_cert.sh --quiet
azure storage blob upload scripts/deploy_bosh.sh bosh-setup ${template_version}/scripts/deploy_bosh.sh --quiet
azure storage blob upload scripts/deploy_cloudfoundry.sh bosh-setup ${template_version}/scripts/deploy_cloudfoundry.sh --quiet
azure storage blob upload scripts/inject_xip_io_records.py bosh-setup ${template_version}/scripts/inject_xip_io_records.py --quiet
azure storage blob upload scripts/init.sh bosh-setup ${template_version}/scripts/init.sh --quiet
azure storage blob upload scripts/setup_env bosh-setup ${template_version}/scripts/setup_env --quiet
azure storage blob upload scripts/setup_env.py bosh-setup ${template_version}/scripts/setup_env.py --quiet
azure storage blob upload manifests/bosh.yml bosh-setup ${template_version}/manifests/bosh.yml --quiet
azure storage blob upload manifests/single-vm-cf.yml bosh-setup ${template_version}/manifests/single-vm-cf.yml --quiet
azure storage blob upload manifests/multiple-vm-cf.yml bosh-setup ${template_version}/manifests/multiple-vm-cf.yml --quiet
