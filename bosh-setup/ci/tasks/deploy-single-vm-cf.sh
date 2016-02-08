#!/usr/bin/env bash

set -e

azure login --service-principal -u ${AZURE_CLIENT_ID} -p ${AZURE_CLIENT_SECRET} --tenant ${AZURE_TENANT_ID}
azure config mode arm

hostName=$(azure group deployment show ${AZURE_GROUP_NAME} --json | grep "ssh azureuser" | sed 's/.*: "ssh azureuser@\(.*\)"/\1/')

apt-get update
apt-get install --yes python-software-properties software-properties-common
apt-add-repository --yes ppa:ansible/ansible
apt-get update
apt-get clean
apt-get install --yes ansible

echo $hostName >> /etc/ansible/hosts
sed -i -e "s/#host_key_checking/host_key_checking/" /etc/ansible/ansible.cfg
ansible $hostName -a "./deploy_cloudfoundry.sh example_manifests/single-vm-cf.yml"
