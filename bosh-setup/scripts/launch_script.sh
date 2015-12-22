#!/usr/bin/env bash

set -e

username=$5
home_dir="/home/$username"

apt-get -y install python-pip
pip install azure netaddr

# Generate the private key and certificate
chmod +x create_cert.sh
bosh_key="bosh.key"
bosh_cert="bosh.cert"
./create_cert.sh $bosh_key $bosh_cert
cp $bosh_key $home_dir
chmod 400 $home_dir/$bosh_key
cf_key="cloudfoundry.key"
cf_cert="cloudfoundry.cert"
./create_cert.sh $cf_key $cf_cert

python setup_devbox.py $1 $2 $3 $4

chmod +x deploy_bosh.sh
cp deploy_bosh.sh $home_dir
cp bosh.yml $home_dir
example_manifests="$home_dir/example_manifests"
mkdir -p $example_manifests
cp single-vm-cf-224.yml $example_manifests 
cp multiple-vm-cf-224.yml $example_manifests
cp cf-for-enterprise-224.yml $example_manifests

install_log="$home_dir/install.log"
chmod +x init.sh
./init.sh >$install_log 2>&1

chown -R $username $home_dir
