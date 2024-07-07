#!/bin/bash

# Create the instance
gcloud compute instances create "instance-n2-standard-4" \
    --image-project "ubuntu-os-cloud" \
    --image-family "ubuntu-2204-lts" \
    --zone "europe-west1-b" \
    --machine-type "n2-standard-4" \
    --boot-disk-size "100GB" \
    --tags "cc" \
    --enable-nested-virtualization

gcloud compute instances list
gcloud compute disks list