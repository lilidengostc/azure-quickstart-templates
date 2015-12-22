#!/usr/bin/env python

import netaddr
import os
import random
import re
import requests
import sys
from azure.mgmt.common import SubscriptionCloudCredentials
from azure.mgmt.storage import StorageManagementClient
from azure.storage.blob import BlobService
from azure.storage.table import TableService

def get_token_from_client_credentials(endpoint, client_id, client_secret):
    payload = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'resource': 'https://management.core.windows.net/',
    }
    response = requests.post(endpoint, data=payload).json()
    return response['access_token']

def get_storage_client(settings):
    subscription_id = settings['SUBSCRIPTION_ID']
    auth_token = get_token_from_client_credentials(
        endpoint='https://login.windows.net/{0}/oauth2/token'.format(settings['TENANT_ID']),
        client_id=settings['CLIENT_ID'],
        client_secret=settings['CLIENT_SECRET']
    )
    creds = SubscriptionCloudCredentials(subscription_id, auth_token)
    storage_client = StorageManagementClient(creds)
    return storage_client

def create_containers(storage_client, resource_group_name, storage_account_name, blob_public_access=None):
    storage_access_key = storage_client.storage_accounts.list_keys(
        resource_group_name,
        storage_account_name
    ).storage_account_keys.key1
    blob_service = BlobService(storage_account_name, storage_access_key)
    blob_service.create_container('bosh')
    blob_service.create_container(
        container_name='stemcell',
        x_ms_blob_public_access=blob_public_access
    )

def create_tables(storage_client, resource_group_name, storage_account_name):
    # Prepare the table for storing meta datas of storage account and stemcells
    storage_access_key = storage_client.storage_accounts.list_keys(
        resource_group_name,
        storage_account_name
    ).storage_account_keys.key1
    table_service = TableService(storage_account_name, storage_access_key)
    table_service.create_table('stemcells')

def prepare_storage(settings):
    storage_client = get_storage_client(settings)
    resource_group_name = settings["RESOURCE_GROUP_NAME"]

    # Prepare the default storage account
    default_storage_account_name = settings["DEFAULT_STORAGE_ACCOUNT_NAME"]
    create_containers(
        storage_client,
        resource_group_name,
        default_storage_account_name,
        'blob'
    )
    create_tables(
        storage_client,
        resource_group_name,
        default_storage_account_name
    )

    # Prepare the additional storage accounts
    additional_storage_accounts_prefix = settings["ADDITIONAL_STORAGE_ACCOUNTS_PREFIX"]
    additional_storage_accounts_number = settings["ADDITIONAL_STORAGE_ACCOUNTS_NUMBER"]
    for index in range(0, int(additional_storage_accounts_number)):
        additional_storage_account_name = '{0}{1}'.format(
            additional_storage_accounts_prefix,
            index
        )
        create_containers(
            storage_client,
            resource_group_name,
            additional_storage_account_name
        )

def render_bosh_manifest(settings):
    with open('bosh.cert', 'r') as tmpfile:
        ssh_cert = tmpfile.read()
    indentation = " " * 8
    ssh_cert = ("\n"+indentation).join([line for line in ssh_cert.split('\n')])

    ip = netaddr.IPNetwork(settings['SUBNET_ADDRESS_RANGE_FOR_BOSH'])
    gateway_ip = str(ip[1])
    bosh_director_ip = str(ip[4])
    
    # Render the manifest for bosh-init
    bosh_template = 'bosh.yml'
    if os.path.exists(bosh_template):
        with open(bosh_template, 'r') as tmpfile:
            contents = tmpfile.read()
        for k in ["SUBNET_ADDRESS_RANGE_FOR_BOSH", "VNET_NAME", "SUBNET_NAME_FOR_BOSH", "SUBSCRIPTION_ID", "DEFAULT_STORAGE_ACCOUNT_NAME", "RESOURCE_GROUP_NAME", "TENANT_ID", "CLIENT_ID", "CLIENT_SECRET"]:
            v = settings[k]
            contents = re.compile(re.escape("REPLACE_WITH_{0}".format(k))).sub(v, contents)
        contents = re.compile(re.escape("REPLACE_WITH_SSH_CERTIFICATE")).sub(ssh_cert, contents)
        contents = re.compile(re.escape("REPLACE_WITH_GATEWAY_IP")).sub(gateway_ip, contents)
        contents = re.compile(re.escape("REPLACE_WITH_BOSH_DIRECTOR_IP")).sub(bosh_director_ip, contents)
        with open(bosh_template, 'w') as tmpfile:
            tmpfile.write(contents)

def render_cloud_foundry_manifest(settings):
    with open('cloudfoundry.cert', 'r') as tmpfile:
        ssl_cert = tmpfile.read()
    with open('cloudfoundry.key', 'r') as tmpfile:
        ssl_key = tmpfile.read()
    ssl_cert_and_key = "{0}{1}".format(ssl_cert, ssl_key)
    indentation = " " * 8
    ssl_cert_and_key = ("\n"+indentation).join([line for line in ssl_cert_and_key.split('\n')])

    ip = netaddr.IPNetwork(settings['SUBNET_ADDRESS_RANGE_FOR_CLOUD_FOUNDRY'])
    gateway_ip = str(ip[1])
    reserved_ip_from = str(ip[2])
    reserved_ip_to = str(ip[3])

    # Render the manifest of single-vm cloud foundry
    static_ip = str(ip[4])
    cloudfoundry_internal_ip = static_ip
    system_domain = "{0}.xip.io".format(settings["CLOUD_FOUNDRY_PUBLIC_IP"])
    cloudfoundry_template = 'single-vm-cf-224.yml'
    if os.path.exists(cloudfoundry_template):
        with open(cloudfoundry_template, 'r') as tmpfile:
            contents = tmpfile.read()
        for k in ["SUBNET_ADDRESS_RANGE_FOR_CLOUD_FOUNDRY", "VNET_NAME", "SUBNET_NAME_FOR_CLOUD_FOUNDRY", "CLOUD_FOUNDRY_PUBLIC_IP"]:
            v = settings[k]
            contents = re.compile(re.escape("REPLACE_WITH_{0}".format(k))).sub(v, contents)
        contents = re.compile(re.escape("REPLACE_WITH_SSL_CERT_AND_KEY")).sub(ssl_cert_and_key, contents)
        contents = re.compile(re.escape("REPLACE_WITH_GATEWAY_IP")).sub(gateway_ip, contents)
        contents = re.compile(re.escape("REPLACE_WITH_RESERVED_IP_FROM")).sub(reserved_ip_from, contents)
        contents = re.compile(re.escape("REPLACE_WITH_RESERVED_IP_TO")).sub(reserved_ip_to, contents)
        contents = re.compile(re.escape("REPLACE_WITH_STATIC_IP")).sub(static_ip, contents)
        contents = re.compile(re.escape("REPLACE_WITH_CLOUD_FOUNDRY_INTERNAL_IP")).sub(cloudfoundry_internal_ip, contents)
        contents = re.compile(re.escape("REPLACE_WITH_SYSTEM_DOMAIN")).sub(system_domain, contents)
        with open(cloudfoundry_template, 'w') as tmpfile:
            tmpfile.write(contents)

    # Render the manifest of multiple-vm cloud foundry
    static_ip_from = str(ip[4])
    static_ip_to = str(ip[100])
    haproxy_ip = str(ip[4])
    postgres_ip = str(ip[11])
    router_ip = str(ip[12])
    nats_ip = str(ip[13])
    etcd_ip = str(ip[14])
    nfs_ip = str(ip[15])
    system_domain = "{0}.xip.io".format(settings["CLOUD_FOUNDRY_PUBLIC_IP"])
    cloudfoundry_template = 'multiple-vm-cf-224.yml'
    if os.path.exists(cloudfoundry_template):
        with open(cloudfoundry_template, 'r') as tmpfile:
            contents = tmpfile.read()
        for k in ["SUBNET_ADDRESS_RANGE_FOR_CLOUD_FOUNDRY", "VNET_NAME", "SUBNET_NAME_FOR_CLOUD_FOUNDRY", "CLOUD_FOUNDRY_PUBLIC_IP"]:
            v = settings[k]
            contents = re.compile(re.escape("REPLACE_WITH_{0}".format(k))).sub(v, contents)
        contents = re.compile(re.escape("REPLACE_WITH_SSL_CERT_AND_KEY")).sub(ssl_cert_and_key, contents)
        contents = re.compile(re.escape("REPLACE_WITH_GATEWAY_IP")).sub(gateway_ip, contents)
        contents = re.compile(re.escape("REPLACE_WITH_RESERVED_IP_FROM")).sub(reserved_ip_from, contents)
        contents = re.compile(re.escape("REPLACE_WITH_RESERVED_IP_TO")).sub(reserved_ip_to, contents)
        contents = re.compile(re.escape("REPLACE_WITH_STATIC_IP_FROM")).sub(static_ip_from, contents)
        contents = re.compile(re.escape("REPLACE_WITH_STATIC_IP_TO")).sub(static_ip_to, contents)
        contents = re.compile(re.escape("REPLACE_WITH_HAPROXY_IP")).sub(haproxy_ip, contents)
        contents = re.compile(re.escape("REPLACE_WITH_POSTGRES_IP")).sub(postgres_ip, contents)
        contents = re.compile(re.escape("REPLACE_WITH_ROUTER_IP")).sub(router_ip, contents)
        contents = re.compile(re.escape("REPLACE_WITH_NATS_IP")).sub(nats_ip, contents)
        contents = re.compile(re.escape("REPLACE_WITH_ETCD_IP")).sub(etcd_ip, contents)
        contents = re.compile(re.escape("REPLACE_WITH_NFS_IP")).sub(nfs_ip, contents)
        contents = re.compile(re.escape("REPLACE_WITH_SYSTEM_DOMAIN")).sub(system_domain, contents)
        with open(cloudfoundry_template, 'w') as tmpfile:
            tmpfile.write(contents)

    # Render the manifest of cloud foundry for enterprise
    static_ip_from = str(ip[4])
    static_ip_to = str(ip[100])
    haproxy_ip = str(ip[4])
    postgres_ip = str(ip[11])
    router1_ip = str(ip[12])
    router2_ip = str(ip[22])
    nats_ip = str(ip[13])
    etcd_ip = str(ip[14])
    nfs_ip = str(ip[15])
    system_domain = "{0}.xip.io".format(settings["CLOUD_FOUNDRY_PUBLIC_IP"])
    cloudfoundry_template = 'cf-for-enterprise-224.yml'
    if os.path.exists(cloudfoundry_template):
        with open(cloudfoundry_template, 'r') as tmpfile:
            contents = tmpfile.read()
        for k in ["SUBNET_ADDRESS_RANGE_FOR_CLOUD_FOUNDRY", "VNET_NAME", "SUBNET_NAME_FOR_CLOUD_FOUNDRY", "CLOUD_FOUNDRY_PUBLIC_IP"]:
            v = settings[k]
            contents = re.compile(re.escape("REPLACE_WITH_{0}".format(k))).sub(v, contents)
        contents = re.compile(re.escape("REPLACE_WITH_SSL_CERT_AND_KEY")).sub(ssl_cert_and_key, contents)
        contents = re.compile(re.escape("REPLACE_WITH_GATEWAY_IP")).sub(gateway_ip, contents)
        contents = re.compile(re.escape("REPLACE_WITH_RESERVED_IP_FROM")).sub(reserved_ip_from, contents)
        contents = re.compile(re.escape("REPLACE_WITH_RESERVED_IP_TO")).sub(reserved_ip_to, contents)
        contents = re.compile(re.escape("REPLACE_WITH_STATIC_IP_FROM")).sub(static_ip_from, contents)
        contents = re.compile(re.escape("REPLACE_WITH_STATIC_IP_TO")).sub(static_ip_to, contents)
        contents = re.compile(re.escape("REPLACE_WITH_HAPROXY_IP")).sub(haproxy_ip, contents)
        contents = re.compile(re.escape("REPLACE_WITH_POSTGRES_IP")).sub(postgres_ip, contents)
        contents = re.compile(re.escape("REPLACE_WITH_ROUTER1_IP")).sub(router1_ip, contents)
        contents = re.compile(re.escape("REPLACE_WITH_ROUTER2_IP")).sub(router2_ip, contents)
        contents = re.compile(re.escape("REPLACE_WITH_NATS_IP")).sub(nats_ip, contents)
        contents = re.compile(re.escape("REPLACE_WITH_ETCD_IP")).sub(etcd_ip, contents)
        contents = re.compile(re.escape("REPLACE_WITH_NFS_IP")).sub(nfs_ip, contents)
        contents = re.compile(re.escape("REPLACE_WITH_SYSTEM_DOMAIN")).sub(system_domain, contents)
        additional_storage_accounts_prefix = settings["ADDITIONAL_STORAGE_ACCOUNTS_PREFIX"]
        additional_storage_accounts_number = settings["ADDITIONAL_STORAGE_ACCOUNTS_NUMBER"]
        additional_storage_accounts = [ "{0}{1}".format(additional_storage_accounts_prefix, index) for index in range(0, int(additional_storage_accounts_number))]
        contents = re.compile(re.escape("REPLACE_WITH_NATS_STORAGE_ACCOUNT")).sub(random.choice(additional_storage_accounts), contents)
        contents = re.compile(re.escape("REPLACE_WITH_ETCD_SERVER_STORAGE_ACCOUNT")).sub(random.choice(additional_storage_accounts), contents)
        contents = re.compile(re.escape("REPLACE_WITH_NFS_SERVER_STORAGE_ACCOUNT")).sub(random.choice(additional_storage_accounts), contents)
        contents = re.compile(re.escape("REPLACE_WITH_POSTGRES_STORAGE_ACCOUNT")).sub(random.choice(additional_storage_accounts), contents)
        contents = re.compile(re.escape("REPLACE_WITH_CC_STORAGE_ACCOUNT")).sub(random.choice(additional_storage_accounts), contents)
        contents = re.compile(re.escape("REPLACE_WITH_HAPROXY_STORAGE_ACCOUNT")).sub(random.choice(additional_storage_accounts), contents)
        contents = re.compile(re.escape("REPLACE_WITH_HEALTH_MANAGER_STORAGE_ACCOUNT")).sub(random.choice(additional_storage_accounts), contents)
        contents = re.compile(re.escape("REPLACE_WITH_DOPPLER_STORAGE_ACCOUNT")).sub(random.choice(additional_storage_accounts), contents)
        contents = re.compile(re.escape("REPLACE_WITH_LOGGREGATOR_STORAGE_ACCOUNT")).sub(random.choice(additional_storage_accounts), contents)
        contents = re.compile(re.escape("REPLACE_WITH_UAA_STORAGE_ACCOUNT")).sub(random.choice(additional_storage_accounts), contents)
        contents = re.compile(re.escape("REPLACE_WITH_ROUTER_STORAGE_ACCOUNT")).sub(random.choice(additional_storage_accounts), contents)
        contents = re.compile(re.escape("REPLACE_WITH_RUNNER1_STORAGE_ACCOUNT")).sub(random.choice(additional_storage_accounts), contents)
        contents = re.compile(re.escape("REPLACE_WITH_RUNNER2_STORAGE_ACCOUNT")).sub(random.choice(additional_storage_accounts), contents)
        with open(cloudfoundry_template, 'w') as tmpfile:
            tmpfile.write(contents)

def get_settings():
    settings = dict()
    for item in sys.argv[1].split(';'):
        key, value = item.split(':')
        settings[key] = value
    settings['TENANT_ID'] = sys.argv[2]
    settings['CLIENT_ID'] = sys.argv[3]
    settings['CLIENT_SECRET'] = sys.argv[4]
    return settings

def main():
    settings = get_settings()

    prepare_storage(settings)

    render_bosh_manifest(settings)

    render_cloud_foundry_manifest(settings)

if __name__ == "__main__":
    main()
