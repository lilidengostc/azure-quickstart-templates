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
    },
    "autoDeployBosh": {
      "value": "enabled"
    }
  }
}
EOF

AZURE_GROUP_NAME=$UUID
echo azure group create ${AZURE_GROUP_NAME} "${AZURE_REGION_NAME}"
azure group create ${AZURE_GROUP_NAME} "${AZURE_REGION_NAME}"
hostName=$(azure group deployment create ${AZURE_GROUP_NAME} --template-file ./bosh-setup-template/bosh-setup/azuredeploy.json --parameters-file ./parameters.json --json | grep "ssh azureuser" | sed 's/.*: "ssh azureuser@\(.*\)"/\1/')

apt-get update
apt-get -y upgrade
apt-get clean
apt-get install --yes python-software-properties software-properties-common
apt-add-repository --yes ppa:ansible/ansible
apt-get update
apt-get install --yes ansible

echo $hostName >> /etc/ansible/hosts
sed -i -e "s/#host_key_checking/host_key_checking/" /etc/ansible/ansible.cfg
ansible $hostName -a "./deploy_cloudfoundry.sh example_manifests/single-vm-cf.yml"

azure group delete ${AZURE_GROUP_NAME} --quiet
