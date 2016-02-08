#!/usr/bin/env bash

set -e

azure login --service-principal -u ${AZURE_CLIENT_ID} -p ${AZURE_CLIENT_SECRET} --tenant ${AZURE_TENANT_ID}
azure config mode arm

azure group delete ${AZURE_GROUP_NAME} --quiet
