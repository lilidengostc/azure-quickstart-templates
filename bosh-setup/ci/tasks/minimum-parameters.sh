#!/usr/bin/env bash

set -e

azure login --service-principal -u ${AZURE_CLIENT_ID} -p ${AZURE_CLIENT_SECRET} --tenant ${AZURE_TENANT_ID}
azure config mode arm

UUID=$(cat /proc/sys/kernel/random/uuid)
UUID=${UUID//-}
UUID="cf${UUID:0:22}"

cat > parameters.json << EOF
{
  "\$schema": "http://schema.management.azure.com/schemas/2015-01-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "vmName": {
      "value": "$UUID"
    },
    "adminUsername": {
      "value": "azureuser"
    },
    "sshKeyData": {
      "value": "${SSH_KEY_DATA}"
    },
    "tenantID": {
      "value": "${AZURE_TENANT_ID}"
    },
    "clientID": {
      "value": "${AZURE_CLIENT_ID}"
    },
    "clientSecret": {
      "value": "${AZURE_CLIENT_SECRET}"
    }
  }
}
EOF
azure group create -n "$UUID" -l "${AZURE_REGION_NAME}" -d "bosh-setup-template"  -f ./bosh-setup-template/bosh-setup/azuredeploy.json -e ./parameters.json -vv
